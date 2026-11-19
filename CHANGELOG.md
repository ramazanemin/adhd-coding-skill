# Changelog

All notable changes to this skill are recorded here. Dates follow the commit
history of this repository. This project has no published release tags yet, so
entries are grouped by date rather than by version number.

## 2026-11-19

### Fixed

- `tests/live_eval.py` checkers treated blank answers as passing for S4 and S7;
  every checker now rejects empty text and S4/S7 require a positive element
  (a concrete next action, and a recovery question respectively).
- Unknown `--scenarios` IDs selected zero scenarios and exited with success;
  they now raise a configuration error and exit with code 2.
- Turkish capital `İ` was never matched because `"İ".lower()` keeps a combining
  dot; all checkers now fold text through a Turkish-aware `normalize()`.

### Added

- S11–S14 offline fixtures and checkers for the working-memory contract.
- `tests/test_live_eval.py` (35 standard-library tests, no network).
- `.github/workflows/validate.yml` runs the unit tests, package validation and
  the offline fixture evaluation on push and pull request.
- `--concurrency` (default 1), `Retry-After` handling for 429/402/503, fail-fast
  on other 4xx responses, and a reported provider source with a warning when the
  anonymous fallback is used.
- A `mode` field (`live` or `offline-fixtures`) in evaluation artifacts so
  fixture runs cannot be mistaken for model runs.

## 2026-11-14

### Added

- Persistent project working memory: one concise prose snapshot in the target
  project's `WORKING_MEMORY.md`, or in the equivalent handoff file that project
  instructions already designate. Covers goal, verified state, decisions,
  changed paths, dated test results, blockers, deferred ideas and next action.
- Single-writer memory protocol for parallel work: contributors hand off a base
  revision plus exact before/after facts; the designated project writer merges
  independent changes, preserves unrelated newer facts, and defers competing
  facts it cannot resolve. This is a coordination rule, not a runtime lock and
  not automatic Git merging.
- Interoperability rules so the skill does not take over other skills' planning,
  debugging, testing, review or deployment workflows, and does not copy their
  plans and reports into memory.
- Acceptance scenarios M1–M12 in `tests/scenarios.md` and a recorded evaluation
  of the memory behavior in `tests/evaluation.md`.

### Changed

- `SKILL.md` gained the "Persistent working memory and other skills" and
  "Parallel memory changes: propose, merge, commit" sections.
- Both READMEs describe the memory contract and state explicitly that parallel
  safety depends on participants honoring one writer.

## 2026-10-19

### Added

- Debugging, Refactoring and Code Review working modes in `SKILL.md`, with one
  worked example each.
- Deterministic `--offline` mode for `tests/live_eval.py`.

## 2026-10-15

### Added

- `tests/live_eval.py` baseline vs. skill-loaded runner for S1–S10.
- `tests/validate_package.py` package, metadata, link, encoding, coverage and
  whitespace checks.

### Changed

- `SKILL.md` tightened for shorter progress updates and explicit modes.

## 2026-10-13

### Added

- Initial release: `skills/adhd-coding/SKILL.md`, Codex metadata
  (`agents/openai.yaml`), English and Turkish READMEs, license, and the S1–S5
  behavior scenarios.
