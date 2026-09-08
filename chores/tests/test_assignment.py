from datetime import time

from django.test import TestCase
from django.utils import timezone

from chores.models import Availability, ChorePreference, MemberSkill
from chores.services.assignment import autoassign, best_candidate, recommend_for
from chores.services.tracking import complete_occurrence
from chores.tests.factories import make_chore, make_household, make_member, make_occurrence


class RecommendationTests(TestCase):
    def setUp(self):
        self.household = make_household()
        self.ada = make_member(self.household, display_name='Ada')
        self.bob = make_member(self.household, display_name='Bob')
        self.chore = make_chore(household=self.household, name='Vacuuming', effort_weight=3)
        self.today = timezone.localdate()
        self.occurrence = make_occurrence(self.chore, self.today)

    def test_every_eligible_member_is_ranked_with_a_breakdown(self):
        ranked = recommend_for(self.occurrence)

        self.assertEqual(len(ranked), 2)
        for recommendation in ranked:
            self.assertEqual(
                set(recommendation.breakdown),
                {'workload', 'preference', 'availability', 'suitability'},
            )
            self.assertGreaterEqual(recommendation.score, 0.0)
            self.assertLessEqual(recommendation.score, 1.0)

    def test_ranking_is_sorted_by_descending_score(self):
        scores = [r.score for r in recommend_for(self.occurrence)]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_the_underloaded_member_is_preferred(self):
        heavy = make_chore(household=self.household, name='Bathroom', effort_weight=5)
        complete_occurrence(make_occurrence(heavy, self.today), self.ada)

        self.assertEqual(best_candidate(self.occurrence).member, self.bob)

    def test_a_liked_chore_beats_a_disliked_one_all_else_equal(self):
        ChorePreference.objects.create(
            member=self.ada, chore=self.chore, sentiment=ChorePreference.Sentiment.LIKES
        )
        ChorePreference.objects.create(
            member=self.bob, chore=self.chore, sentiment=ChorePreference.Sentiment.DISLIKES
        )

        self.assertEqual(best_candidate(self.occurrence).member, self.ada)

    def test_availability_on_the_due_weekday_is_preferred(self):
        Availability.objects.create(
            member=self.ada,
            weekday=self.today.weekday(),
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        Availability.objects.create(
            member=self.bob,
            weekday=(self.today.weekday() + 1) % 7,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )

        self.assertEqual(best_candidate(self.occurrence).member, self.ada)

    def test_a_member_who_cannot_perform_is_never_recommended(self):
        MemberSkill.objects.create(member=self.bob, chore=self.chore, can_perform=False)

        ranked = recommend_for(self.occurrence)

        self.assertEqual([r.member for r in ranked], [self.ada])

    def test_skill_outranks_a_strong_workload_signal(self):
        # Bob is far more underloaded, but has opted out of this chore entirely.
        heavy = make_chore(household=self.household, name='Bathroom', effort_weight=9)
        complete_occurrence(make_occurrence(heavy, self.today), self.ada)
        MemberSkill.objects.create(member=self.bob, chore=self.chore, can_perform=False)

        self.assertEqual(best_candidate(self.occurrence).member, self.ada)

    def test_nobody_eligible_yields_no_recommendation(self):
        for member in (self.ada, self.bob):
            MemberSkill.objects.create(member=member, chore=self.chore, can_perform=False)

        self.assertEqual(recommend_for(self.occurrence), [])
        self.assertIsNone(best_candidate(self.occurrence))

    def test_an_empty_household_yields_no_recommendation(self):
        empty = make_household(name='Empty')
        occurrence = make_occurrence(make_chore(household=empty), self.today)

        self.assertEqual(recommend_for(occurrence), [])

    def test_recommendations_are_explainable(self):
        explanation = best_candidate(self.occurrence).explain()

        for factor in ('workload', 'preference', 'availability', 'suitability'):
            self.assertIn(factor, explanation)


class AutoassignTests(TestCase):
    def setUp(self):
        self.household = make_household()
        self.ada = make_member(self.household, display_name='Ada')
        self.bob = make_member(self.household, display_name='Bob')
        self.chore = make_chore(household=self.household)
        self.occurrence = make_occurrence(self.chore, timezone.localdate())

    def test_autoassign_sets_the_top_candidate(self):
        pick = autoassign(self.occurrence)

        self.occurrence.refresh_from_db()
        self.assertEqual(self.occurrence.assigned_to, pick.member)

    def test_autoassign_respects_a_manual_assignment(self):
        self.occurrence.assigned_to = self.bob
        self.occurrence.save(update_fields=['assigned_to'])

        self.assertIsNone(autoassign(self.occurrence))

        self.occurrence.refresh_from_db()
        self.assertEqual(self.occurrence.assigned_to, self.bob)

    def test_autoassign_leaves_the_occurrence_alone_when_nobody_is_eligible(self):
        for member in (self.ada, self.bob):
            MemberSkill.objects.create(member=member, chore=self.chore, can_perform=False)

        self.assertIsNone(autoassign(self.occurrence))

        self.occurrence.refresh_from_db()
        self.assertIsNone(self.occurrence.assigned_to)


class BatchAssignmentTests(TestCase):
    """Assigning many occurrences in one pass must spread them, not stack them."""

    def setUp(self):
        self.household = make_household()
        self.members = [
            make_member(self.household, display_name=name) for name in ('Ada', 'Bo', 'Cy')
        ]
        self.today = timezone.localdate()

    def test_a_batch_spreads_across_the_household(self):
        chore = make_chore(household=self.household, name='Dishes', effort_weight=2)
        occurrences = [
            make_occurrence(chore, self.today + timezone.timedelta(days=offset))
            for offset in range(9)
        ]

        for occurrence in occurrences:
            autoassign(occurrence)

        counts = {
            member.pk: member.assigned_occurrences.count() for member in self.members
        }
        self.assertEqual(sum(counts.values()), 9)
        # Nobody is left idle while somebody else hoards the rota.
        self.assertTrue(all(count > 0 for count in counts.values()), counts)
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1, counts)

    def test_outstanding_work_counts_toward_workload(self):
        heavy = make_chore(household=self.household, name='Bathroom', effort_weight=9)
        light = make_chore(household=self.household, name='Trash', effort_weight=1)
        # Ada is already holding a heavy unfinished chore.
        make_occurrence(heavy, self.today, assigned_to=self.members[0])

        pick = best_candidate(make_occurrence(light, self.today))

        self.assertNotEqual(pick.member, self.members[0])
