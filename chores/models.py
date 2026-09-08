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
