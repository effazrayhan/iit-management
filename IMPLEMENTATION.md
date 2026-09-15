## Updated core model

Your student email format gives you a useful source of structured information:

`bsse1501@iit.du.ac.bd`

can be interpreted as:

```text
bsse   → program
15     → batch
01     → roll
iit.du.ac.bd → required student email domain
```

After successful Google SSO, the backend should validate the email against a strict regex/policy. Don't trust information sent by the frontend.

For example:

```text
^bsse(?P<batch>\d{2})(?P<roll>\d{2})@iit\.du\.ac\.bd$
```

Then:

```text
bsse1501@iit.du.ac.bd
        ↓
Program = BSSE
Batch   = 15
Roll    = 01
```

However, make the parser configurable rather than hard-coding this everywhere. Email conventions can change.

Also, **Google authentication proves control of the Google account; your FastAPI backend must still enforce the permitted domain/email pattern and roles**.

---

# Phase-based implementation plan

I would divide development into **8 phases**. Each phase should leave you with something testable rather than building the whole ERP simultaneously.

### Phase 0 — Requirements, policies and system design

Before coding, freeze the fundamental rules.

Define the four primary roles:

```text
SUPER_ADMIN
DEPARTMENT_ADMIN
TEACHER
STUDENT
```

CR is better represented as a **student responsibility/appointment**, not a completely separate authentication role.

For example:

```text
Student
  └── CRAppointment
        batch_id
        student_id
        start_date
        end_date
        status
```

Also establish policies for complaints, anonymous reviews, CR elections, attendance editing, teacher verification and data visibility.

Create the initial ERD during this phase.

**Deliverable:** ERD + requirements + permission matrix + API conventions.

---

## Phase 1 — FastAPI foundation + Google SSO

This should be your first real development milestone.

Suggested backend:

```text
FastAPI
│
├── PostgreSQL
├── SQLAlchemy 2
├── Alembic
├── Pydantic
├── Redis
└── Google OAuth / OIDC
```

Frontend could be:

```text
Next.js
TypeScript
Tailwind CSS
```

Create a clean FastAPI structure early:

```text
app/
├── main.py
├── core/
│   ├── config.py
│   ├── security.py
│   ├── permissions.py
│   └── exceptions.py
│
├── db/
│   ├── session.py
│   └── base.py
│
├── models/
├── schemas/
├── api/
│   └── v1/
├── services/
├── repositories/
├── dependencies/
├── utils/
└── tests/
```

Don't put business logic directly inside route handlers.

### Student Google SSO flow

```text
Student
   ↓
Continue with Google
   ↓
Google authentication
   ↓
Frontend obtains authentication result
   ↓
FastAPI verifies Google identity/token
   ↓
Extract verified email
   ↓
Validate email format/domain
   ↓
bsse1501@iit.du.ac.bd
   ↓
Parse program/batch/roll
   ↓
Find/Create User
   ↓
Find/Create StudentProfile
   ↓
Issue application session/token
```

For students, accept only the configured pattern/domain.

Teachers need a different policy because their university emails probably won't follow the student roll pattern. I'd use:

```text
Google SSO
    ↓
@iit.du.ac.bd
    ↓
Not student email format?
    ↓
Teacher registration request
    ↓
Department Admin approval
    ↓
Teacher account activated
```

Don't automatically make every non-student `@iit.du.ac.bd` account a teacher.

**Phase 1 result:** secure login/logout, student identification, teacher approval and RBAC.

---

# Phase 2 — Student information + academic master data

Now establish the foundation everything else references.

Student profile:

```text
StudentProfile
├── user_id
├── student_id
├── roll
├── name
├── program
├── session
├── batch_id
├── phone
├── hall_id
├── hometown_district
├── current_address
├── blood_group
├── last_blood_donation
└── profile_completed
```

Because batch and roll come from email, students shouldn't normally be allowed to edit them.

Create master entities for:

```text
Program
AcademicSession
Batch
Semester
Course
Hall
```

For example:

```text
Batch
----------------
id: 15
display_name: 15th Batch
session: 2022-23
program: BSSE
status: ACTIVE
```

Courses should be centrally configured:

```text
Course
----------------
code: SE-301
name: Software Architecture
credits: 3
semester: 5
```

This enables your autofill requirement:

> Teacher chooses `SE-301` → "Software Architecture" appears automatically.

**Phase 2 result:** complete student profiles and reliable departmental master data.

---

# Phase 3 — Batch management + CR system

Now implement the batch-level community structure.

A batch can have **multiple CR positions**, as you requested.

Don't simply put:

```text
batch.cr_id
```

because that limits you.

Instead:

```text
CRPosition
----------------
id
batch_id
title
number_of_seats
```

For example:

```text
15th Batch

CR Position:
General CR
Seats: 2
```

or potentially later:

```text
Male CR
Female CR
Academic CR
Sports CR
```

without changing your architecture.

### CR election

Build a real election entity:

```text
CRElection
├── id
├── batch_id
├── title
├── nomination_start
├── nomination_end
├── voting_start
├── voting_end
├── seats
├── status
└── created_by
```

Then:

```text
CRCandidate
├── election_id
├── student_id
├── manifesto
└── status
```

and:

```text
CRVote
├── election_id
├── voter_id
├── candidate_id
└── created_at
```

Critical database constraint:

```text
UNIQUE(election_id, voter_id)
```

That ensures:

**one student → one vote → per election**

But there is an important privacy decision.

If you want a **secret ballot**, don't design the normal query path so administrators can trivially retrieve:

> Student X voted for Student Y.

Separate voter eligibility/participation from the anonymous ballot where practical.

### Election flow

```text
Admin creates election
        ↓
Nomination opens
        ↓
Eligible students become candidates
        ↓
Nomination closes
        ↓
Candidate list finalized
        ↓
Voting opens
        ↓
Only students from that batch vote
        ↓
Voting closes
        ↓
Votes counted
        ↓
Winner(s) announced
        ↓
CRAppointment created
```

The server controls election opening/closing—not the frontend clock.

**Phase 3 result:** batches have elected CRs with election history rather than manually assigned CR flags.

---

# Phase 4 — Classroom + course management

Now connect teachers, batches and courses.

Teacher:

```text
Create Classroom

Batch:
[15th Batch ▼]

Course:
[SE-301 ▼]

Course Name:
Software Architecture

Semester:
5th

Section:
A
```

Backend creates:

```text
Classroom
├── id
├── course_id
├── batch_id
├── teacher_id
├── semester_id
├── academic_session_id
└── status
```

Students should normally be automatically enrolled based on batch.

Use a separate:

```text
ClassroomEnrollment
```

table anyway because there will eventually be exceptions.

This lets you support retakes, irregular students, electives, withdrawals, etc.

CRs can receive limited classroom capabilities later, such as announcements, but **CR status should never grant teacher permissions**.

**Phase 4 result:** teachers have course classrooms populated with the appropriate students.

---

# Phase 5 — Attendance

Now build attendance on top of classrooms.

Teacher creates a class session:

```text
SE-301
Software Architecture

Date: 15 Sep 2026
Time: 10:00–11:30
Topic: Layered Architecture
```

Then:

```text
Student        Status

Roll 01        Present
Roll 02        Present
Roll 03        Absent
Roll 04        Late
```

Use:

```text
ClassSession
```

and:

```text
AttendanceRecord
```

rather than maintaining an editable percentage.

Calculate:

```text
Attendance % =
attended sessions / applicable sessions × 100
```

You can define exactly how `LATE` and `EXCUSED` contribute through department configuration.

Student dashboard then displays:

```text
Software Architecture

Classes held       24
Present            20
Absent              4
Attendance        83.3%
Status              ✓
```

Keep an audit history when teachers modify historical attendance.

**Phase 5 result:** usable classroom/attendance product.

---

# Phase 6 — Complaints + confidential reviews

At this point, introduce the more sensitive functionality.

### Complaint system

Use categories such as:

```text
Academic
Classroom
Lab
Facilities
Teacher-related
Administration
Harassment/Safety
Other
```

Workflow:

```text
Submitted
   ↓
Acknowledged
   ↓
Under Review
   ↓
Assigned
   ↓
Action Taken
   ↓
Resolved
```

Allow attachments and potentially identified/confidential submission modes.

### Course/teacher feedback

Tie feedback to actual enrollment:

```text
Student
   ↓
ClassroomEnrollment verified
   ↓
Feedback allowed
```

Therefore, a student can't randomly review a teacher whose course they never took.

Structured ratings + comments are preferable to unrestricted criticism.

For example:

```text
Explanation clarity       ★★★★☆
Course organization       ★★★☆☆
Assessment fairness       ★★★★☆
Class regularity          ★★★★★
Student interaction       ★★★★☆

Suggestions:
[.............................]
```

Teachers receive aggregate feedback.

Department administration can receive more detailed analytics depending on your policy, while student identity remains protected according to the anonymity design.

**Phase 6 result:** student voice and departmental accountability system.

---

# Phase 7 — Dashboards, blood-donor utility and notifications

Only now would I invest heavily in dashboards because you'll finally have meaningful data.

### Student

```text
┌ Attendance ──── 82.4% ┐
┌ Courses ─────────── 6 ┐
┌ Complaints ───────── 2 ┐
┌ CR Election ─── OPEN! ┐

Attendance by Course
█████████░ 91% SE-301
████████░░ 82% SE-303
███████░░░ 74% SE-305
```

### Teacher

```text
Active Courses             4
Students                  143
Classes This Month         27
Average Attendance       81.2%
```

### Admin

```text
Students                 650
Teachers                  31
Active Classrooms         42
Average Attendance       79%
Open Complaints           13
Complaint Resolution     84%
Feedback Response Rate   71%
```

You can also implement the blood-donor feature here.

For example, a consenting student could search:

```text
Blood Group: O+
Batch: Any
Available donor: Yes
```

But don't expose everybody's phone number by default. A student should explicitly choose whether their donor/contact information is discoverable.

Notifications can cover:

```text
Attendance warning
Complaint status changed
New classroom
CR nomination opened
CR voting started
Election result
Feedback period opened
Department announcement
```

**Phase 7 result:** the system starts feeling like a unified departmental platform rather than several CRUD applications.

---

# Phase 8 — Hardening + production rollout

This phase is extremely important because you're handling student information, complaints, anonymous feedback and elections.

Add:

**Security:** strict RBAC, rate limiting, CSRF/session protections where applicable, secure cookies/token handling, OAuth validation, file-upload validation, authorization tests and secret management.

**Data:** database backups, migration procedures, retention policies, soft deletion where appropriate and disaster recovery.

**Audit:** teacher approval, attendance edits, complaint administrative actions, course modifications, election creation/closing and permission changes should all be logged.

Also perform load testing and penetration/security testing before department-wide deployment.

Then roll out gradually:

```text
Development
      ↓
Internal testing
      ↓
One batch pilot
      ↓
2–3 batches
      ↓
Teacher pilot
      ↓
Whole IIT
```

I would **not launch elections, complaints, reviews and attendance simultaneously**. Start with profiles/classrooms/attendance, establish trust, then activate the sensitive modules.

---

## Recommended overall architecture

I'd aim for this:

```text
                    ┌──────────────────┐
                    │     Next.js      │
                    │   Web / PWA UI   │
                    └────────┬─────────┘
                             │
                         HTTPS/API
                             │
                    ┌────────▼─────────┐
                    │     FastAPI      │
                    │                  │
                    │ Auth / RBAC      │
                    │ Students         │
                    │ Teachers         │
                    │ Academics        │
                    │ Classrooms       │
                    │ Attendance       │
                    │ Elections        │
                    │ Complaints       │
                    │ Feedback         │
                    │ Analytics        │
                    └─────┬─────┬─────┘
                          │     │
             ┌────────────┘     └────────────┐
             ▼                               ▼
      ┌──────────────┐                ┌─────────────┐
      │ PostgreSQL   │                │    Redis    │
      │ Primary DB   │                │Cache/Queues │
      └──────────────┘                └─────────────┘

              ┌──────────────────────────┐
              │ Google OAuth/OIDC        │
              │ University Authentication│
              └──────────────────────────┘

              ┌──────────────────────────┐
              │ Object Storage           │
              │ Complaint attachments    │
              └──────────────────────────┘
```

I would initially keep FastAPI as a **modular monolith**, not microservices. You don't need separate attendance, election and complaint services at this scale. Good module boundaries inside one backend will be much easier to develop and operate.

### Development priority

If you're developing this yourself or with a small team, the practical order is:

**Foundation → Authentication → RBAC → Academic data → Profiles → CR/elections → Classrooms → Attendance → Complaints → Feedback → Dashboards → Notifications → Security hardening → Pilot.**

Most importantly, design the **database ERD and permission matrix before starting FastAPI endpoints**. With this application, poor data relationships or permissions will become expensive to fix once attendance, elections and anonymous feedback are sitting on top of them.
