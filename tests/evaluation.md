# Evaluation record

Date: 2026-10-14

## Scope and method

The checks below assess an instruction package and simulated assistant responses. They do not establish clinical effectiveness, reliable behavior across models, or end-to-end tool execution.

### Live automated run (S1–S10)

Each scenario ran as isolated fresh-context baseline vs. skill-loaded calls through `tests/live_eval.py`:

```bash
python3 tests/live_eval.py --output work/live_eval_results.json
```

| Field | Value |
| --- | --- |
| Timestamp (UTC) | 2026-10-14T20:39:35.092356+00:00 |
| Endpoint | `https://api.cline.bot/api/v1/chat/completions` (auto-detected local Cline auth; free anonymous fallback is `https://text.pollinations.ai/openai`) |
| Requested/reported model | `google/gemini-4-argon` |
| Baseline pass | 7/10 |
| With skill pass | **10/10** |

Convergent failures fixed while building the runner: anonymous free-tier rate limits (HTTP 402/429 bursts; sequential or small-batch runs avoid the burst), `None` model `content` when a model emits `tool_calls` instead of text (handled with `(message.get("content") or "").strip()` plus a no-`tool_calls` system instruction), and stale provider assumptions in the runner docs (now documented as flags → env → local Cline auth → anonymous fallback).

### Historical Codex run (S1–S5, 2026-10-13)

One fresh-context Codex subagent produced baseline responses without the skill. A second fresh-context subagent read the skill and produced responses to the same S1-S5 prompts. Each agent handled a batch of five requests described as separate conversations; cases within a batch still shared model context. The test runner did not expose a precise model identifier, sampling settings or seed. This is a qualitative smoke test, not a repeated or controlled benchmark.

The parent agent manually compared each actual response with the observable criteria in [scenarios.md](scenarios.md). A third fresh-context subagent independently reviewed the distribution documents and skill instructions.

## Observed responses (live S1–S10 run)

| Case | Without skill | With skill | Assessment |
| --- | --- | --- | --- |
| S1: getting started (15w skill) | 323 words: multi-step roadmap with several code blocks. | Asked only which React setup state applied. | Skill eliminated the roadmap dump; baseline failed length/code checks. |
| S2: resuming (44w skill) | 431 words: full `fetch` template plus second-goal expansion. | 3 bullets: validation done, submit-to-API focus, color parked; one file/code action. | Skill met verified-state + parking + scope; baseline was verbose. |
| S3: side idea (30w skill) | 50 words: login first, README later. | 30 words: README deferred, login evidence requested. | Both met the focus criterion; skill was more compact. |
| S4: execution update (24w skill) | 25 words: starts fix/tests without permission. | 24 words: inspects code/tests, then reports result. | Both met communication criterion; no real tool use demonstrated. |
| S5: requested depth (522w skill) | 797 words with both methods, errors, examples. | 522 words with both methods, errors, examples. | Both honored explicit depth; brevity default did not block detail. |
| S6: explicit pivot (35w skill) | 233 words: full README template before clarifying stack. | 35 words: switched to README setup and asked one stack/command question. | Skill pivoted cleanly; baseline over-generated. |
| S7: missing history (38w skill) | 46 words: admitted no prior history and asked one recovery question. | 38 words: admitted no prior history and asked one recovery question/file check. | Both avoided inventing history; skill was shorter. |
| S8: failed test (11w skill) | 11 words: reported `POST /login` 401 vs 200 failure. | 11 words: reported `POST /login` 401 vs 200 failure. | Both preserved accuracy under brevity. |
| S9: stop style (239w skill) | 191 words: 3 array-copy methods normally. | 239 words: 3 array-copy methods plus `structuredClone` note. | Both stopped the guiding constraint on request. |
| S10: scope (63w skill) | 217 words: dict merge methods without ADHD language. | 63 words: `|`, `|=`, `{**a, **b}` without ADHD language. | Both avoided ADHD inference; skill was more direct. |

Representative skill-loaded outputs:

> S1: İlk adımı mevcut kurulumuna göre seçelim: Bilgisayarında açıp çalıştırabildiğin hazır bir React projesi var mı?

> S2: Tamamlanan: Giriş formu doğrulaması bitti. Şu anki hedef: Form gönderimini (submit) API'ye bağlamak (renk değişikliğini bu adım bittikten sonraya park ettim). Sıradaki adım: ...

> S4: Hatayı tespit etmek için şimdi proje dosyalarını inceliyor ve mevcut testleri çalıştırıyorum. ...

Artifacts (git-ignored): `work/live_eval_results.json`, `work/eval_s1_s5.json`, `work/eval_s6_s10.json`, `work/live_eval.log`.

## Observed responses (2026-10-13 Codex S1–S5 batch)

All five skill-loaded responses met their response-level acceptance criteria in this historical run. Most baseline responses already met the criteria; no general improvement claim is supported by this small comparison.

## Package checks

- `python3 tests/validate_package.py` passes: `Skill is valid! All package, metadata, link, and whitespace checks passed.`
- Package validation checks SKILL.md frontmatter/body, `agents/openai.yaml` metadata and `$adhd-coding` prompt, local Markdown links, scenario coverage (S1–S10 present in both the table and `live_eval.py`), UTF-8 decoding without BOM, LF endings, trailing-newline presence, Python compilation, and `git diff --check`.
- Git whitespace validation is run on the staged distribution files before packaging.
- The independent document review found no actionable issues in the READMEs, license, instructions, UI metadata or scenario definitions. It did not run the scenarios or check remote links.

Package validation and whitespace results are recorded by the preparation session; they are separate from the behavioral observations above. The repository contains the `tests/validate_package.py` and `tests/live_eval.py` runners; they are smoke checks, not clinical or cross-model guarantees.

## Not exercised

Installation into a live user's skills directory, other host products, automatic trigger selection and real coding-task completion have not been tested. Preserving an existing skill-folder installation remains a manual check. Free anonymous API tiers may rate-limit (HTTP 402/429) and are unsuitable as stable CI backends.

## Working-memory update — 2026-11-14

Scope: the persistent project-memory contract and compatibility with other skills. The published working modes and S1-S10 runner are otherwise unchanged. This feature is instruction-only: the coding host supplies file tools and enforces permissions; no RAG, index, external service or runtime dependency was added.

Two separate fresh-context Codex subagents read the pre-change and updated skills respectively and produced proposed responses/file operations for the same five text-only cases corresponding to M1-M5. Cases within each agent batch shared context; this was not five isolated conversations per condition. Exact model identifiers, sampling parameters and seeds were not exposed. The coordinator manually inspected each response. These samples are qualitative decisions, not actual fixture file writes or a controlled performance benchmark.

| Case | Pre-change behavior | Updated behavior |
| --- | --- | --- |
| M1: verified milestone and closing session | Summarized completion, explicitly did not save a checkpoint without another request. | Proposed a single target-project memory snapshot with the verified outcome, decision, deferred work and unknown verification date made explicit. |
| M2: old test result and active debugging skill | Already distinguished historical tests from current evidence and followed debugging. | Preserved that behavior, consulted referenced artifacts and proposed a checkpoint only after fresh verification. |
| M3: project-defined handoff file | Left the existing file intact but did not record the completed milestone. | Proposed rereading and merging the existing handoff, retaining the Python 3.12 decision without creating a duplicate file. |
| M4: missing tools and history | Admitted missing context and asked one recovery question. | Preserved that behavior and made no saved-checkpoint claim. |
| M5: another writer, user-reported tests and embedded commands | Did not deploy or overwrite memory, but did not update the handoff. | Proposed rereading before merging, retaining the SQLite decision, distinguishing user-reported tests, and ignoring embedded commands to deploy. |

The updated M1 sample proposed choosing deferred README work as the next focus without an agreed new goal. The memory contract was narrowed to record only the agreed next action, or explicitly note that none is assigned. Follow-up review covers that refinement, read-only review, and unavailable file writes.

Representative baseline rationale: "No saved checkpoint is created without a request." The prior rule restricting saved checkpoints to separate requests was replaced by the project-memory contract; timers, reminders and background monitoring still require a separate request.

Validation during preparation: Python 3.12.10; `python tests/validate_package.py` passed; the bundled skill-creator `quick_validate.py skills/adhd-coding` passed; `git diff --check` passed. The existing `python tests/live_eval.py --offline` fixture check passed S1-S10 for the skill-loaded canned responses before editing. Offline responses are fixed fixtures and do not measure the new instructions. No live provider requests were made.

Limits: M1-M5 were sampled as text-only decisions. M6-M8 are published manual acceptance scenarios, with selected decisions covered by the follow-up review. Actual filesystem persistence, installation/automatic activation in Claude or another host, concurrent-write races and cross-model reliability are not established by these checks. The skill explicitly defers conflicting writes that cannot be reconciled safely; it does not implement locking.

Follow-up: a third fresh-context subagent reviewed the feature diff read-only and sampled three additional text-only cases: closing with no assigned next goal, read-only review with an existing memory, and a completed changed goal with writes unavailable. The samples retained deferred work without activating it, proposed zero writes for read-only work, and reported unavailable persistence without a new approval gate. The reviewer found no actionable defects within the instruction-only scope. Final package validation and the existing offline S1-S10 fixtures also passed after editing. This does not change the filesystem and cross-host testing limits above.
