# Problem format and AI integration

This guide describes the contract implemented in
[`app/homework/schema.py`](../app/homework/schema.py). It separates the existing
grading-input builder from the grading integration that still needs to be built.

## What works today

Professors author structured short-answer problems. Students submit text answers,
and the server saves those answers with a snapshot of the assignment. Submitting
does not call AI, calculate a score, or create a completion record.

`build_grading_payload(submission)` can turn a saved submission into JSON-safe
grading input. No current submission code calls this helper. Separately, the
student dashboard has a working Rocky question-and-answer dialog; it sends the
student's typed question without automatically adding homework or reference answers.

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
and rubrics are accepted today; a future grader needs a policy for handling them.

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
the live assignment is edited or deleted. Build future grading input from that
saved snapshot rather than rereading the latest assignment's questions.

## Exact input produced for future grading

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
homework payload above. No grading prompt template or response schema is wired in.

Without streaming, the client returns the response's `output_text`. With
`stream=True`, it returns a lazy iterator over SSE text deltas. Consume or close
the iterator to release the connection; failures can occur during iteration.
The dashboard streams the answer and retains a completed answer in session state.
It sends a single question per request, without conversation history.

The client itself does not load `.env`; its dashboard caller does. Standalone
scripts must load configuration before constructing a client. Each send requires
a fresh `make_payload` call because sending clears the prepared payload.

## Remaining grading work

The following is integration guidance, **not implemented behavior**:

1. Load an authorized saved submission on the server and build its grading payload.
2. Define a grading prompt and serialize the payload into Rocky's string input. Treat student answers as untrusted data, including text that asks the model to ignore the rubric.
3. Define a versioned model-output contract with problem IDs, awarded points, and feedback. No canonical grading-output schema exists yet.
4. Validate the returned structure, exact problem-ID coverage, and finite scores between zero and each problem's maximum. Calculate totals on the server.
5. Define persisted grading results, failure/retry states, and a policy preventing duplicate grades/completions when a job retries. Submissions currently remain ungraded indefinitely.
6. Connect trusted scores to completion history and any recommendation inputs. Decide how repeat attempts affect displayed grades.

`complete_assignment` currently records nonnegative total points and checks live
assignment visibility/enrollment. It has no per-problem maximum check, submission
link, or retry deduplication. Because it requires a live assignment, it cannot
record a completion after that assignment is deleted, even though a saved snapshot
can still supply grading context. Resolve this policy before wiring in a worker.

The existing weakness analyzer expects separate `Question` and `Attempt` shapes
with `question_id` and boolean `correct`; it does not consume homework submissions
or partial-credit scores automatically. See the [architecture guide](architecture.md).
