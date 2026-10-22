# How the application works

The app runs in Streamlit with MongoDB persistence and a Rocky HTTP client.
There is no separate application API server in this repository: page code calls
Python helpers directly.

## Main modules

| Location | Responsibility |
| --- | --- |
| [`app/app.py`](../app/app.py) | Entry point, initial user state, shared styling, and role-scoped navigation. |
| [`app/pages/home.py`](../app/pages/home.py), [`welcome.py`](../app/pages/welcome.py) | Show login or dispatch to the student's/professor's dashboard. |
| [`app/auth/`](../app/auth) | Registration, password verification, and login rate limiting. |
| [`app/pages/dashboards/`](../app/pages/dashboards) | Role-specific dashboard views, professor class management, and student Rocky dialog. |
| [`app/pages/assignment_editor.py`](../app/pages/assignment_editor.py) | Professor edits to assignment details and questions. |
| [`app/components/problem_editor.py`](../app/components/problem_editor.py) | Prompt editor and instructor grading fields; no database access. |
| [`app/homework/views.py`](../app/homework/views.py) | Student homework list, answer form, and saved-attempt display. |
| [`app/homework/schema.py`](../app/homework/schema.py) | Canonical problem normalization and future AI grading-input builder. |
| [`app/db/DataBase.py`](../app/db/DataBase.py) | Shared lazy MongoDB connection, CRUD, class queries, and enrollment checks. |
| [`app/db/assignments.py`](../app/db/assignments.py) | Assignment ownership, scheduling, visibility, and problem edits. |
| [`app/db/homework_submissions.py`](../app/db/homework_submissions.py) | Authorized homework reads and new ungraded submission records. |
| [`app/db/completed_assignments.py`](../app/db/completed_assignments.py) | Trusted scored completion history, separate from submissions. |
| [`app/rocky/`](../app/rocky) | AI transport and a standalone topic-performance analyzer. |

## User workflow and state

Registration creates a `student` account. Login returns a session user containing
`id`, email, name, and `permissions`. Supported login roles are `student` and
`professor`. Professor access must be provisioned outside public registration.

`app.py` registers the Home page for everyone and explicit Homework/Assignment
pages for students. Professor dashboard sections, including the assignment editor,
are selected within the dashboard using session state. A file in `app/pages/`
does not automatically become a navigable page because the entry point explicitly
configures navigation.

Streamlit reruns scripts after interactions. Session state holds the logged-in
user, selected page/assignment, form widget values, and the Rocky client/answer.
MongoDB holds saved assignments and submitted attempts. Unsubmitted homework
entries are not autosaved. Logging out clears session state; saved database
records remain available after signing in again.

The homework path is:

```text
Professor saves assignment and problems
  → enrolled student opens posted homework
  → student submits a complete problem-ID-to-answer mapping
  → server validates access and saves answers + assignment snapshot
  → student sees saved attempt, awaiting grading
```

AI grading and score persistence are future steps. The student Rocky dialog is
a separate question-and-answer interaction.

## Persistence model

| Collection | Purpose and important relationships |
| --- | --- |
| `users` | Email, names, password hash, creation time, and `permissions`. Login/registration initialize a unique email index. |
| `classes` | Class records; `instructor_id` references the professor's user ObjectId. |
| `students` | Enrollment rows linking `user_id` and `class_id`; new enrollments initialize `grade: {earned: 0.0, possible: 0.0}`. |
| `assignments` | Title, description, status, UTC dates, `class_id`, `professor_id`, and embedded `problems`. |
| `homework_submissions` | A new ungraded record for each submit, including answers and the assignment snapshot. |
| `completed_assignments` | Separate scored attempts with `assignment_id`, `user_id`, total `score`, and `completed_at`. |
| `rate_limits` | Fixed-window login counters identified by action, normalized email, and window start. |

Most references use BSON ObjectIds. Assignment `professor_id` is stored as the
string supplied by the application, whereas class `instructor_id` is an ObjectId.
The session user's `id` is also a string. Preserve these distinctions in queries.
Problem IDs are strings embedded inside assignments, not separate MongoDB IDs.

`app/db/models.py` describes `Question` and `Attempt` TypedDicts for analytics;
these are not the embedded homework problem/submission schema and are not runtime
database validators. `analyze_student_weaknesses(attempts, questions)` joins
`Attempt.question_id` to `Question._id`, groups boolean correctness by topic, and
sorts ascending accuracy, breaking ties by descending attempt count. Unknown or
missing topics are skipped. It is not wired to homework grading, and
`app/rocky/recommendation.py` is currently empty.

## Access and scheduling rules

- Professor assignment mutations are scoped by assignment owner; creation also checks that the professor teaches the selected class.
- The professor enrollment flow checks the actor's database role and class ownership before adding an existing student. It does not require student approval.
- Homework detail reads and submissions check the student database role, enrollment, and current assignment visibility on the server.
- Visible homework has `published` or `closed` status and a reached posted date. Legacy published/closed records with no posted date remain visible.
- Due dates and `closed` status do not block late or repeat submissions under current policy. Drafts and future assignments stay hidden.
- Instructor reference answers and rubrics stay out of student rendering, although they are stored in assignment and submission documents.

Not every low-level helper independently authorizes the caller. For example,
`get_assignment` reads by ID and `list_submissions_for_student` filters by the
supplied user ID. Callers must pass the authenticated identity and enforce the
appropriate access checks. Student-facing UI must render selected public fields
rather than complete database documents.

Passwords use salted `scrypt` and constant-time hash comparison. Login allows five
attempts per email per fixed 15-minute window; successful login deletes a matching
rate-limit record. See [`app/auth/`](../app/auth) for the implementation.

For exact date and history contracts, see [Assignments and submissions](assignments.md).
