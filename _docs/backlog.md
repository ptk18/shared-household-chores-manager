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

### T2. Assignment + occurrence model — `TODO`
Separates "the chore" (recurring definition) from "this week's instance".

- `ChoreOccurrence` — FK `Chore`, `due_date`, `status` (pending / done / overdue / skipped), `assigned_to` (FK `Member`, nullable), `completed_at`, `completed_by`.

**Files:** `chores/models.py`, migration.
**Done when:** a `Chore` can generate occurrences and each carries its own status independently.
**Why it matters:** completion history and fairness both read from occurrences. Collapsing this into `Chore` makes fairness uncomputable later.

### T3. Django admin registration — `TODO`
Cheapest possible data-entry UI, so later tasks have real data to work against.

**Files:** `chores/admin.py`.
**Done when:** all four models are CRUD-able at `/admin/` with sensible `list_display` and filters.

---

## Phase 2 — Preferences and constraints

### T4. Member preferences, availability, skills — `TODO`
The inputs the recommendation engine needs.

- `ChorePreference` — Member × Chore, `sentiment` (likes / neutral / dislikes).
- `Availability` — Member, weekday, time window.
- `MemberSkill` — Member × Chore (or category), `can_perform` boolean.

**Files:** `chores/models.py`, `chores/admin.py`, migration.
**Done when:** each is editable inline from the `Member` admin page.

### T5. Chore templates + seed command — `TODO`
The predefined chores from plan §7 (dishes, laundry, vacuuming, trash, bathroom, groceries) with default effort weights.

**Files:** `chores/models.py` (`ChoreTemplate`), `chores/management/commands/seed_templates.py`.
**Done when:** `manage.py seed_templates` is idempotent and a household can instantiate a template into a real `Chore`.

---

## Phase 3 — Scheduling and tracking

### T6. Occurrence generation — `TODO`
Turn recurring `Chore.frequency` into dated `ChoreOccurrence` rows for a horizon (e.g. next 14 days).

**Files:** `chores/services/scheduling.py`, `chores/management/commands/generate_occurrences.py`.
**Done when:** running twice does not duplicate occurrences; unit tests cover daily / weekly / monthly.

### T7. Completion + overdue marking — `TODO`
Mark done (stamping `completed_at` / `completed_by`), and a sweep that flips past-due pending occurrences to overdue.

**Files:** `chores/services/tracking.py`, `chores/management/commands/mark_overdue.py`, tests.
**Done when:** tests cover the boundary — an occurrence due today is not yet overdue; due yesterday is.

---

## Phase 4 — The smart parts

### T8. Fairness scoring — `TODO`
Per-member effort score over a rolling window: sum of `effort_weight` for completed occurrences, normalized by the member's declared capacity.

**Files:** `chores/services/fairness.py`, tests.
**Done when:** given a fixture household, the function returns a per-member score and an imbalance measure. Test the degenerate cases: one member, zero completions, equal load.

### T9. Assignment recommendation engine — `TODO`
Score each (member, occurrence) candidate on the four plan §3 factors — current workload, preference, availability, skill — and return a ranked suggestion. Start with a transparent weighted-sum; hard-filter on skill and availability.

**Files:** `chores/services/assignment.py`, tests.
**Done when:** recommendations are explainable (each carries a per-factor breakdown) and tests pin the ordering for a fixture household.
**Scope guard:** no optimizer or solver yet. A readable weighted score you can debug beats an optimal one you can't.

---

## Phase 5 — Interface

### T10. Dashboard view — `TODO`
The plan §6 combined screen: Today · My chores · Household health · Overdue.

**Files:** `chores/views.py`, `chores/urls.py`, `household/urls.py`, `chores/templates/chores/dashboard.html`.
**Done when:** the four sections render for a logged-in member against seeded data.

### T11. Auth + role-based permissions — `TODO`
Login/logout, and enforce plan §8 roles: admin manages household and members; member manages own chores; guest is read-mostly.

**Files:** `chores/permissions.py`, view decorators/mixins, `household/settings.py` (`LOGIN_URL`), tests.
**Done when:** a member cannot edit household settings and cannot complete another member's chore; tests assert both denials.

### T12. Complete/claim actions — `TODO`
POST endpoints to mark an occurrence done and to claim an unassigned one, wired into the dashboard.

**Files:** `chores/views.py`, `chores/urls.py`, templates.
**Done when:** the dashboard round-trips a completion and the fairness numbers move.

---

## Phase 6 — Coordination

### T13. Gentle escalation — `TODO`
Plan §5 loop: reminder before due → overdue mark → escalation (notify household, offer reassignment) rather than auto-punish.

**Files:** `chores/services/escalation.py`, `chores/management/commands/run_reminders.py`, tests.
**Done when:** the escalation ladder is driven by explicit state transitions and tests cover each rung. Delivery starts as console/email backend — no push infrastructure in this pass.

---

## Deliberately not in this backlog

- Mobile app / API layer (DRF) — add only once the web flow is proven.
- Real-time notifications, calendar sync, gamification.
- Multi-household users.
- Anything requiring a solver library for assignment (see T9 scope guard).
