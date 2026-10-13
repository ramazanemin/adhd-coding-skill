# ADHD Coding Skill

**Clearer coding conversations. One useful next step when you need guidance. Completed work when you ask the assistant to do it.**

[Türkçe](README.tr.md) · [Skill instructions](skills/adhd-coding/SKILL.md) · [Behavior scenarios](tests/scenarios.md)

An instruction-only Agent Skill for ADHD-friendly coding collaboration. It helps an assistant keep explanations manageable, recover the current task after a break, and avoid turning every new idea into extra work. You can use these preferences whether or not you have ADHD.

## What it changes

- **Doing:** the assistant carries out authorized work and reports the result briefly.
- **Guiding:** the assistant gives one concrete action, then helps with the next when you are ready.
- **Explaining:** the assistant answers at the depth you request, including full examples when useful.

Short answers are a default, not a restriction. You can say "explain in detail," "show the whole plan," or "stop using this style" at any time.

## Install in Codex

1. Download or clone this repository.
2. In the project where you want to use the skill, create `.agents/skills` if needed.
3. Copy this repository's `skills/adhd-coding` folder into it. The result should be `.agents/skills/adhd-coding/SKILL.md`. If that destination already exists, compare the versions and preserve your edits before replacing anything.
4. Invoke it in your coding conversation:

```text
$adhd-coding Help me finish the login form. Keep updates short and do the implementation and tests.
```

Codex supports repository skills in `.agents/skills` and user skills in `~/.agents/skills`. For use across projects, copy the same folder to the user location instead. See the [official skills documentation](https://learn.chatgpt.com/docs/build-skills) for current discovery and installation behavior. If the skill does not appear, restart Codex.

For another Agent Skills-compatible coding assistant, follow that host's installation instructions and install the same skill folder. This repository does not claim that every host has been tested. The optional `agents/openai.yaml` file provides Codex metadata.

## Try it

```text
$adhd-coding I want to learn React but I am stuck getting started. Give me one useful first action.
```

```text
$adhd-coding I lost the thread. Summarize the last verified state and resume the current task.
```

```text
$adhd-coding Fix this bug, run the relevant tests, and give me a short result. Ask only if an essential detail is missing.
```

The skill does not start timers, save personal health information, or run background tasks. Those require a separate request and appropriate tools. It is a communication aid, with no claim of clinical effectiveness.

## Repository

```text
skills/adhd-coding/SKILL.md        Portable skill instructions
skills/adhd-coding/agents/openai.yaml  Optional Codex metadata
tests/scenarios.md                Behavioral acceptance scenarios
tests/evaluation.md               Recorded checks and their limits
README.tr.md                     Turkish documentation
LICENSE                          MIT license
```

## Validation and contributions

Read the [scenarios](tests/scenarios.md) and [evaluation record](tests/evaluation.md). Behavioral tests judge observable outcomes, including honoring detailed requests and completing authorized work. They are not medical evidence or a promise of identical behavior across models.

To suggest an improvement, describe the user request, the observed response, and the desired behavior. Use fictional or anonymized examples. Keep additions focused on coding collaboration, and retest affected scenarios.

[MIT License](LICENSE).
