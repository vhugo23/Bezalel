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
