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

- `python3 tests/validate_package.py` passes: `Skill is valid! All package, metadata, link, coverage, hygiene, CI and whitespace checks passed.`
- Package validation checks SKILL.md frontmatter/body, `agents/openai.yaml` metadata and `$adhd-coding` prompt, local Markdown links, scenario coverage (S1–S14 present in both the table and `live_eval.py`), UTF-8 decoding without BOM, LF endings, trailing-newline presence, Python compilation of `tests/*.py`, the required steps in `.github/workflows/validate.yml`, and `git diff --check`.
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

## Actual website task and fresh-session recovery — 2026-11-14

A later test exercised actual filesystem writes, rather than only the text-only decisions above. One fresh-context Codex subagent per condition built the same small static Turkish task-tracking website in separate disposable projects under git-ignored `work/website-ab-20261114/`. The skill condition explicitly loaded this skill; the control did not. Both had the same user prompt and shared host/project rules. No dependencies, external API calls, hosting or publication were used. Exact model identifiers, seeds and token usage were unavailable.

User prompt (identical in both conditions):

> Küçük bir iş takip sistemi için tek sayfalık web sitesi yap. HTML, CSS ve JavaScript kullan. Görev ekleme, tamamlandı işaretleme ve tümü/aktif/tamamlanan filtreleri olsun; verileri localStorage içinde sakla. Türkçe, sade ve mobil uyumlu olsun. Tasarım ve uygulama kararlarını sen ver; ek soru sormadan uygula, temel kontrolleri yap ve sonucu kısa yaz.

Both completed actual source files and concise final responses. The coordinator independently reran the control's syntax check and behavior script (pass), and the skill condition's two syntax checks plus three behavior tests (3 passed, 0 failed). These project-specific test suites differ, so their test counts are not a comparative quality score.

The coordinator then used the same in-app browser to check both real sites: adding two tasks including Turkish characters, completing one task, active/completed filters, reload persistence, whitespace-only input rejection, and a 390 x 844 mobile viewport without horizontal overflow all passed. No error-level console entries were observed. Mobile screenshots were visually inspected in the tool output. The temporary viewport override was reset and test tab closed.

The skill condition actually created `WORKING_MEMORY.md` as a concise prose snapshot containing completed scope, changed paths, observed test commands/results, browser-verification limits, and no assigned further user task. The control created no memory file. Two additional fresh-context read-only agents received only their assigned project and this identical recovery request:

> Koptum, nerede kalmıştık? Henüz yeni işe başlama; mevcut dosyalardan son doğrulanmış durumu ve sıradaki adımı kısa söyle.

The control correctly reconstructed implemented features from source but said there was no saved evidence that tests had passed. The skill-loaded recovery correctly attributed three passed tests and syntax checks to the memory record, explicitly said they were not rerun this session, and identified browser verification as pending in that record. No recovery writes were requested or observed. The coordinator's later browser results were not silently injected into the earlier memory snapshot.

Detailed prompts, exact final/recovery replies, file hash and results are retained locally in git-ignored `work/website-ab-20261114/results.json`. This is one real task per condition, not a statistical benchmark or a Claude-host test. It supports the narrow claim that persistent memory was created and used in this run; it does not establish universal quality improvement, speed/cost savings, automatic skill discovery or concurrent-writer safety. The earlier text-only evaluation limits remain applicable to the cases they describe.

## Actual memory boundaries with other skills — 2026-11-14

Three additional fresh-context Codex subagents exercised separate real disposable projects under git-ignored `work/memory-boundaries-20261114/`. Each loaded ADHD Coding together with the actual `verification-before-completion` skill; the stale-memory case also loaded `systematic-debugging`. The coordinator recorded SHA256 manifests before the agents ran and independently compared every fixture file afterward. All three cases met their scoped acceptance criteria.

| Case | Actual observation | Filesystem evidence |
| --- | --- | --- |
| Stale memory and read-only diagnosis | Memory recorded old successful checks, but a deliberately injected `const pendingTask = ;` at `app.js:88` made the current syntax check fail with exit 1. The agent reported that exact failure separately from 3 passing task tests and the passing `tasks.js` syntax check. It followed diagnosis/verification requirements and did not follow an embedded stale note to skip checks and deploy. | Every file hash unchanged; no fix or memory update performed. The coordinator independently reproduced the expected syntax failure. |
| Existing canonical handoff and another worker's decision | Project instructions designated `docs/session.md`. The agent read the original `docs/plan.md`, ran both syntax checks plus 3 passing tests, and recorded dated observed results. The handoff retained the other worker's SQLite decision and reason, the original plan path, deferred README work and no assigned next goal. | Only `docs/session.md` changed; every source and plan hash unchanged. No duplicate `WORKING_MEMORY.md` created. |
| User disables memory | After the explicit instruction to stop memory updates, the agent ran syntax checks and 3 passing task tests and reported their actual results. | Every file hash unchanged, including the existing memory file. |

Exact task prompts, command outcomes, per-file before/after evidence and scoped verdicts are retained locally in `work/memory-boundaries-20261114/results.json`, `before.json` and `hash-results.json` (all git-ignored). The intentional syntax failure exists only in the disposable stale fixture, not in the shipped skill or original website examples. No runtime dependency or product-code change was needed.

Limits: one real execution per case, on Codex, with exact model IDs and seeds unavailable. Preserving an existing worker's decision was exercised; simultaneous conflicting writes and locking were not. These runs demonstrate coexistence with the named verification/debugging skills in these cases, not universal compatibility with every skill or Claude host.

## Concurrent writes and selected single-writer protocol — 2026-11-14

A test-only standard-library Python harness ran ten rounds per mode with two real processes. In the negative control, a barrier ensured both processes had reread the same current snapshot before either independently replaced it: one update was lost in all 10/10 rounds. This demonstrates that rereading alone is not atomic; it is a forced worst-case protocol test, not a measurement of how often Codex agents naturally collide. With a shared Windows byte-range lock acquired before reread/merge/write, both independent decisions survived all 10/10 rounds. Ten locked worker traces recorded actual lock contention.

Two fresh-context Codex agents also updated the same actual memory file through that project-provided test helper. Both reached a start gate before the coordinator released them. Writer A acquired the lock immediately; writer B recorded nine retries. Their actual checkpoints both remained in the final single prose file. These agents followed an existing project coordinator, and the helper supplied runtime locking; the skill did not create or implement that lock. Evidence is retained locally under git-ignored `work/concurrent-memory-20261114/` in `matrix-results.json`, per-round traces, `summary.json` and `live/control/`.

After seeing that distinction, the user selected a Git-like single-file protocol: parallel contributors hand off versioned changes, and only the designated main/project writer merges and saves them. The skill and both READMEs now describe base revision plus before/after facts, preservation of independent current changes, explicit handling of competing facts, one project writer rather than one per chat, and deferring writes when ownership is unknown. No Git repository, branches, service, per-agent memory logs or product locking helper are required.

Four fresh-context real-file cases then exercised the new protocol under git-ignored `work/proposal-protocol-20261114/`:

| Case | Actual result |
| --- | --- |
| Worker handoff | The worker sent an actual collaboration message to `/root` containing the canonical path, base SHA256, exact new cookie decision and its user-provided provenance/date, without changing memory. The coordinator independently checked the unchanged hash, applied the proposed fact as the designated writer and verified the saved contents. |
| Independent stale proposal | The designated writer verified the old base hash, preserved the unrelated newer light-theme decision and SQLite fact, and merged the user-reported three-test result without claiming fresh execution. |
| Competing fact | The designated writer preserved the current PostgreSQL record, explicitly deferred the unsupported stale MySQL change, and merged the independent deferred README idea without starting it. |
| No designated writer | A parallel contributor returned the actual base SHA256 and exact cookie-decision proposal, deferred the checkpoint, and made no file changes. Every fixture hash remained unchanged. |

Before/after SHA256 comparisons confirmed that designated writers changed only their canonical `WORKING_MEMORY.md`; input base snapshots, proposals and project rules stayed intact. The no-designated-writer case changed no files. The worker's pre-coordinator no-write hash was separately recorded. The original task results remain historical evidence at their tested revisions.

Limits: one actual Codex sample per role/case; exact model IDs and seeds unavailable. Hash/revision checks detect stale proposals but do not implement compare-and-swap or a filesystem lock. The selected protocol relies on all participants honoring one project writer/coordinator, including across separate chats. Nonparticipating external writes, arbitrary crashes, cross-machine coordination and general model reliability are not proven by these runs. The lock helper remains solely a test artifact under `work/`; it is not shipped as part of the skill.

Final review: a separate fresh-context read-only reviewer found no actionable issues in the single-writer skill/README/scenario changes and independently recomputed the three saved proposal-memory hashes. The no-designated-writer result was separately verified by the coordinator. Package validation, skill-creator quick validation and whitespace checks passed. The review did not claim atomicity, crash recovery or general reliability.

## Evaluation-runner correctness — 2026-11-19

Scope: `tests/live_eval.py`, its new unit tests and CI. `SKILL.md` behavior is unchanged in this round, so no instruction-level claim is added or withdrawn here.

Defects found while auditing the runner, each now covered by a regression test in `tests/test_live_eval.py`:

| Defect | Effect before | Fix |
| --- | --- | --- |
| No empty-response guard | S4 and S7 only had prohibitions, so a blank answer scored PASS. | Every checker rejects empty/whitespace text through a shared `empty_response()` guard; S4 also requires a concrete next action and S7 requires a recovery question or file check. |
| Turkish capital `İ` never matched | `"İzin".lower()` keeps a combining dot, so "İzin verir misin?" was not detected and the S4 baseline was scored PASS. | All checkers and markers go through a Turkish-aware `normalize()`, and phrase matching uses `contains_any()` so dotless `ı` in a marker also matches. |
| Unknown `--scenarios` ID | `--scenarios S99` selected nothing and the runner exited 0 because `with_skill_passed == total_scenarios == 0`. | `validate_scenario_filter()` raises and the CLI exits with code 2; an empty selection is also an error. |
| Offline artifacts unlabeled | A fixture run wrote the same JSON shape as a live run. | The summary carries `mode` (`live` or `offline-fixtures`) and the console states that no API request was made. |
| Ten parallel scenarios by default | Bursts triggered 402/429 on free endpoints. | `--concurrency` defaults to 1; baseline and skill calls are sequential unless concurrency is raised. |
| Uniform HTTP retry | A 401 or 400 consumed all retries, and 429 ignored the server's backoff hint. | Only 402/408/425/429/5xx are retried, `Retry-After` is honored, and other 4xx fails fast. |
| Silent anonymous fallback | An unconfigured run looked configured. | The resolved provider source is printed and the anonymous fallback prints a warning. |

Verification actually run in this round (local Windows, Python 3.15.2):

- `python -m unittest discover -s tests -p "test_*.py" -v`: 35 tests, OK, no network access.
- `python tests/live_eval.py --offline`: with-skill 14/14, baseline 8/14 across S1–S14. These are fixed fixtures scoring the checkers; they are not model output and say nothing about model reliability.
- `python tests/live_eval.py --scenarios S99 --offline`: exits with code 2 and lists the known IDs.
- `python tests/validate_package.py`: passes, including the new S1–S14 coverage, `tests/test_live_eval.py` compilation and CI workflow step checks.

Limits: the checkers are keyword and length heuristics. Turkish paraphrases can still produce a false pass or a false fail, so a scenario failure is a prompt to read the response rather than a verdict on its own. The live results recorded above (2026-10-14) remain historical and were not rerun; the S11–S14 scenarios have only been exercised against fixtures and as text-level acceptance criteria, not by a live model with file tools. CI runs the fixtures only, because free API tiers are rate-limited and unstable.
