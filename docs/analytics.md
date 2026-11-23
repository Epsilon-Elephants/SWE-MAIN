# Dashboard analytics

Professor assignment cards show the average percentage across students with a
valid assignment grade. A professor-confirmed decision takes precedence; otherwise
the **highest** graded attempt for each student and assignment counts, including
tentative Rocky scores, so a weaker resubmission never lowers a grade (ties go to
the newer attempt). A pending or failed retry keeps the previous graded result until
a new grade is ready. Work awaiting grading is excluded, rather than counted as zero.
The rule lives in `homework.grades.kept_attempt` and is shared by course totals,
dashboards, the gradebook, and these analytics.

Class cards show the average professor-recorded course percentage when recorded
grades are available. Students without a recorded grade are excluded. Otherwise,
the card shows the average homework percentage: each student's earned and
possible points are summed across their counted assignment grades, then those
student percentages are averaged. The card labels the source and student count.
For example, students with homework percentages of 50% and 90% have an average of
70%, regardless of their differing numbers of attempts.

Topic insights join problem grades to topic labels in the saved submission
snapshot. Grades for the same topic are combined by points within each student;
case and surrounding whitespace in topic names are ignored. A student is flagged
for a topic when that percentage is **below 70%**. Assignment cards summarize just
that assignment; class cards combine the counted grades across the class.
Professor cards count affected students per topic and show three topics with the
rest available in an expander.

Each student class card has a small **Your focus topics** panel showing only that
student's topic percentages for that class, including the course workspace. No grades yet, missing topic labels,
and no struggling topics have separate messages. Topic insights use saved labels,
so editing a live assignment does not change what an earlier attempt assessed.

Professor analytics reads verify the current account and restrict queries to
classes the professor currently teaches. Summaries expose numbers and topic
labels, without answers, reference answers, or grading guidance. Reads are batched
by class; MongoDB projects only score and topic fields, and `kept_attempt` picks the
counted attempt in Python so the rule has a single source of truth. Database failures leave the cards usable with an unavailable message.
No schema migration or additional AI request is needed.

Status popups confirm assignment/problem saves and deletion, class grade saves,
enrollment changes, Rocky questions, and homework submission/grading. Completion
messages are retained in the current session through reruns and page switches,
then consumed once. Grading reports success only when the saved grading status is
`graded`; background completion is detected by the submission-history and course
score refreshes. Retries are queued without blocking the page. Failed, blocked,
automatically retrying, and still-pending results have distinct messages. Inline
errors and saved-work notices remain available after the popup disappears.
