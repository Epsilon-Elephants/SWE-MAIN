# How the application works

The app runs in Streamlit with MongoDB persistence and a Rocky HTTP client.
There is no separate application API server in this repository: page code calls
Python helpers directly.

## Course workflow

The interface follows the course-card and course-navigation organization of
[Canvas's dashboard](https://community.instructure.com/en/kb/articles/664620-how-do-i-use-the-dashboard)
and [course home](https://community.instructure.com/en/kb/articles/661274-how-do-i-use-the-course-home-page-as-a-student).
The global sidebar contains Dashboard, Courses, Assignments, and Account (plus
student Practice). Creation/editing and individual course pages are registered
hidden routes, reached from their course or assignment.

Dashboards emphasize course cards with a narrow To do panel rather than stacking
metrics, assignment descriptions, rosters, and grades together. Each course has
Assignments and Grades, with People for professors. Current database role and
class ownership/enrollment are checked before course data is read. Students see
only their own course submissions; professors can open grading review from the
course grade list. Existing manually recorded class grades appear in student
course Grades and remain separate from AI assignment scores.

Assignment hubs use searchable rows and a selected group rather than listing
every group at once. The professor editor selects one question at a time;
optional partial-credit criteria are collapsed. Submission review has one row
per attempt and one grading popup, without a duplicate summary table. Student
submission details select one attempt. Lists remain bounded to five entries
with overflow popups. Course helpers live in `app/courses/views.py`, outside the
legacy `pages/` directory, to avoid page-name collisions on refresh.

## Main modules

| Location | Responsibility |
| --- | --- |
| [`app/app.py`](../app/app.py) | Entry point, initial user state, shared styling, and role-scoped navigation. |
| [`.streamlit/config.toml`](../.streamlit/config.toml) | Academic theme, built-in fonts, and sidebar palette. |
| [`app/app_pages/`](../app/app_pages/) | Overview, homework, professor creation/editing, classes, practice status, and account routes. |
| [`app/app_pages/overview.py`](../app/app_pages/overview.py), [`welcome.py`](../app/pages/welcome.py) | Show login or dispatch to the student's/professor's dashboard. |
| [`app/auth/`](../app/auth) | Registration, password verification, and login rate limiting. |
| [`app/pages/dashboards/`](../app/pages/dashboards) | Role-specific dashboard views, professor class management, and student Rocky dialog. |
| [`app/pages/assignment_editor.py`](../app/pages/assignment_editor.py) | Professor edits to assignment details and questions. |
| [`app/components/problem_editor.py`](../app/components/problem_editor.py) | Prompt editor and instructor grading fields; no database access. |
| [`app/homework/views.py`](../app/homework/views.py) | Student homework list, answer form, and saved-attempt display. |
| [`app/homework/schema.py`](../app/homework/schema.py) | Canonical problem normalization and private AI grading-input builder. |
| [`app/db/DataBase.py`](../app/db/DataBase.py) | Shared lazy MongoDB connection, CRUD, class queries, and enrollment checks. |
| [`app/db/assignments.py`](../app/db/assignments.py) | Assignment ownership, scheduling, visibility, and problem edits. |
| [`app/db/homework_submissions.py`](../app/db/homework_submissions.py) | Authorized homework reads, saved attempts, and professor submission queries. |
| [`app/db/student_dashboard.py`](../app/db/student_dashboard.py) | Real student enrollment, manual class grades, coursework, and submission metrics. |
| [`app/db/completed_assignments.py`](../app/db/completed_assignments.py) | Trusted scored completion history, separate from submissions. |
| [`app/rocky/`](../app/rocky) | AI transport, grading contract, performance analysis, and recommendation backend. |

## User workflow and state

Registration creates a `student` account. Login returns a session user containing
`id`, email, name, and `permissions`. Supported login roles are `student` and
`professor`. Professor access must be provisioned outside public registration.

`app.py` registers the overview for everyone and shows a role-scoped sidebar.
Professors have separate classes, creation, and editing pages; students have
separate homework-list, assignment-taking, and practice-status pages. Both roles
have an account page. Contextual editing/taking routes are hidden from the menu
but registered for `st.switch_page`. All route entry scripts live in
`app/app_pages/`, separate from the helpers in `app/pages/`. A file in `app/pages/` does not
automatically become navigable because the entry point explicitly configures
navigation. Selection IDs remain in session state; refreshing in a new session
does not restore a selected assignment.

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
  → server claims the attempt and Rocky compares answers with professor references
  → server validates every problem score and saves points, feedback, and percentage
  → student and professor see the saved AI result (or a retryable grading state)
```

`app/homework/grading.py` manages authorization, leases, and conditional result
writes; `app/rocky/grading.py` owns the model prompt and output validation.
Answers are saved before the model call. Missing references block grading;
service/validation failures preserve answers without assigning a zero. The
student Rocky dialog remains a separate question-and-answer interaction.

`app/homework/worker.py` processes saved attempts independently of student
sessions, with leases and automatic retry scheduling. Grading also produces a
bounded practice suggestion per problem; `app/homework/study.py` supplies fallback
guidance and builds topic-based overview recommendations from published grades.
`app/homework/grades.py` chooses the professor override when present, preserving
the original AI result. Professor review and overrides use an authorized dialog
and revision checks.

Rocky grades remain tentative until a professor accepts them or saves an
override. `professor_grade` stores that confirmed score, including whether its
source is Rocky or a professor edit. `course_score_summary` groups attempts by
assignment and uses the latest professor decision, or otherwise the newest
graded AI attempt. An assignment with a confirmed score cannot also contribute
tentative points. The student course header refreshes its aggregate score bar
every five seconds after rechecking current role and enrollment. Only point
totals reach the chart; answers and grading references stay server-side.

`app/components/compact_list.py` renders five entries plus a See more popup with
five entries per page. Navigation actions close the list popup before opening a
different view/dialog. Professor class and roster browsers also use pages of five,
with database paging for people. `.streamlit/config.toml` provides selectable
light/dark variants through Streamlit's native settings. Sidebar logout clears
all user session state; the Account page has no separate logout action.

Professor counts and the editor's submission viewer read `homework_submissions`,
including ungraded work. Submission detail reads verify the assignment owner and
current class instructor. The older `completed_assignments` helpers are retained
for compatibility but no longer supply these UI counts. Student dashboards show
manual class grades from enrollment records; these are not calculated homework
averages. Public-web resource searches run only on explicit form submission.

Each professor class has one **Open roster** button. Its dialog shows a searchable,
paginated roster with class grades, grade editing, and confirmed student removal;
**Add students** switches to the enrollment view in the same dialog. Every
enrollment, removal, and grade write checks that the acting user is the class's
current professor. Manual grades update the enrollment's `grade.earned` and
`grade.possible` values; they do not grade individual homework submissions.

## Persistence model

| Collection | Purpose and important relationships |
| --- | --- |
| `users` | Email, names, password hash, creation time, and `permissions`. Login/registration initialize a unique email index. |
| `classes` | Class records; `instructor_id` references the professor's user ObjectId. |
| `students` | Enrollment rows linking `user_id` and `class_id`; new enrollments initialize `grade: {earned: 0.0, possible: 0.0}`. |
| `assignments` | Title, description, status, UTC dates, `class_id`, `professor_id`, and embedded `problems`. |
| `homework_submissions` | A separate attempt per submit, with immutable answers/snapshot, grading state, and validated problem scores/feedback. |
| `completed_assignments` | Separate scored attempts with `assignment_id`, `user_id`, total `score`, and `completed_at`. |
| `rate_limits` | Fixed-window login counters identified by action, normalized email, and window start. |

Most references use BSON ObjectIds. Assignment `professor_id` is stored as the
string supplied by the application, whereas class `instructor_id` is an ObjectId.
The session user's `id` is also a string. Preserve these distinctions in queries.
Problem IDs are strings embedded inside assignments, not separate MongoDB IDs.

`app/db/models.py` describes `Question` and `Attempt` TypedDicts for analytics;
these are not the embedded homework problem/submission schema and are not runtime
database validators. `analyze_student_weaknesses(attempts, questions)` joins
`Attempt.question_id` to `Question._id` and groups actual boolean question grades
or numeric assignment accuracy by topic. Both student and class analyzers retain
full precision for ranking and threshold comparisons; prompts round only for
display. Unknown topics and attempts without valid performance data are skipped.

`app/rocky/data_adapter.py` reads scored `completed_assignments`. It divides each
completion's points by the assignment total, or by summed problem points (one
point by default, including legacy text problems). Each completion is one numeric
observation with an assignment-scoped ID. It does not infer per-problem grades
from the total. Mixed-topic assignments retain an assignment-specific category
rather than claiming mastery of individual topics. Records with no reliable
points denominator are excluded.

`app/rocky/recommendation.py` builds student and class guidance using these
analytics, validates Rocky's topic/reason fields, and falls back to known weak
topics when the response is unusable. Empty histories return insufficient data
without calling Rocky. Convenience calls own their engine/client, and reused
engines serialize the complete payload transaction. The adapters also read actual problem scores from graded homework, preserving
partial credit and snapshot topics. Homework grading is wired to submit/retry and
the student/professor views. The student overview shows topic practice suggestions
from its latest graded attempts; the broader recommendation engine remains a
separate backend. Callers must enforce the access rules below before requesting database reports.

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
