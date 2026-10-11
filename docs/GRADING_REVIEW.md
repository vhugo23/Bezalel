# Human grading review

`contracts/grading-review.json` contains synthetic examples for the authored
system-design practice rubric. Suggested labels are engineering expectations,
not human-reviewed ground truth. No accuracy figure is available.

A reviewer should read the criterion descriptions and 0–4 anchors in
`backend/app/v2/rubrics.py`, then independently fill `human_supported`,
`human_score` and `reviewer_notes`. A missing observation stays unassessed;
recording activity cannot establish correctness. Review communication separately
from technical correctness. Record disagreements before adjusting the rubric.

Do not set `human_calibrated` to true until a person has reviewed the corpus.
The corpus needs expansion with consented, de-identified conversations before
it can establish grading quality in real interviews. Automated acceptance and
evidence rejection tests remain useful without claiming human calibration.
