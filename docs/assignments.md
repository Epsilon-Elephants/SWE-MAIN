# Assignment dates and completions

Assignment documents have `posted` (the first date students can see homework)
and `due_date` (the deadline). Both are BSON dates stored in UTC. Python `date`
values mean midnight UTC; timezone-aware `datetime` values are converted to UTC
and naive datetimes are interpreted as UTC.

`create_assignment(..., class_id=..., posted=..., due_date=...)` defaults to
posted now and no deadline. Dates can be changed with `update_assignment` or
`update_class_assignment` using the same keyword arguments. Omitted update
arguments preserve existing dates; `due_date=None` removes a deadline. A deadline
before the posted date is rejected.

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

The professor create/edit forms require both dates and save assignments as
`published`: the posted date controls when students can first see them. The
professor editor uses these dates instead of a manual status selector. The
student dashboard currently has no submission/grading workflow; completion
helpers are ready to connect to trusted grading code.

## MongoDB validation

In mongosh, select the application database and run
`load("docs/assignment-validation.js")` from the project root. The script creates
missing collections or adds rules alongside existing validators. It validates
date types and ordering, and requires assignment/user references, a nonnegative
numeric score, and a completion date for completion records. Existing assignment
documents may omit dates for compatibility. Validation does not backfill data
or verify referenced users, assignments, or enrollment; the Python helpers
perform those checks. Existing conflicting validators must be updated separately.
