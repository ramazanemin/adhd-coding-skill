# Evaluation record

Date: 2026-10-13

## Scope and method

The checks below assess an instruction package and simulated assistant responses. They do not establish clinical effectiveness, reliable behavior across models, or end-to-end tool execution.

One fresh-context Codex subagent produced baseline responses without the skill. A second fresh-context subagent read the skill and produced responses to the same S1-S5 prompts. Each agent handled a batch of five requests described as separate conversations; cases within a batch still shared model context. The test runner did not expose a precise model identifier, sampling settings or seed. This is a qualitative smoke test, not a repeated or controlled benchmark.

The parent agent manually compared each actual response with the observable criteria in [scenarios.md](scenarios.md). A third fresh-context subagent independently reviewed the distribution documents and skill instructions.

## Observed responses

| Case | Without skill | With skill | Assessment |
| --- | --- | --- | --- |
| S1: getting started | Asked whether a React project existed, but first introduced `useState`, `onChange` and a later Add button. | Asked only whether a runnable React project already existed. | The skill-loaded response made the prerequisite question more focused. The baseline was usable but included premature detail. |
| S2: resuming | Restated validation complete / API not connected, continued toward API work and deferred color changes. | Restated the same verified state, parked the color idea and requested the submit code in the simulated text-only setting. | Both preserved the goal and known state. The skill-loaded response offered one user action. Actual file inspection was not exercised. |
| S3: side idea | Prioritized working login; limited possible README changes to relevant instructions. | Prioritized working login and deferred the README rewrite. | Both met the focus criterion. |
| S4: execution update | Announced reproduction, investigation, fix and tests without asking permission. | Announced inspection, reproduction, fix and tests without asking permission. | Both met the communication criterion. This does not demonstrate that any fix or test was performed. |
| S5: requested depth | Explained both Promise methods, error behavior and use cases with code. | Explained both methods, error behavior and use cases with code despite the short-output default. | Both honored the explicit request for depth. |

All five skill-loaded responses met their response-level acceptance criteria in this run. Most baseline responses already met the criteria; no general improvement claim is supported by this small comparison.

Representative skill-loaded outputs:

> S1: İlk adımı mevcut kurulumuna göre seçelim: Bilgisayarında açıp çalıştırabildiğin bir React projesi var mı?

> S3: Bugünkü hedef çalışan login. README'yi yeniden yazmayı sonraya bırakalım; şimdi login hatasını düzeltmeye odaklanıyorum.

> S4: Önce ilgili kodu inceleyip hatayı yeniden üreteceğim. Ardından düzeltmeyi uygulayıp test edeceğim ve sonucu kısa yazacağım.

## Package checks

- The bundled Codex skill-creator `quick_validate.py` accepted the skill: `Skill is valid!`.
- Package validation checks local Markdown link targets, Codex UI metadata lengths and types, the `$adhd-coding` default prompt, and UTF-8 frontmatter.
- Git whitespace validation is run on the staged distribution files before packaging.
- The independent document review found no actionable issues in the READMEs, license, instructions, UI metadata or scenario definitions. It did not run the scenarios or check remote links.

Package validation and whitespace results are recorded by the preparation session; they are separate from the behavioral observations above. The repository contains no CI runner or automated model-evaluation service.

## Not exercised

The additional manual checks in scenarios.md (explicit pivot, missing history, disabling the style, failed-test reporting, non-trigger behavior and preserving an existing installation) are published for future testing. They have not been executed as independent agent scenarios in this run. Installation into a live user's skills directory, other host products, automatic trigger selection and real coding-task completion have not been tested.
