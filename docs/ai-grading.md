# Problem format and AI integration

The app grades short-answer homework with Kent State Rocky using the professor's
reference answer and optional partial-credit rubric. Grades are stored on each
saved submission and shown to students and professors.

## What happens on submit

1. The server checks the student's role, enrollment, assignment visibility, and exact answer IDs.
2. Answers and a canonical assignment snapshot are saved before contacting Rocky.
3. The grader claims that saved attempt with a ten-minute lease, builds its private grading input, and sends one request to Rocky.
4. The server validates exactly one result per problem, finite points between zero and the saved maximum, and nonblank feedback. It calculates totals and a 0–100 percentage itself.
5. The same submission becomes `graded`, with per-problem points, feedback, model, and grading time. There is no second completion record to duplicate during retries.

Students see AI scores and feedback in their submitted-attempt history. Professors
see actual homework attempts in the assignment editor, including answers, scores,
feedback, and a grading/retry button. Normal page reruns do not call the model.

## Canonical problem document

```json
{
  "schema_version": 1,
  "problem_id": "d9dd92ef-0b68-4ca8-a409-cf55ce92c73c",
  "type": "short_answer",
  "content": "Explain why P ∧ Q is true only when both propositions are true.",
  "points": 3.0,
  "topic": "Propositional logic",
  "reference_answer": "A conjunction is true exactly when both operands are true.",
  "grading_guidance": "Award 1 point for identifying conjunction and 2 points for explaining that both operands must be true."
}
```

| Field | Meaning and rules | Student-visible? |
| --- | --- | --- |
| `schema_version` | Integer `1`; other versions are rejected. | Not rendered |
| `problem_id` | Stable, nonblank string; generated as a UUID if omitted. Unique within the assignment. | Used internally to match answers |
| `type` | Only `short_answer` is supported. | Not rendered |
| `content` | Required, nonblank prompt. Supports Markdown, Unicode symbols, and LaTeX. | Yes |
| `points` | Finite positive number, excluding booleans; defaults to `1.0`. | Yes |
| `topic` | Text used to label the subject; defaults to `""`. | Yes |
| `reference_answer` | Private model answer; defaults to `""`. | No |
| `grading_guidance` | Private rubric and partial-credit instructions; defaults to `""`. | No |

The [JSON Schema](homework-problem.schema.json) describes the complete canonical
document. Python's `normalize_problem` also accepts authoring shorthand, fills in
defaults, strips surrounding whitespace from text fields other than the ID, and
returns only canonical fields. It does not execute a JSON Schema validator.
`normalize_problems` additionally rejects empty lists and duplicate IDs.

Older plain strings and `{problem_id, content}` documents still work. Existing
IDs are preserved, including when a professor edits a question. A text-only
`update_problem` preserves existing metadata. A structured edit is normalized as
the replacement canonical document, so omitted optional fields return to defaults;
include metadata you want to keep. The existing problem ID is always preserved.

For authoring, keep the student task in `content`, an example of a correct answer
in `reference_answer`, and scoring criteria in `grading_guidance`. Use consistent
topic names if results will later be grouped by topic. Empty reference answers
are allowed for authoring, but block grading until the professor supplies them.
Rubrics are optional.

LaTeX stays text in storage and in the AI input. JSON requires backslashes to be
escaped: a prompt containing `$P \land Q$` is written as `"$P \\land Q$"` in JSON.
The editor accepts the ordinary single-backslash form.

## From student answers to saved submission

The UI calls `submit_homework(assignment_id, session_user_id, answers)` with a
mapping keyed by problem ID:

```json
{
  "d9dd92ef-0b68-4ca8-a409-cf55ce92c73c": "Both propositions have to be true for their conjunction to be true."
}
```

Every current problem must have exactly one nonblank text answer. Missing or extra
IDs and non-text answers are rejected. The server checks the student's role,
current enrollment, and assignment visibility, then saves:

- Submission version, assignment/user/class ObjectIds, and a server-generated UTC timestamp.
- `status: "submitted"` and `grading_status: "ungraded"`.
- An `assignment_snapshot` containing title, description, dates, and canonical problems, including private grading fields.
- An ordered `answers` list of `{problem_id, answer}` objects with trimmed text.

Each submit creates a new attempt. The snapshot preserves the grading context if
the live assignment is edited or deleted. Build grading input from that
saved snapshot rather than rereading the latest assignment's questions.

## Exact grading input

For the example above, `build_grading_payload` returns this shape:

```json
{
  "schema_version": 1,
  "submission_id": "507f1f77bcf86cd799439011",
  "assignment_id": "507f1f77bcf86cd799439012",
  "assignment_title": "Logic homework 1",
  "assignment_description": "Explain your reasoning.",
  "problems": [
    {
      "schema_version": 1,
      "problem_id": "d9dd92ef-0b68-4ca8-a409-cf55ce92c73c",
      "type": "short_answer",
      "content": "Explain why P ∧ Q is true only when both propositions are true.",
      "points": 3.0,
      "topic": "Propositional logic",
      "reference_answer": "A conjunction is true exactly when both operands are true.",
      "grading_guidance": "Award 1 point for identifying conjunction and 2 points for explaining that both operands must be true.",
      "student_answer": "Both propositions have to be true for their conjunction to be true."
    }
  ]
}
```

MongoDB IDs become strings. User ID, class ID, submission timestamp, and assignment
dates are omitted. Problems retain snapshot order; answers are matched by ID,
not by position. The result can be serialized with `json.dumps(payload,
ensure_ascii=False)` to preserve readable logic symbols.

The builder expects a trusted, saved submission with `_id`, a supported version,
canonical snapshot problems, and matching answers. It is not a general validator
for arbitrary external documents. The payload contains private instructor data
and belongs in server-side grading code, not a student download or chat widget.

## Rocky transport already available

[`app/rocky/rocky.py`](../app/rocky/rocky.py) implements the `rocky` client:

1. Construction reads `ROCKY_KEY` from the environment, falling back to Streamlit secrets.
2. An authenticated GET to `https://rocky.cs.kent.edu/v1/models` selects the first returned model ID (30-second timeout).
3. `make_payload(inpt, max_tokens=300, store=False, stream=False)` prepares a request.
4. `send_payload()` consumes that prepared request and POSTs it to `https://rocky.cs.kent.edu/v1/responses` (390-second timeout).

The HTTP body has `model`, `input` (a string), `max_output_tokens`, `store`, and
`stream`. This transport body wraps the prompt; it is distinct from the structured
homework payload above. The grading service wraps the structured payload in the instructions in
`app/rocky/grading.py`. It requests JSON results and validates them before saving.

Without streaming, the client returns the response's `output_text`. With
`stream=True`, it returns a lazy iterator over SSE text deltas. Consume or close
the iterator to release the connection; failures can occur during iteration.
The dashboard streams the answer and retains a completed answer in session state.
It sends a single question per request, without conversation history.

The client itself does not load `.env`; its dashboard caller does. Standalone
scripts must load configuration before constructing a client. Each send requires
a fresh `make_payload` call because sending clears the prepared payload.

## Validated output and storage

Rocky must return the following versioned shape; the order may differ from the
questions, because the server matches results by ID:

```json
{
  "schema_version": 1,
  "results": [
    {"problem_id": "d9dd92ef-0b68-4ca8-a409-cf55ce92c73c", "points_awarded": 2.0,
     "feedback": "Explain how both operands affect the truth value."}
  ]
}
```

Unknown, duplicate, or missing IDs; booleans/string scores; NaN/infinity; scores
outside each problem's maximum; and missing/oversized feedback reject the whole
response. Partial results never become a grade. Model-provided totals, maxima,
or percentages are ignored. Points support fractional partial credit.

The saved `grading_result` includes `schema_version`, `problems` (each with
`problem_id`, `points_awarded`, `max_points`, `feedback`), `total_points`,
`max_points`, a two-decimal `percentage`, `model`, and UTC `graded_at`.
`grading_context` privately records the exact references/rubrics used. Student
widgets render selected score/feedback fields, never the private context,
snapshot references, raw response, prompt, or transport errors.

## Failures, missing references, and retries

| State | Meaning |
| --- | --- |
| `ungraded` | Saved, with no grading attempt yet (including legacy submissions). |
| `grading` | A worker holds a ten-minute lease. An expired lease can be reclaimed. |
| `graded` | A complete, validated result is persisted. Clicking again does not grade twice. |
| `failed` | Service failure or invalid response/input; answers remain saved, with no fabricated zero. |
| `blocked` | At least one professor reference is missing; no model request is made. |

Students can retry their own submissions while still enrolled. Professors can
grade submissions in classes they currently teach. Roles and ownership are checked
against the database before claiming an attempt. Conditional writes with a unique
token stop an expired worker from replacing a later worker's result.

Use the immutable snapshot whenever it has references. If a snapshot is missing a
reference, retry may use a newly supplied answer/rubric from the live assignment
only when that problem's ID, question text, and points still match. It never
replaces the saved question or maximum. This allows professors to supply an answer
key after submission while keeping the original attempt intact.

Grading is synchronous during submit/retry; there is no separate task worker.
A process interruption or failed final database write leaves a reclaimable lease.
Repeated homework submissions intentionally remain separate attempts. Existing
graded attempts are not automatically regraded after a professor edits an answer.

## Database setup and recommendation integration

Before deploying to a database using the old ungraded-only validator, run:

```javascript
load("docs/assignment-validation.js")
```

Run this in `mongosh` after selecting the intended application database. The
script upgrades the old application-owned status enum even when nested by older
runs, preserves unrelated validation constraints, and adds result validation.
It is repeatable and does not alter student answers or backfill grades. Do not
combine the old `ungraded` enum with the new one without upgrading it: their
intersection would reject every graded write. Custom validators can impose
additional constraints and should be checked by the database operator.

Recommendation adapters now read actual per-problem scores from graded homework
alongside legacy `completed_assignments`. They use the saved problem topics and
partial-credit ratios, including when the live assignment has since been deleted.
Failed or ungraded attempts are excluded. This connects the grade data to the
recommendation backend; recommendation widgets remain separate future UI work.
Manual enrollment/class grades are still separate; AI grading does not overwrite
them. Professor score overrides and grade history beyond separate attempts remain
future work.

Tests mock Rocky and MongoDB. A separate synthetic smoke check verified a correct
and incorrect answer against `qwen3.8-27b`; no real student data or database writes
were used. This checks the integration, not grading quality across a course.
