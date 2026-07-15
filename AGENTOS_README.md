# AgentOS

A personal cognitive process: it reads your world model, judges the highest-leverage
move toward your real goal, prepares it, hands you one small trigger, and learns from
whether you pull it - while being engineered to make itself progressively unnecessary.

Not an assistant (waits), not an agent (executes), not a council (takes orders).
A process you are part of, whose purpose is to be a forcing function for your own
action - because the final mile in the world is always human.

---

## The six stages (each builds on the last)

| Stage | File | What it is |
|---|---|---|
| 1 | state_layer.py | STATE - your dossiers made queryable + a live board (ground_state.json) you read and write. |
| 2 | questioner.py | THE QUESTIONER - the senior function. Judges any move: GREENLIGHT / DOWNGRADE / REFUSE via a four-step procedure. Outranks the builder. |
| 3 | loop.py | THE LOOP - one cycle: Sense -> Record -> Question -> Prepare -> Hand off -> Update. Generates its own agenda. Emits ONE trigger card. |
| 4 | builder.py | THE BUILDER - for moves whose 95% is construction: produces a real artifact into drafts/, never pushes. Resource-aware. |
| 5 | guardrail.py + backbone.py | THE BACKBONE - runs the loop unattended behind a safety guardrail + a dark-days dead-man's-switch. |
| 6 | transfer.py | THE TRANSFER SCHEDULE - reads your outcome history and hands execution back as you prove you pull it. The self-erasing layer. |

---

## Setup

1. Put the folder somewhere stable (e.g. C:\Users\HP\Desktop\agentos\).
2. Put your dossiers + profile into corpus/.
3. python state_layer.py index
4. python state_layer.py board     <- you should see your real situation.

Pure standard library for stages 1, 3, 5, 6. Stages 2 and 4 need a model for full
autonomy but ship with a $0 paste-mode fallback. No pip install to start.

## Wiring a model (optional - for autonomous judging/building)

  AGENTOS_PROVIDER = gemini   (or anthropic)
  AGENTOS_MODEL    = <a current model id - you set this; the code does not hardcode one>
  GEMINI_API_KEY   = ...      (or ANTHROPIC_API_KEY)

Gemini's free tier is the cheap workhorse for the Questioner. The Builder respects the
api_budget_usd cap in ground_state.json - it burns prepaid (Pro) capacity freely but
never overspends the API cap.

## Daily use

  python loop.py                 # one cycle -> one trigger card (the move for now)
  python backbone.py             # same, unattended + logged (for scheduled runs)
  python questioner.py "X"       # judge any move before doing it
  python builder.py "spec"       # build an artifact into drafts/ (push stays yours)
  python transfer.py --report    # how much you've taken back

Record what happens - the signal the whole system learns from:
  python state_layer.py outcome "the move" --pulled --moved

## Run unattended

  python backbone.py --print-task-scheduler        # Windows: schtasks + the wake-timer step
  python backbone.py --install-cron "0 23 * * *"    # Linux/Mac

---

## The honest boundaries (read these)

- THE FINAL MILE IS HUMAN. The system thinks, researches, builds a draft, hands you a
  card. It cannot push, send, submit, deploy, or pay - yours, always, by design
  (enforced in guardrail.py, refused in builder.py).
- POWERED-OFF LAPTOPS DON'T RUN JOBS. Schedulers fire only while the machine is on or
  set to wake. True laptop-shut autonomy needs the wake timer or a cheap VPS.
- THE QUESTIONER IS ONLY AS GOOD AS THE BOARD. A board missing a fact (it once lacked
  your resource/capacity model) produces a confident wrong verdict. Keep the board
  honest; that's the maintenance.
- THE TRANSFER SCHEDULE STARTS SHALLOW. It sharpens only as you log real outcomes.
  With little history it hand-holds. Correct, not broken.
- SELF-IMPROVEMENT HERE IS EVALUATION-DRIVEN, NOT MAGIC. It gets better at causing your
  action and at fading - not at performing sophistication.

The point: not to live your life for you, but to convert your decisions into shipped
action and then get out of the way as the capability becomes yours. Built to win by
needing to do less.
