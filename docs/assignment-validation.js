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
