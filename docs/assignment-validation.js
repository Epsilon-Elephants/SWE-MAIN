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

// Upgrade the old application-owned status enum, including nested validators
// created by older runs, while retaining unrelated/custom constraints.
function upgradeHomeworkGradingStatuses(validator) {
  if (!validator || typeof validator !== "object") return validator;
  const copy = { ...validator };
  const schema = copy.$jsonSchema;
  if (schema && schema.required && ["schema_version", "answers", "assignment_snapshot"].every(
    field => schema.required.includes(field)
  ) && schema.properties && schema.properties.grading_status) {
    const statuses = schema.properties.grading_status.enum;
    if (Array.isArray(statuses) && statuses.length === 1 && statuses[0] === "ungraded") {
      copy.$jsonSchema = { ...schema, properties: { ...schema.properties,
        grading_status: { ...schema.properties.grading_status,
          enum: ["ungraded", "grading", "graded", "failed", "blocked"] },
      } };
    }
  }
  if (Array.isArray(copy.$and)) copy.$and = copy.$and.map(upgradeHomeworkGradingStatuses);
  return copy;
}

function addAssignmentValidator(collectionName, validator) {
  const info = db.getCollectionInfos({ name: collectionName })[0];
  if (!info) {
    db.createCollection(collectionName, {
      validator, validationLevel: "strict", validationAction: "error",
    });
    return;
  }
  const existing = collectionName === "homework_submissions"
    ? upgradeHomeworkGradingStatuses(info.options.validator)
    : info.options.validator;
  const alreadyIncluded = existing && (JSON.stringify(existing) === JSON.stringify(validator)
    || (existing.$and || []).some(item => JSON.stringify(item) === JSON.stringify(validator)));
  const result = db.runCommand({
    collMod: collectionName,
    validator: alreadyIncluded ? existing : existing && Object.keys(existing).length
      ? { $and: [existing, validator] }
      : validator,
    validationLevel: "strict",
    validationAction: "error",
  });
  if (!result.ok) throw new Error(JSON.stringify(result));
}

addAssignmentValidator("assignments", assignmentDatesValidator);
addAssignmentValidator("completed_assignments", completionValidator);

// Homework keeps immutable answers and validated Rocky grades on the same attempt.
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
      grading_status: { enum: ["ungraded", "grading", "graded", "failed", "blocked"] },
      grading_error: { enum: [null, "missing_reference", "invalid_response", "invalid_submission", "service_unavailable"] },
      grading_token: { bsonType: "string" },
      grading_started_at: { bsonType: "date" },
      grading_lease_until: { bsonType: "date" },
      grading_result: {
        bsonType: "object",
        required: ["schema_version", "problems", "total_points", "max_points", "percentage", "model", "graded_at"],
        properties: {
          schema_version: { enum: [1] },
          total_points: { bsonType: ["double", "int", "long"], minimum: 0, maximum: Number.MAX_VALUE },
          max_points: { bsonType: ["double", "int", "long"], minimum: 0, exclusiveMinimum: true, maximum: Number.MAX_VALUE },
          percentage: { bsonType: ["double", "int", "long"], minimum: 0, maximum: 100 },
          model: { bsonType: "string" },
          graded_at: { bsonType: "date" },
          problems: {
            bsonType: "array", minItems: 1,
            items: {
              bsonType: "object", required: ["problem_id", "points_awarded", "max_points", "feedback"],
              properties: {
                problem_id: { bsonType: "string", pattern: "\\S" },
                points_awarded: { bsonType: ["double", "int", "long"], minimum: 0, maximum: Number.MAX_VALUE },
                max_points: { bsonType: ["double", "int", "long"], minimum: 0, exclusiveMinimum: true, maximum: Number.MAX_VALUE },
                feedback: { bsonType: "string", pattern: "\\S", maxLength: 2000 },
              },
            },
          },
        },
      },
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

addAssignmentValidator("homework_submissions", {
  $and: [homeworkSubmissionValidator, {
    $or: [
      { grading_status: { $ne: "graded" } },
      { $jsonSchema: { required: ["grading_result"] } },
    ],
  }],
});
db.homework_submissions.createIndex({ user_id: 1, assignment_id: 1, submitted_at: -1 });
