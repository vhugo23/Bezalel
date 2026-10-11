"""Next steps for a candidate who quits a session early.

Authored text filled in with facts from the saved session. No model writes it,
so it never claims a score or a diagnosis the session did not record.
"""
from .models import QuitPlan, QuitStep

REASONS = {
    'lost': "I don't know this material",
    'unclear': "I don't understand what is being asked",
    'time': "I'm out of time",
    'technical': 'Voice or the app is not working',
    'wrong_track': "This isn't what I need to practice",
    'other': 'Something else',
}
HEADLINES = {
    'lost': 'Learn the piece that stopped you, then come back',
    'unclear': 'Get the question clear before you answer it',
    'time': 'Keep what you did and pick it up later',
    'technical': 'Keep practising without voice',
    'wrong_track': 'Pick practice that fits what you need',
    'other': 'Where to go from here',
}


# What the "I don't know" button says on the candidate's behalf when a step is skipped.
SKIP_TEXT = {'lost':"I don't know this one.",'unclear':"I don't understand what is being asked here.",'other':"I'd like to skip this one."}
WHY_ENDED = {
    'session':'',
    'last':' This was the last step, so there was nothing to move on to.',
    'lab':' Later lab stages build on this one, so the lesson ended here.',
    'repeat':' This was the second step you could not answer, so the lesson ended here instead of pushing you through the rest.',
}


def count(n, word):
    return f'{n} {word}' if n==1 else f'{n} {word}s'


def decide(reason, *, step, total, skipped, lab):
    """Skip one step, or end the lesson. Returns 'moved_on' or the key of WHY_ENDED."""
    if reason not in SKIP_TEXT:return 'session'  # out of time, broken voice, wrong track: about the session, not this step
    if step>=total-1:return 'last'
    if lab:return 'lab'
    if skipped:return 'repeat'
    return 'moved_on'


def build(reason, note, *, track, titles, step, answered, hints_used, hints_total, why='session'):
    """titles: step titles in order. answered: indexes of steps with a candidate turn."""
    total=len(titles)
    live=0<=step<total
    title=titles[step] if live else ''
    done=len(set(answered))
    left=max(hints_total-hints_used,0)
    where=f'step {step+1} of {total}, "{title}"' if live else 'the last step'
    summary=f'You stopped "{track}" at {where}. You answered on {done} of {count(total,"step")}'
    summary+=f' and used {hints_used} of {count(hints_total,"hint")} on this one.' if live and hints_total else '.'
    summary+=WHY_ENDED[why]

    grade=QuitStep(title='Send what you said for review',action='grade',
        detail=f'Your answers on {count(done,"step")} are saved. Grading them quotes your own words and, if it finds a gap it can verify, builds a lesson and a retest from it.')
    restart=QuitStep(title='Run this track again',action='restart',
        detail='This session is closed, so a new run starts at step 1.'+(f' You had not reached: {", ".join(titles[step+1:])}.' if live and titles[step+1:] else ''))
    choose=QuitStep(title='Choose a different track',action='plan',detail='Your plan lists every track that is ready to run.')
    if not live:hints=None
    elif left:hints=QuitStep(title='Use the hints you skipped',detail=f'{count(left,"hint")} for "{title}" went unused. Ask for them before you answer next time.')
    elif hints_total:hints=QuitStep(title='Go back to the basics behind this step',detail=f'You used every hint for "{title}", so the gap is in what the step assumes you already know.')
    else:hints=None

    if reason=='lost':
        steps=[QuitStep(title='Name what stopped you',detail=(f'The step you left was "{title}". ' if live else '')+'Write down the one term or idea in its task that you could not explain. Learn that first.'),
               hints,grade if done else None,
               QuitStep(title='Build up to it',action='plan',detail='Run an easier track from your plan, then try this one again.')]
    elif reason=='unclear':
        steps=[QuitStep(title='Ask Dana to rephrase',detail='Say "can you put that another way?" before you answer. It is a normal turn in the conversation.'),
               QuitStep(title='Read the task first',detail='Each step shows its task under "Your turn" on the left. Read it before you start talking.'),
               hints,restart]
    elif reason=='time':
        steps=[grade if done else None,restart,
               QuitStep(title='Find it in your history',action='history',detail='This session and its transcript stay in your practice history.')]
    elif reason=='technical':
        steps=[QuitStep(title='Type your answers',detail='Every step takes typed answers in the message box with voice off.'),
               QuitStep(title='Check the microphone',detail='Allow microphone access for this site and use headphones, then press Start voice again.'),
               grade if done else None,restart]
    elif reason=='wrong_track':
        steps=[choose,QuitStep(title='Update your intake',action='intake',detail='Your plan is ranked from your intake. Change the role, struggles or sources there and generate a new plan.')]
    else:
        steps=[choose,grade if done else None,restart]
    return QuitPlan(reason=reason,reason_label=REASONS[reason],note=note.strip(),headline=HEADLINES[reason],
                    summary=summary,next_steps=[s for s in steps if s])
