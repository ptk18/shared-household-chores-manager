from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Household(models.Model):
    """A group of people who share chores. The top-level tenant of the system."""

    name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Member(models.Model):
    """
    A person's participation in a household.

    Kept as a profile alongside auth.User rather than a custom AUTH_USER_MODEL:
    swapping the user model after the first migration is expensive, and the
    household-specific attributes (role, display name) do not belong on the
    account itself.
    """

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        MEMBER = 'member', 'Member'
        GUEST = 'guest', 'Guest'

    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name='members',
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='member',
    )
    display_name = models.CharField(
        max_length=80,
        help_text='Name shown to the rest of the household.',
    )
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.MEMBER,
    )
    capacity = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('2.00'))],
        help_text=(
            'Share of a full load this member is expected to carry, where 1.00 is '
            'a standard share. Lowered for someone working nights or recovering '
            'from illness; 0.00 excuses them entirely. This is how plan section 4 '
            "'personal circumstances' enters the fairness maths."
        ),
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_name']

    def __str__(self):
        return f'{self.display_name} ({self.household.name})'

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN


class Chore(models.Model):
    """
    A recurring chore definition owned by a household.

    This is the template for work, not the work itself — dated instances live in
    ChoreOccurrence (T2) so that completion history and fairness can be measured
    per instance.
    """

    class Category(models.TextChoices):
        KITCHEN = 'kitchen', 'Kitchen'
        LAUNDRY = 'laundry', 'Laundry'
        CLEANING = 'cleaning', 'Cleaning'
        OUTDOOR = 'outdoor', 'Outdoor'
        SHOPPING = 'shopping', 'Shopping'
        ADMIN = 'admin', 'Household admin'
        OTHER = 'other', 'Other'

    class Frequency(models.TextChoices):
        ONCE = 'once', 'One-off'
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        MONTHLY = 'monthly', 'Monthly'

    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name='chores',
    )
    name = models.CharField(max_length=120)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
    )
    effort_weight = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text=(
            'Relative effort on a 1-10 scale. This is the currency fairness is '
            'measured in, so it is deliberately coarse — vacuuming might be 3 '
            'where taking out the trash is 1.'
        ),
    )
    frequency = models.CharField(
        max_length=10,
        choices=Frequency.choices,
        default=Frequency.WEEKLY,
    )
    estimated_minutes = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text='Optional. Used for surfacing time cost, not for fairness.',
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Inactive chores stop generating new occurrences but keep their history.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['household', 'name'],
                name='unique_chore_name_per_household',
            ),
        ]

    def __str__(self):
        return f'{self.name} ({self.household.name})'


class ChoreOccurrence(models.Model):
    """
    One dated instance of a chore — "the dishes, due Tuesday".

    Separate from Chore so that status, assignment and completion history are
    per-instance. Fairness (T8) sums effort over completed occurrences, which is
    only possible because each instance is its own row.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        DONE = 'done', 'Done'
        OVERDUE = 'overdue', 'Overdue'
        SKIPPED = 'skipped', 'Skipped'

    OPEN_STATUSES = (Status.PENDING, Status.OVERDUE)

    chore = models.ForeignKey(
        Chore,
        on_delete=models.CASCADE,
        related_name='occurrences',
    )
    due_date = models.DateField()
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    assigned_to = models.ForeignKey(
        Member,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_occurrences',
        help_text='Unassigned occurrences are open for anyone to claim.',
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        Member,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_occurrences',
        help_text=(
            'Recorded separately from assigned_to: whoever actually did the work '
            'earns the fairness credit, even if someone else was assigned.'
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['due_date', 'chore__name']
        constraints = [
            models.UniqueConstraint(
                fields=['chore', 'due_date'],
                name='unique_occurrence_per_chore_per_day',
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['assigned_to', 'status']),
        ]

    def __str__(self):
        return f'{self.chore.name} due {self.due_date}'

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def effort_weight(self):
        """Fairness credit this occurrence is worth. Reads through to the chore."""
        return self.chore.effort_weight


class ChorePreference(models.Model):
    """How a member feels about a chore. A soft signal in the T9 recommendation score."""

    class Sentiment(models.IntegerChoices):
        DISLIKES = -1, 'Dislikes'
        NEUTRAL = 0, 'Neutral'
        LIKES = 1, 'Likes'

    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name='preferences',
    )
    chore = models.ForeignKey(
        Chore,
        on_delete=models.CASCADE,
        related_name='preferences',
    )
    sentiment = models.SmallIntegerField(
        choices=Sentiment.choices,
        default=Sentiment.NEUTRAL,
    )

    class Meta:
        ordering = ['member__display_name', 'chore__name']
        constraints = [
            models.UniqueConstraint(
                fields=['member', 'chore'],
                name='unique_preference_per_member_chore',
            ),
        ]

    def __str__(self):
        return f'{self.member.display_name} {self.get_sentiment_display().lower()} {self.chore.name}'


class Availability(models.Model):
    """
    A recurring weekly window in which a member can do chores.

    A member with no availability rows is treated as always available — the
    common case, and it keeps the system usable before anyone fills this in.
    """

    class Weekday(models.IntegerChoices):
        MONDAY = 0, 'Monday'
        TUESDAY = 1, 'Tuesday'
        WEDNESDAY = 2, 'Wednesday'
        THURSDAY = 3, 'Thursday'
        FRIDAY = 4, 'Friday'
        SATURDAY = 5, 'Saturday'
        SUNDAY = 6, 'Sunday'

    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name='availability',
    )
    weekday = models.IntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ['weekday', 'start_time']
        verbose_name_plural = 'availability'
        constraints = [
            models.UniqueConstraint(
                fields=['member', 'weekday', 'start_time'],
                name='unique_availability_slot',
            ),
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F('start_time')),
                name='availability_ends_after_it_starts',
            ),
        ]

    def __str__(self):
        return (
            f'{self.member.display_name} {self.get_weekday_display()} '
            f'{self.start_time:%H:%M}-{self.end_time:%H:%M}'
        )


class MemberSkill(models.Model):
    """
    Whether a member is able to do a chore at all.

    Unlike preference this is a hard filter in T9: a member who cannot safely
    operate the mower is never recommended for mowing, however fair it would be.
    Absence of a row means capable — opt out, not opt in.
    """

    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name='skills',
    )
    chore = models.ForeignKey(
        Chore,
        on_delete=models.CASCADE,
        related_name='skills',
    )
    can_perform = models.BooleanField(default=True)
    note = models.CharField(
        max_length=200,
        blank=True,
        help_text='Optional reason, e.g. "allergic to oven cleaner".',
    )

    class Meta:
        ordering = ['member__display_name', 'chore__name']
        constraints = [
            models.UniqueConstraint(
                fields=['member', 'chore'],
                name='unique_skill_per_member_chore',
            ),
        ]

    def __str__(self):
        verb = 'can' if self.can_perform else 'cannot'
        return f'{self.member.display_name} {verb} {self.chore.name}'


class ChoreTemplate(models.Model):
    """
    A predefined chore households can adopt, with sensible defaults already set.

    Global rather than household-scoped: templates are the shared starting
    library. Adopting one copies its values into a household-owned Chore, so
    later edits to the template never rewrite a household's tuned settings.
    """

    name = models.CharField(max_length=120, unique=True)
    category = models.CharField(
        max_length=20,
        choices=Chore.Category.choices,
        default=Chore.Category.OTHER,
    )
    default_effort_weight = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    default_frequency = models.CharField(
        max_length=10,
        choices=Chore.Frequency.choices,
        default=Chore.Frequency.WEEKLY,
    )
    estimated_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return self.name

    def create_chore_for(self, household, **overrides):
        """Instantiate this template as a real chore owned by `household`."""
        fields = {
            'name': self.name,
            'category': self.category,
            'effort_weight': self.default_effort_weight,
            'frequency': self.default_frequency,
            'estimated_minutes': self.estimated_minutes,
        }
        fields.update(overrides)
        return Chore.objects.create(household=household, **fields)


class EscalationEvent(models.Model):
    """
    A rung of the escalation ladder that has already been climbed for an occurrence.

    Recorded so the ladder never repeats itself. Plan section 5 asks for gentle
    escalation, and nothing feels less gentle than the same reminder four times.
    """

    class Level(models.IntegerChoices):
        REMINDER = 1, 'Advance reminder'
        DUE_TODAY = 2, 'Due today'
        OVERDUE_NOTICE = 3, 'Overdue notice'
        HOUSEHOLD_NUDGE = 4, 'Household nudge'
        REASSIGN_OFFER = 5, 'Offered for reassignment'

    occurrence = models.ForeignKey(
        ChoreOccurrence,
        on_delete=models.CASCADE,
        related_name='escalations',
    )
    level = models.IntegerField(choices=Level.choices)
    sent_at = models.DateTimeField(auto_now_add=True)
    detail = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['occurrence', 'level']
        constraints = [
            models.UniqueConstraint(
                fields=['occurrence', 'level'],
                name='unique_escalation_level_per_occurrence',
            ),
        ]

    def __str__(self):
        return f'{self.get_level_display()} for {self.occurrence}'
