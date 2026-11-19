# Trigger test

Behavior scenarios (S1–S14) measure what happens *after* the skill loads. This file measures whether it loads at all, which is the failure a user never sees: the answer looks fine, just not ADHD-friendly.

## How to run

1. Start a **fresh conversation** where the skill is installed but not mentioned.
2. Paste one prompt below, exactly as written.
3. Record whether the skill activated (its instructions are visibly in effect, or the host shows it loaded) and whether the reply follows its rules.
4. Repeat for each prompt, one conversation each. Do not chain them: earlier turns prime the model.

## Prompts that must load the skill

| ID | Prompt | Why it should load |
| --- | --- | --- |
| T1 | I keep abandoning my side projects halfway, and I can't even start this React app. Where do I begin? | Low-overwhelm / one-step guidance signal without naming ADHD |
| T2 | I'm completely lost. Where were we? My brain is fried and I can't remember what we finished. | Resuming a distracted session |
| T3 | Give me one step at a time and short answers. Long explanations are useless to me right now. | Explicit one-step + low-overwhelm request |

## Prompts that must not load the skill

| ID | Prompt | Why it should not load |
| --- | --- | --- |
| N1 | How do I center a div? | Ordinary programming question; no overwhelm or focus signal |
| N2 | Refactor this class and add unit tests. | Ordinary coding request; detail is wanted, not reduced |
| N3 | fix improt plz | Terse, typo-ridden request; ADHD must never be inferred from typos or brevity |

## Pass rule

- **Pass:** 3/3 load prompts activate the skill, 3/3 non-load prompts leave it off.
- **Fail:** any miss. A false positive (N1–N3 loading) is the worse failure, because it applies ADHD preferences to someone who did not ask for them.
- Explicit invocation (`$adhd-coding ...`) always loads the skill and is not part of this test.

## Recording a run

Note the host, model, date, whether the skill was installed at project or user level, and the per-prompt result. This test has not been executed against a live host yet; the table is the specification, not a result. Automated runners in `tests/live_eval.py` inject the instructions directly and therefore cannot test triggering.
