# Assignment dates and completions

For a complete example of what the AI grading input will look like, see
[Problem format and AI integration](ai-grading.md). For navigation and collection
relationships, see [How the application works](architecture.md).

Assignment documents have `posted` (the first date students can see homework)
and `due_date` (the deadline). Both are BSON dates stored in UTC. Python `date`
values mean midnight UTC; timezone-aware `datetime` values are converted to UTC
and naive datetimes are interpreted as UTC.

`create_assignment(..., class_id=..., posted=..., due_date=..., problems=[...])`
requires a nonblank title, both dates, and at least one nonblank problem string
or structured short-answer problem (see below).
Problems are stored with generated IDs as part of the same insert.
Dates can be changed with `update_assignment` or
`update_class_assignment` using the same keyword arguments. Omitted update
arguments preserve existing dates. Missing or cleared dates, empty problem lists,
and a deadline before the posted date are rejected when saving assignments.
The last problem cannot be removed; delete the assignment instead if needed.

`list_assignments_for_student(user_id)` returns published or closed assignments
in the student's enrolled classes once their posted date has arrived. Deadlines
do not hide assignments or prevent completion. Drafts remain hidden. Existing
published/closed assignments without dates remain available without a migration.

`db.completed_assignments.complete_assignment(assignment_id, user_id, score)`
records a completion in the MongoDB `completed_assignments` collection with:

- `assignment_id`: ObjectId referencing the assignment.
- `user_id`: ObjectId referencing the student user.
- `score`: finite, nonnegative numeric points (no fixed percentage scale).
- `completed_at`: server-generated UTC completion datetime.

The student must be enrolled and the assignment must be posted. Repeat calls
create separate completion records, preserving attempt history. Call this from
trusted grading code with a calculated score and the authenticated user's ID.
Use `list_completed_assignments_for_user` or `list_completions_for_assignment`
to retrieve history.

The professor create form includes a required first problem. The create/edit
forms require a title, both dates, and at least one problem and save assignments as
`published`: the posted date controls when students can first see them. The
professor editor uses these dates instead of a manual status selector. Students can open Homework from their dashboard, select an assignment, answer
its questions, and submit. Grading is not connected yet; the scored completion
helpers remain reserved for trusted grading code.

## MongoDB validation

In mongosh, select the application database and run
`load("docs/assignment-validation.js")` from the project root. The script creates
missing collections or adds rules alongside existing validators. It validates
date types and ordering, and requires assignment/user references, a nonnegative
numeric score, and a completion date for completion records. Existing assignment
documents may omit dates for compatibility. Validation does not backfill data
or verify referenced users, assignments, or enrollment; the Python helpers
perform those checks. Existing conflicting validators must be updated separately.


## Short-answer problem format (v1)

`app/homework/schema.py` owns normalization and the future grading payload.
The machine-readable canonical problem schema is
[`homework-problem.schema.json`](homework-problem.schema.json).
New assignments and added/edited problems use this format:

```json
{
  "schema_version": 1,
  "problem_id": "a-stable-generated-uuid",
  "type": "short_answer",
  "content": "Explain why P ∧ Q is true only when both propositions are true.",
  "points": 3.0,
  "topic": "Propositional logic",
  "reference_answer": "A conjunction requires both operands to be true.",
  "grading_guidance": "Award full credit for explaining both operands must be true."
}
```

`content` is the prompt and supports Streamlit Markdown, Unicode, and LaTeX.
`points` must be finite and positive; it defaults to 1. `topic`,
`reference_answer`, and `grading_guidance` default to empty strings. The professor
assignment editor can set these fields for existing and new questions.
Reference answers and grading guidance are private: student pages render only
prompts, points, topics, and the student's own responses. Do not expose whole
problem/snapshot documents in downloads or frontend components.

Legacy `{problem_id, content}` documents are normalized on read/submission with
these defaults, preserving problem IDs. No backfill is required. Existing
string-based authoring calls still work; text-only updates preserve metadata.
A full structured problem can be passed to `create_assignment`, `add_problem`,
or `update_problem`. IDs stay stable when an existing question is edited.

## Ungraded submissions

`db.homework_submissions.submit_homework(assignment_id, user_id, answers)` takes a
mapping from problem ID to short-answer text. The UI passes the authenticated
student ID; the helper checks the student's role, current enrollment, and
assignment visibility again before writing. Blank, missing, extra, and non-text
answers are rejected. Every question requires an answer. Drafts and future
homework cannot be accessed or submitted. Past-due and closed homework remain
available under the existing completion policy.

The MongoDB `homework_submissions` collection stores:

- `schema_version`: 1.
- `assignment_id`, `user_id`, `class_id`: BSON ObjectIds.
- `submitted_at`: server-generated UTC BSON datetime.
- `status`: `submitted`; `grading_status`: `ungraded`.
- `assignment_snapshot`: title, description, posted/due dates, and canonical
  problems including private instructor grading guidance at submission time.
- `answers`: ordered `{problem_id, answer}` objects, with trimmed, nonblank text.

No score, correctness, feedback, completion record, recommendation update, or AI
request is produced. The UI confirms submission, shows the student's saved
answers and submission dates, and marks the homework as awaiting grading.
Repeat submissions create separate attempts; ordinary page reruns do not write.
Students can review their submitted attempts after navigating away or logging in
again. Unsubmitted form entries are not autosaved and can be lost on navigation.
Snapshots keep old submissions gradeable even after a professor edits/deletes an
assignment. Student access to the assignment itself still requires current
visibility and enrollment.

`list_submissions_for_student(user_id, assignment_id=None)` returns that user's
history, newest first. This is a trusted server helper; always supply the
session user's ID in student-facing views.

For the next phase, load a saved submission on the server and call
`build_grading_payload(submission)`. It returns JSON-safe `schema_version`,
`submission_id`, `assignment_id`, `assignment_title`, `assignment_description`,
and `problems`: each canonical problem plus its `student_answer`, matched by ID.
This function is not called by the current submission flow and makes no network
requests. The future grader must treat student answers as untrusted content,
validate model output, and write scores through trusted server code.

The validation script also installs the `homework_submissions` validator and a
nonunique history index on `(user_id, assignment_id, submitted_at)`. Run it manually
against the intended database; application tests never connect to live MongoDB.
The new collection is also created automatically on its first application insert
if the script has not been run.
