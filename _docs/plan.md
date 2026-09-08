# Shared Household Chores Tool — Scope Plan

## 1. Product Purpose

A smart household chore management tool for **any household type**.

The system helps households:
- Assign chores intelligently
- Distribute workload fairly
- Track completion
- Coordinate chores with minimal conflict

The household size and members are configurable.

---

## 2. Core Product Pillars

1. **Assignment** — determine who should do each chore.
2. **Fairness** — distribute workload fairly.
3. **Tracking** — monitor completed and overdue chores.
4. **Coordination** — help household members coordinate without unnecessary conflict or nagging.

---

## 3. Smart Chore Assignment

The system should **recommend assignments automatically** rather than relying only on manual assignment.

The recommendation engine considers:

- **Workload** — how much each member has already done.
- **Preferences** — chores members like or dislike.
- **Availability** — when members are available.
- **Skill / ability** — whether a member is suitable for a particular chore.

The household can therefore receive intelligent assignment recommendations rather than a simple static rotation.

---

## 4. Fairness Model

Fairness is defined using a **hybrid model**:

- **Weighted effort** — chores have different effort/weight values. For example, vacuuming can count as more effort than taking out the trash.
- **Personal circumstances** — assignments can account for individual availability/capacity.

The goal is not necessarily to give everyone the same number of chores, but to achieve a fair distribution of overall effort.

---

## 5. Missed / Overdue Chores

Use a **gentle escalation loop**:

1. Chore is assigned.
2. Member receives a reminder.
3. If the chore becomes overdue, the system marks it overdue.
4. The system can escalate appropriately rather than immediately reassigning or punishing the member.

The goal is to encourage completion while minimizing household conflict.

---

## 6. Main Screen

Use a **combined household dashboard** containing:

- **Today** — chores that need attention today.
- **My chores** — personalized tasks for the current member.
- **Household health** — overall completion and fairness status.
- **Overdue chores** — tasks requiring attention.

This makes the application a household command center rather than simply a to-do list.

---

## 7. Chore Creation

Use a **hybrid chore creation system**:

### Templates
Provide common predefined chores such as:
- Washing dishes
- Laundry
- Vacuuming
- Taking out trash
- Cleaning bathroom
- Grocery-related household tasks

### Custom chores
Allow households to create their own chores.

A chore can eventually contain attributes such as:
- Name
- Category
- Frequency
- Estimated effort / weight
- Deadline
- Preferred time
- Other assignment-relevant constraints

---

## 8. Household Roles

Use **role-based access control**.

Initial roles:

- **Admin** — manages household-level settings and members.
- **Member** — participates in chores and manages their own relevant tasks.
- **Guest / Child** — optional restricted role for households that need it.

Permissions should depend on the member's role rather than giving everyone identical control.

---

## 9. Optimization Goal

The primary optimization strategy is:

> **Fairness + completion**

The system should balance two objectives:

1. Keep household workload reasonably fair.
2. Maximize the probability that assigned chores actually get completed.

This means the "fairest theoretical assignment" is not always the best assignment if it is unlikely to be completed.

---

# Initial Product Scope

### In scope

- Configurable households
- Multiple household members
- Role-based access
- Chore templates
- Custom chores
- Chore frequency/scheduling
- Effort weighting
- Member preferences
- Member availability
- Skill/ability constraints
- Smart assignment recommendations
- Fairness calculation
- Completion tracking
- Overdue status
- Gentle reminders/escalation
- Combined household dashboard

### Core product idea

**A smart household chore coordinator that continuously recommends fair assignments while considering effort, preferences, availability, and suitability — with the goal of keeping chores both fair and completed.**

---

## Scope Decisions Made

| Decision | Choice |
|---|---|
| Target household | Any household |
| Core problem | Assignment + fairness + tracking + coordination |
| Assignment | Smart assignment |
| Assignment factors | Workload + preferences + availability + skill/ability |
| Fairness | Weighted effort + personal circumstances |
| Missed chores | Gentle escalation |
| Main screen | Combined dashboard |
| Chore creation | Templates + custom |
| Permissions | Role-based |
| Optimization | Fairness + completion |