// Verify migration behavior without connecting to MongoDB.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('docs/assignment-validation.js', 'utf8');
const original = {
  $and: [
    { custom_department_rule: { $exists: true } },
    { $and: [{ $jsonSchema: {
      required: ['schema_version', 'answers', 'assignment_snapshot'],
      properties: { grading_status: { enum: ['ungraded'] }, answers: { bsonType: 'array' } },
    } }] },
  ],
};
const stored = { homework_submissions: { validator: original } };
const db = {
  getCollectionInfos: ({ name }) => stored[name] ? [{ options: stored[name] }] : [],
  createCollection: (name, options) => { stored[name] = options; },
  runCommand: (command) => { stored[command.collMod] = command; return { ok: 1 }; },
  homework_submissions: { createIndex: () => {} },
};
function run() { vm.runInNewContext(source, { db }); }
run();
const once = JSON.stringify(stored.homework_submissions.validator);
assert(once.includes('custom_department_rule'));
function findEnums(node, found = []) {
  if (node && typeof node === 'object') {
    const status = node.$jsonSchema?.properties?.grading_status?.enum;
    if (status) found.push(status);
    if (node.$and) node.$and.forEach(item => findEnums(item, found));
  }
  return found;
}
const enums = findEnums(stored.homework_submissions.validator);
assert(enums.length >= 2);
assert(enums.every(statuses => statuses.includes('graded') && statuses.includes('failed') && statuses.includes('blocked')));
assert.deepEqual(original.$and[1].$and[0].$jsonSchema.properties.grading_status.enum, ['ungraded']);
run();
assert.equal(JSON.stringify(stored.homework_submissions.validator), once);
assert.equal(stored.homework_submissions.validationAction, 'error');
console.log('Grading validator upgrade preserves custom constraints and is repeatable.');
