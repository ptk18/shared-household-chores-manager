"""
Recommend who should do a chore.

Plan section 9 asks to optimise for *fairness and completion together*: the
fairest assignment is worthless if it will not actually get done. So workload
pulls toward the underloaded member while preference and availability pull
toward the member likely to follow through, and skill is a hard gate.

Deliberately a transparent weighted sum rather than a solver. Every
recommendation carries its per-factor breakdown so a household can see *why* the
system suggested someone — an optimal answer nobody trusts gets overridden, and
then the fairness data rots.
"""

from dataclasses import dataclass

from chores.models import Availability, ChorePreference, MemberSkill
from chores.services.fairness import household_fairness, outstanding_effort

# Weights sum to 1.0. Workload leads because fairness is the product's reason to
# exist; preference and availability together outweigh it, so the system will not
# insist on a fair-but-doomed assignment.
WEIGHTS = {
    'workload': 0.40,
    'preference': 0.25,
    'availability': 0.25,
    'suitability': 0.10,
}

# An unavailable member is discouraged, not excluded — someone has to do it, and
# availability is self-reported and often stale.
UNAVAILABLE_SCORE = 0.25

_SENTIMENT_SCORES = {
    ChorePreference.Sentiment.DISLIKES: 0.0,
    ChorePreference.Sentiment.NEUTRAL: 0.5,
    ChorePreference.Sentiment.LIKES: 1.0,
}


@dataclass(frozen=True)
class Recommendation:
    """A scored candidate, carrying the reasoning that produced it."""

    member: object
    score: float
    breakdown: dict

    def explain(self):
        """One human-readable line per factor, strongest first."""
        parts = sorted(
            self.breakdown.items(), key=lambda kv: kv[1] * WEIGHTS[kv[0]], reverse=True
        )
        return ', '.join(f'{name} {value:.2f}' for name, value in parts)


def _workload_scores(household, window_days):
    """
    Map each member to 0..1, where 1 is the most underloaded.

    Counts work already *assigned but unfinished* alongside work completed.
    Completed effort alone is not enough: assigning a fortnight of chores in one
    pass would otherwise hand every one of them to the same person, because the
    assignments made moments earlier would be invisible to the next decision.

    Uses deviation from expected share, so a member with reduced capacity is not
    punished for having done less than everyone else.
    """
    report = household_fairness(household, window_days=window_days)
    if not report.entries:
        return {}

    outstanding = outstanding_effort(household)
    projected = {
        entry.member.pk: entry.effort + outstanding.get(entry.member.pk, 0)
        for entry in report.entries
    }
    total_projected = sum(projected.values())

    deviations = {}
    for entry in report.entries:
        actual = projected[entry.member.pk] / total_projected if total_projected else 0.0
        deviations[entry.member.pk] = actual - entry.expected_share

    widest, narrowest = max(deviations.values()), min(deviations.values())
    spread = widest - narrowest
    if spread < 1e-9:
        # Everyone is square: workload gives no signal, so stay neutral rather
        # than manufacturing an arbitrary ordering.
        return {pk: 0.5 for pk in deviations}
    return {pk: (widest - dev) / spread for pk, dev in deviations.items()}


def _preference_scores(chore, member_ids):
    stated = {
        p.member_id: _SENTIMENT_SCORES[p.sentiment]
        for p in ChorePreference.objects.filter(chore=chore, member_id__in=member_ids)
    }
    return {pk: stated.get(pk, 0.5) for pk in member_ids}


def _availability_scores(member_ids, due_date):
    """Members who declared no availability are treated as always available."""
    weekday = due_date.weekday()
    declared = set(
        Availability.objects.filter(member_id__in=member_ids).values_list(
            'member_id', flat=True
        )
    )
    free = set(
        Availability.objects.filter(
            member_id__in=member_ids, weekday=weekday
        ).values_list('member_id', flat=True)
    )
    return {
        pk: 1.0 if (pk not in declared or pk in free) else UNAVAILABLE_SCORE
        for pk in member_ids
    }


def _capable_member_ids(chore, members):
    """Skill is a hard gate: an opted-out member is never recommended."""
    blocked = set(
        MemberSkill.objects.filter(
            chore=chore, member__in=members, can_perform=False
        ).values_list('member_id', flat=True)
    )
    return [m.pk for m in members if m.pk not in blocked]


def recommend_for(occurrence, window_days=28, limit=None):
    """
    Rank the household's members as candidates for `occurrence`.

    Returns an empty list when nobody is eligible — every member has opted out of
    this chore, or the household has no members. Callers must handle that rather
    than assume a winner exists.
    """
    chore = occurrence.chore
    members = list(chore.household.members.all())
    eligible_ids = set(_capable_member_ids(chore, members))
    eligible = [m for m in members if m.pk in eligible_ids]
    if not eligible:
        return []

    member_ids = [m.pk for m in eligible]
    workload = _workload_scores(chore.household, window_days)
    preference = _preference_scores(chore, member_ids)
    availability = _availability_scores(member_ids, occurrence.due_date)

    recommendations = []
    for member in eligible:
        breakdown = {
            'workload': workload.get(member.pk, 0.5),
            'preference': preference[member.pk],
            'availability': availability[member.pk],
            # Capacity as a gentle tiebreak: someone at reduced capacity is a
            # slightly worse fit even when the workload maths already accounts
            # for it.
            'suitability': min(float(member.capacity), 1.0),
        }
        score = sum(WEIGHTS[name] * value for name, value in breakdown.items())
        recommendations.append(
            Recommendation(member=member, score=score, breakdown=breakdown)
        )

    recommendations.sort(key=lambda r: (-r.score, r.member.display_name))
    return recommendations[:limit] if limit else recommendations


def best_candidate(occurrence, window_days=28):
    """The single top recommendation, or None if nobody is eligible."""
    ranked = recommend_for(occurrence, window_days=window_days, limit=1)
    return ranked[0] if ranked else None


def autoassign(occurrence, window_days=28):
    """
    Assign `occurrence` to its best candidate and return the recommendation.

    Leaves already-assigned occurrences alone — a household member's manual
    choice outranks the engine's suggestion.
    """
    if occurrence.assigned_to_id is not None:
        return None

    pick = best_candidate(occurrence, window_days=window_days)
    if pick is None:
        return None

    occurrence.assigned_to = pick.member
    occurrence.save(update_fields=['assigned_to'])
    return pick
