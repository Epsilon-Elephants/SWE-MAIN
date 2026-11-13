# Problem format and AI integration

The app grades short-answer homework with Kent State Rocky using the professor's
reference answer and optional partial-credit rubric. Grades are stored on each
saved submission and shown to students and professors.

## What happens on submit

1. The server checks the student's role, enrollment, assignment visibility, and exact answer IDs.
2. Answers and a canonical assignment snapshot are saved before contacting Rocky.
3. The page returns immediately with Processing. A background worker claims the saved attempt with a ten-minute lease and sends one request to Rocky.
4. The server validates exactly one result per problem, finite points between zero and the saved maximum, and nonblank feedback. It calculates totals and a 0–100 percentage itself.
5. The same submission becomes `graded`, with per-problem points, feedback, model, and grading time. There is no second completion record to duplicate during retries.

Students see tentative Rocky scores or confirmed scores and feedback in their submitted-attempt history. Professors
see actual homework attempts in the assignment editor, including answers, scores,
feedback, and a Review and grade popup. Normal page reruns do not call the model.
The popup shows student and professor answers, preserves Rocky's original grade,
and supports a separately saved professor override or restoration of the AI grade.

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
| `topic` | Required, nonblank subject label for new or edited questions. Legacy reads default to `""`. | Yes |
| `reference_answer` | Required, nonblank private model answer for new or edited questions. Legacy reads default to `""`. | No |
| `grading_guidance` | Private rubric and partial-credit instructions; defaults to `""`. | No |

The [JSON Schema](homework-problem.schema.json) describes the complete canonical
document. Python's `normalize_problem` also accepts authoring shorthand, fills in
defaults, strips surrounding whitespace from text fields other than the ID, and
returns only canonical fields. It does not execute a JSON Schema validator.
`normalize_problems` additionally rejects empty lists and duplicate IDs.

Older plain strings and `{problem_id, content}` documents can still be read and graded. Existing
IDs are preserved, including when a professor edits a question. A text-only
`update_problem` preserves existing metadata. A structured edit is normalized as
the replacement canonical document, so omitted optional fields return to defaults;
include metadata you want to keep. The existing problem ID is always preserved.

For authoring, keep the student task in `content`, an example of a correct answer
in `reference_answer`, and scoring criteria in `grading_guidance`. Use consistent
topic names for recommendations. `authored_problem` and `authored_problems`
enforce a nonblank question, topic, reference answer, and positive points for
creation, editing, and publication. Empty assignments can remain drafts; any
question saved into them must be complete. The JSON Schema's `$defs.authored`
describes these stricter rules while the root schema retains historical
snapshot compatibility. No snapshot backfill is needed.

Partial-credit criteria (`grading_guidance`) are optional and collapsed by
default in the editor. When blank or whitespace-only, Rocky uses its own
judgment to award reasonable partial credit for correct concepts, reasoning,
and intermediate steps, considering the significance of mistakes. It does not
require a rubric or default to all-or-nothing scoring. Supplied criteria take
precedence, and the saved point maximum always bounds the score. Missing
references in historical submissions retain the existing blocked/retry behavior.

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
     "feedback": "Explain how both operands affect the truth value.",
     "study_recommendation": "Build a truth table for a new conjunction and explain which rows make it true."}
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

Each graded problem also stores `study_recommendation`, a brief, actionable
practice suggestion tied to its saved `topic`. Rocky generates this alongside
the score and feedback in the same request. Correct answers receive extension
practice; lower scores receive focused review. The field is optional in model
output for backward compatibility. Blank, non-text, oversized, or missing
recommendations fall back to bounded, topic-based practice guidance without
discarding valid scores or making another model request. Recommendation text
must be at most 1000 characters; prompts prohibit copying private reference
answers or rubrics into it.

Students see suggestions below each problem's feedback and under **What to
practice next** on the overview. Overview recommendations use the latest graded
attempt for each assignment, group by the professor's actual topic labels, and
prioritize lower scores. Unlabeled topics remain question-level guidance rather
than inventing a topic label. Professor overrides take precedence and get
practice guidance based on the adjusted scores. No reference answers, private
rubrics, or override reasons are added to overview data. Viewing suggestions
never calls Rocky again.

The student **Practice** page shows the same topic data in full: topics below 70%
under **Review first** (weakest first), the rest under **Keep practicing**, each with
its suggestion and a link to the source assignment. Percentages are rounded down for
display so a score just under the cutoff never appears as 70%. Its optional **Build my
review plan** button asks the recommendation engine for a prioritized plan, sending
only topic names and score summaries (averaged over all graded attempts), never
answers. It allows up to 1000 output tokens, because Rocky's full plan uses about 800
and is cut off at the engine's 400-token default. Repeat requests within two minutes
are ignored, since a sent request cannot be cancelled. If Rocky does not return a
usable plan, the page labels and shows the engine's score-based fallback.

## Tentative and confirmed course totals

Rocky's successful grading produces a **Tentative Rocky score**. It remains an
estimate until a professor reviews the attempt and chooses **Confirm Rocky's
grade**, or saves an override. Both actions recheck current professor ownership,
validate every score against the snapshot, calculate totals on the server, and
save a separate `professor_grade` with reviewer/time metadata. `source: "rocky"`
records acceptance of the AI result; `source: "professor"` records an override.
Existing saved professor overrides are also confirmed. Rocky's original result
is preserved. Choosing **Use Rocky's original grade** after an override confirms
that original result without making another model request.

Student course pages show a compact score bar above course navigation, refreshed
every five seconds. Green shows confirmed earned points, amber shows unconfirmed
Rocky earned points, and gray shows points not earned on the included graded work.
Text below shows confirmed earned/possible points, tentative earned/possible
points, and the combined estimate. A course with no grades shows an empty bar
without inventing a percentage. Each refresh rechecks the student's role and
enrollment and reads only that student's course submissions.

Totals count each assignment once. The most recent professor decision for that
assignment supplies its confirmed grade; other attempts and the corresponding
Rocky score are excluded from the tentative bucket. If no confirmed attempt
exists, the newest graded Rocky attempt supplies a tentative score. A newer
pending resubmission does not turn a known score into zero, and a new tentative
attempt cannot add points on top of an already confirmed assignment. Pending,
failed, and unsubmitted work adds no score or denominator.

For example, confirmed **8/10** plus unconfirmed Rocky **3/5** produces an actual
confirmed percentage of **80%** and a combined estimate of **11/15 (73.33%)**.
Confirming the second score moves its 3/5 into the confirmed total; it is never
counted in both buckets. Separately entered enrollment/class grades remain in a
collapsed **Professor-recorded course grade** section and are not mixed into
these assignment totals because they lack assignment-level attribution.

## Failures, missing references, and retries

| State | Meaning |
| --- | --- |
| `ungraded` | Saved and queued for background grading (including legacy submissions). Shown as Processing. |
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

The app starts one shared background worker per authenticated server process.
It polls due work every five seconds, handles one attempt at a time, retries
temporary outages with backoff from 30 seconds up to ten minutes, and checks
missing references again after a minute. Submit/retry handlers only save or
queue work. Student history refreshes independently of the answer form.
A process interruption or failed final database write leaves a reclaimable lease,
which the worker discovers after restart. The queue lives in MongoDB.
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
Manual enrollment/class grades are still separate; homework grading does not
overwrite them. Professor overrides live in `professor_grade` with reviewer,
timestamp, and reason metadata, while `grading_result` retains Rocky's result.
Revision checks prevent older review forms replacing newer edits. Student views
and recommendation evidence use the active professor grade. A full history of
past professor edits remains future work.

Tests mock Rocky and MongoDB. A separate synthetic smoke check verified a correct
and incorrect answer against `qwen3.8-27b`; no real student data or database writes
were used. This checks the integration, not grading quality across a course.
