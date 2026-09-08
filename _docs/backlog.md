# Backlog — Shared Household Chores Manager

Derived from `_docs/plan.md`. Ordered by dependency: each task assumes the ones above it.
Every task is sized to be completable and verifiable on its own.

**Status legend:** `TODO` · `WIP` · `DONE`

---

## Phase 0 — Foundation

### T0. Project scaffold — `DONE`
Django 6.1 project `household`, app `chores`, venv, pinned `requirements.txt`.

**Done when:** `manage.py check` clean, `migrate` applies, dev server returns 200. ✅

---

## Phase 1 — Domain model

### T1. Core models: Household, Member, Chore — `DONE`
The three nouns everything else hangs off.

- `Household` — name, created_at.
- `Member` — FK to `Household`, OneToOne to `auth.User`, `role` choices (`admin` / `member` / `guest`), display name.
- `Chore` — FK to `Household`, name, category, `effort_weight` (small int, the fairness currency), `frequency` (choices: once / daily / weekly / monthly), `estimated_minutes`, active flag.

**Files:** `chores/models.py`, migration.
**Done when:** migrations apply; objects creatable in `manage.py shell`. ✅ (`chores/migrations/0001_initial.py`, 10 model tests in `chores/tests.py`)
**Note:** use a `Member` profile rather than a custom `AUTH_USER_MODEL` — households are many-to-one over users conceptually, and swapping the user model later is far more painful than adding a profile now.

### T2. Assignment + occurrence model — `DONE`
Separates "the chore" (recurring definition) from "this week's instance".

- `ChoreOccurrence` — FK `Chore`, `due_date`, `status` (pending / done / overdue / skipped), `assigned_to` (FK `Member`, nullable), `completed_at`, `completed_by`.

**Files:** `chores/models.py`, migration.
**Done when:** a `Chore` can generate occurrences and each carries its own status independently.
**Why it matters:** completion history and fairness both read from occurrences. Collapsing this into `Chore` makes fairness uncomputable later.

**Shipped:** `ChoreOccurrence` with a unique `(chore, due_date)` constraint — the constraint is what makes T6 regeneration idempotent. `completed_by` is recorded separately from `assigned_to` so credit follows whoever did the work.
### T3. Django admin registration — `DONE`
Cheapest possible data-entry UI, so later tasks have real data to work against.

**Files:** `chores/admin.py`.
**Done when:** all four models are CRUD-able at `/admin/` with sensible `list_display` and filters.

**Shipped:** all models registered, with preference/availability/skill as inlines on `Member` and `EscalationEvent` read-only.
---

## Phase 2 — Preferences and constraints

### T4. Member preferences, availability, skills — `DONE`
The inputs the recommendation engine needs.

- `ChorePreference` — Member × Chore, `sentiment` (likes / neutral / dislikes).
- `Availability` — Member, weekday, time window.
- `MemberSkill` — Member × Chore (or category), `can_perform` boolean.

**Files:** `chores/models.py`, `chores/admin.py`, migration.
**Done when:** each is editable inline from the `Member` admin page.

**Shipped:** absence of a row means *capable* and *available* — opt-out, not opt-in, so the system is usable before anyone fills these in.
### T5. Chore templates + seed command — `DONE`
The predefined chores from plan §7 (dishes, laundry, vacuuming, trash, bathroom, groceries) with default effort weights.

**Files:** `chores/models.py` (`ChoreTemplate`), `chores/management/commands/seed_templates.py`.
**Done when:** `manage.py seed_templates` is idempotent and a household can instantiate a template into a real `Chore`.

**Shipped:** 8 templates; `ChoreTemplate.create_chore_for()` copies values into a household-owned `Chore` so later template edits never rewrite tuned settings.
---

## Phase 3 — Scheduling and tracking

### T6. Occurrence generation — `DONE`
Turn recurring `Chore.frequency` into dated `ChoreOccurrence` rows for a horizon (e.g. next 14 days).

**Files:** `chores/services/scheduling.py`, `chores/management/commands/generate_occurrences.py`.
**Done when:** running twice does not duplicate occurrences; unit tests cover daily / weekly / monthly.

**Shipped:** monthly anchors clamp to short months (31st → 28th in February) rather than skipping. One-off chores never regenerate once they have an occurrence.
### T7. Completion + overdue marking — `DONE`
Mark done (stamping `completed_at` / `completed_by`), and a sweep that flips past-due pending occurrences to overdue.

**Files:** `chores/services/tracking.py`, `chores/management/commands/mark_overdue.py`, tests.
**Done when:** tests cover the boundary — an occurrence due today is not yet overdue; due yesterday is.

**Shipped:** `complete` / `claim` / `skip` / `mark_overdue`, each refusing illegal transitions via `TransitionError`. Due today is not overdue; due yesterday is.
---

## Phase 4 — The smart parts

### T8. Fairness scoring — `DONE`
Per-member effort score over a rolling window: sum of `effort_weight` for completed occurrences, normalized by the member's declared capacity.

**Files:** `chores/services/fairness.py`, tests.
**Done when:** given a fixture household, the function returns a per-member score and an imbalance measure. Test the degenerate cases: one member, zero completions, equal load.

**Shipped:** imbalance is half the sum of absolute deviations — the fraction of effort that would have to change hands to square up. An idle household scores 0.0 (fair), not unfair.
### T9. Assignment recommendation engine — `DONE`
Score each (member, occurrence) candidate on the four plan §3 factors — current workload, preference, availability, skill — and return a ranked suggestion. Start with a transparent weighted-sum; hard-filter on skill and availability.

**Files:** `chores/services/assignment.py`, tests.
**Done when:** recommendations are explainable (each carries a per-factor breakdown) and tests pin the ordering for a fixture household.
**Scope guard:** no optimizer or solver yet. A readable weighted score you can debug beats an optimal one you can't.

**Shipped:** transparent weighted sum (workload .40, preference .25, availability .25, suitability .10) with a per-factor breakdown surfaced in the UI. Skill is a hard gate. Workload counts outstanding assigned effort, not just completed — see the defect note below.
---

## Phase 5 — Interface

### T10. Dashboard view — `DONE`
The plan §6 combined screen: Today · My chores · Household health · Overdue.

**Files:** `chores/views.py`, `chores/urls.py`, `household/urls.py`, `chores/templates/chores/dashboard.html`.
**Done when:** the four sections render for a logged-in member against seeded data.

**Shipped:** four sections plus an *Up for grabs* panel, and a per-occurrence detail page showing the ranked suggestions with their factor breakdown.
### T11. Auth + role-based permissions — `DONE`
Login/logout, and enforce plan §8 roles: admin manages household and members; member manages own chores; guest is read-mostly.

**Files:** `chores/permissions.py`, view decorators/mixins, `household/settings.py` (`LOGIN_URL`), tests.
**Done when:** a member cannot edit household settings and cannot complete another member's chore; tests assert both denials.

**Shipped:** `member_required` / `admin_required` decorators; policy lives in `chores/permissions.py`, separate from the service-layer mechanism.
### T12. Complete/claim actions — `DONE`
POST endpoints to mark an occurrence done and to claim an unassigned one, wired into the dashboard.

**Files:** `chores/views.py`, `chores/urls.py`, templates.
**Done when:** the dashboard round-trips a completion and the fairness numbers move.

**Shipped:** POST-only, CSRF-protected, scoped to the caller's household (cross-household access 404s).
---

## Phase 6 — Coordination

### T13. Gentle escalation — `DONE`
Plan §5 loop: reminder before due → overdue mark → escalation (notify household, offer reassignment) rather than auto-punish.

**Files:** `chores/services/escalation.py`, `chores/management/commands/run_reminders.py`, tests.
**Done when:** the escalation ladder is driven by explicit state transitions and tests cover each rung. Delivery starts as console/email backend — no push infrastructure in this pass.

**Shipped:** five rungs, each firing at most once per occurrence. The ladder only ever *informs* or *releases* a chore back to the household — it never reassigns punitively, marks work against a member, or touches fairness credit.

---

## Defect found and fixed during implementation

**Batch auto-assignment stacked the whole rota on one member.** `_workload_scores`
originally read only *completed* effort, so assignments made moments earlier were
invisible to the next decision. Assigning a fortnight of chores in one pass gave
every one of them to whoever sorted first alphabetically — an end-to-end run
produced a 25 / 0 / 0 split across three members.

Fixed by counting outstanding assigned effort alongside completed effort
(`fairness.outstanding_effort`). The same run now produces 20 / 21 / 20.
Regression-tested in `BatchAssignmentTests`.

This is worth recording because unit tests did not catch it: every single
assignment was individually correct. Only running the pipeline end-to-end
exposed it.

---

## Running it

```
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_templates
.venv/bin/python manage.py seed_demo      # demo household, password demo1234
.venv/bin/python manage.py runserver
```

Scheduled jobs (cron or equivalent):

```
manage.py generate_occurrences   # daily — fill the horizon
manage.py mark_overdue           # daily — flip past-due to overdue
manage.py run_reminders          # daily — advance the escalation ladder
```

---

## Deliberately not in this backlog

- Mobile app / API layer (DRF) — add only once the web flow is proven.
- Real-time notifications, calendar sync, gamification.
- Multi-household users.
- Anything requiring a solver library for assignment (see T9 scope guard).
