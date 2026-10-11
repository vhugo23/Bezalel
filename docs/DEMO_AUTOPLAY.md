# Demo autoplay

Start either original **System design: whiteboard** or **Fix the site on the Pi**
track, then click **Autoplay demo** at the bottom left. The candidate speaks with
a device voice, answers Dana, draws the design or operates the Pi lab, and finishes
at the ordinary grading screen. Dana uses the existing voice playback and fallback.
No microphone permission is needed for autoplay.

Playback is labelled **scripted demo candidate**. It saves synthetic practice
activity to the signed-in account. The answers deliberately include misconceptions:
nonatomic Redis updates in system design, and file permissions and current versus
historical power flags in the Pi track. The ordinary evaluators determine the scores
and verified gaps from saved evidence; autoplay never injects grades or lessons.
Use the review screen's lesson action and then its changed retest to demonstrate
how the next visit addresses a verified weakness.

Pi follow-ups use skill-specific authored coaching and the engine's reference-tested
changed simulator, selected only after a complete grade identifies a verified gap.
They are labelled **Authored coaching**. System design follow-ups retain AI lesson
generation and independent content review. This keeps Pi practice runnable without
asking a model to redefine the simulator's fixed tasks.

**Stop & take over** cancels speech and prevents subsequent scripted actions after
any already submitted request finishes. The saved session remains available for
manual use. Replay continues from the current step; interrupted tool sequences can
repeat safe simulator actions. Navigating away also stops playback. Changed retests
do not offer the original script.

Voice availability depends on device voices and the configured Dana provider.
If playback audio fails, the controller continues with visible text. Live interviews,
board review and grading use the normal configured providers and their quotas.
Browser acceptance tests accelerate speech and use isolated recorded evaluator
fixtures; they establish application flow, not live model grading quality.

Live calibration of the final scripts, on separate labelled synthetic users,
returned a nonpartial graded report with two verified gaps and a lesson-eligible
`next_gap` for each track. An initial design calibration found no usable gap
because its proposed evidence rule was rejected; the final failure-policy answer
was strengthened and validated in a new batch. These are observed results, not
a guarantee that every future model response or provider quota will succeed.
