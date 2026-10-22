// Run in mongosh after selecting the application's database with `use <DB_NAME>`.
// Existing validators are preserved. This does not backfill legacy documents.
const assignmentDatesValidator = {
  $and: [
    {
      $jsonSchema: {
        bsonType: "object",
        properties: {
          posted: { bsonType: "date", description: "First student-visible date (UTC)" },
          due_date: { bsonType: ["date", "null"], description: "Deadline; late completion is allowed" },
        },
      },
    },
    {
      $expr: {
        $or: [
          { $eq: [{ $ifNull: ["$posted", null] }, null] },
          { $eq: [{ $ifNull: ["$due_date", null] }, null] },
          { $gte: ["$due_date", "$posted"] },
        ],
      },
    },
  ],
};

const completionValidator = {
  $jsonSchema: {
    bsonType: "object",
    required: ["assignment_id", "user_id", "score", "completed_at"],
    properties: {
      assignment_id: { bsonType: "objectId" },
      user_id: { bsonType: "objectId" },
      score: {
        bsonType: ["double", "int", "long", "decimal"],
        minimum: 0,
        maximum: Number.MAX_VALUE,
      },
      completed_at: { bsonType: "date" },
    },
  },
};

function addAssignmentValidator(collectionName, validator) {
  const info = db.getCollectionInfos({ name: collectionName })[0];
  if (!info) {
    db.createCollection(collectionName, {
      validator, validationLevel: "strict", validationAction: "error",
    });
    return;
  }
  const existing = info.options.validator;
  const result = db.runCommand({
    collMod: collectionName,
    validator: existing && Object.keys(existing).length
      ? { $and: [existing, validator] }
      : validator,
    validationLevel: "strict",
    validationAction: "error",
  });
  if (!result.ok) throw new Error(JSON.stringify(result));
}

addAssignmentValidator("assignments", assignmentDatesValidator);
addAssignmentValidator("completed_assignments", completionValidator);

// Ungraded student answers are separate from trusted, scored completions.
const homeworkSubmissionValidator = {
  $jsonSchema: {
    bsonType: "object",
    required: ["schema_version", "assignment_id", "user_id", "class_id", "submitted_at",
      "status", "grading_status", "assignment_snapshot", "answers"],
    properties: {
      schema_version: { enum: [1] },
      assignment_id: { bsonType: "objectId" },
      user_id: { bsonType: "objectId" },
      class_id: { bsonType: "objectId" },
      submitted_at: { bsonType: "date" },
      status: { enum: ["submitted"] },
      grading_status: { enum: ["ungraded"] },
      assignment_snapshot: {
        bsonType: "object",
        required: ["title", "description", "problems"],
        properties: {
          title: { bsonType: "string" },
          description: { bsonType: "string" },
          posted: { bsonType: ["date", "null"] },
          due_date: { bsonType: ["date", "null"] },
          problems: {
            bsonType: "array", minItems: 1,
            items: {
              bsonType: "object",
              required: ["schema_version", "problem_id", "type", "content", "points",
                "topic", "reference_answer", "grading_guidance"],
              properties: {
                schema_version: { enum: [1] },
                problem_id: { bsonType: "string", pattern: "\\S" },
                type: { enum: ["short_answer"] },
                content: { bsonType: "string", pattern: "\\S" },
                points: { bsonType: ["double", "int", "long"], minimum: 0, exclusiveMinimum: true, maximum: Number.MAX_VALUE },
                topic: { bsonType: "string" },
                reference_answer: { bsonType: "string" },
                grading_guidance: { bsonType: "string" },
              },
            },
          },
        },
      },
      answers: {
        bsonType: "array", minItems: 1,
        items: {
          bsonType: "object", required: ["problem_id", "answer"],
          properties: {
            problem_id: { bsonType: "string", pattern: "\\S" },
            answer: { bsonType: "string", pattern: "\\S" },
          },
        },
      },
    },
  },
};

addAssignmentValidator("homework_submissions", homeworkSubmissionValidator);
db.homework_submissions.createIndex({ user_id: 1, assignment_id: 1, submitted_at: -1 });
