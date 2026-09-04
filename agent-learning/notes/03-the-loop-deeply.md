# Module 3 — The loop, deeply
*2026-09-05*

## What I built

Four termination conditions and a checkpoint payload in `math_worker`
([step4_orchestrator.py](../step4_orchestrator.py)). Before this, my agent had exactly
one way to stop: `max_iterations`.

## The problem this solves

An agent that works at 5 turns and quietly gets worse at 20. Mine had never run past 5,
so I had no idea what it cost or how it would end. With one exit, I also couldn't tell
"finished the job" apart from "ran out of turns" — both just fell out the bottom of the
loop and returned something that looked like an answer.

## What surprised me

I assumed both token counts grow as a conversation gets longer. They don't.

```
turn 1:   100 in,  20 out
turn 2:   240 in,  20 out
turn 3:   400 in,  20 out
turn 10: ~2000 in, 20 out
```

`prompt_eval_count` grows quadratically because I re-send the entire history every turn.
`eval_count` stays flat — the model's reply doesn't get longer just because the
conversation did.

So in a multi-turn agent almost all the money is input tokens: history I already paid
for, being paid for again. I'd have optimised output length and wondered why the bill
didn't move.

## The failure I caused on purpose

Set `max_tokens=200` to force the budget to fire. It didn't — I got a normal answer.
Set `max_tokens=1`. That fired:

```
{'status': 'hit_max_tokens', 'messages': 3, 'tokens_used': 192, 'step': 1}
```

The reason is in where I put the check:

```python
for step in range(max_iterations):
    if total_used >= max_tokens:    # turn 1: total_used is 0. Always passes.
```

**Turn one is always free.** The budget can never block the first model call at any
value. If turn one is a 200K-token prompt, I pay in full and find out afterwards.

Moving the check after the call has the mirror flaw — I'd always go one turn over.
Neither placement is right. The actual fix is estimating cost before sending.

## Numbers

| | |
|---|---|
| Termination conditions before → after | 1 → 3 |
| Tokens for one turn, trivial math question | 192 |
| `max_tokens` that failed to fire | 200 |
| `max_tokens` that fired | 1 |

## What I would do differently

I built a checkpoint I can't resume from. `math_worker` returns
`{status, messages, tokens_used, step}` — correct payload. Then the orchestrator
flattens it to a display string and drops `messages`, which is the only field that makes
the run resumable. I kept the label and threw away the state.

Also: changing the return type broke my eval suite silently. `expected_answer in answer`
checks *keys* on a dict, so it reports "answer wrong" instead of crashing. A return-type
change is a code change, and I only got away with it because I had 5 eval cases.

## Open question

A budget that resets on restart isn't a budget. Resume three times under a 4,000-token
cap and I've spent 12,000. Same for `max_iterations` — resuming disarms the
infinite-loop guard entirely.

So the counter has to persist with the checkpoint, not with the process. Where does it
live, and who owns it when the same budget is shared across an orchestrator and its
workers?
