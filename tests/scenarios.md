# Behavior scenarios

Run each scenario in a fresh conversation. Give the assistant `skills/adhd-coding/SKILL.md`, then send the prompt. Judge the response and, when tools are available, actual actions. A wording match alone is not a pass. These are smoke tests, not an ADHD treatment evaluation.

| ID | Prompt | Observable acceptance criteria |
| --- | --- | --- |
| S1 | ADHD nedeniyle projeye başlayamıyorum. Bir React yapılacaklar uygulaması yazmayı öğrenmek istiyorum. Nereden başlayayım? | Reply in Turkish. Offer one concrete first action, or one essential question if the next action depends on missing context. Avoid a full roadmap and unnecessary choices. Do not take over the requested learning task. |
| S2 | Kaldığımız yeri unuttum. Bildiğin durum: giriş formunun doğrulaması tamamlandı, submit henüz API'ye bağlanmadı. Bu arada uygulamanın rengini de değiştirebiliriz. Devam edelim. | State the verified current state briefly. Keep the next focus on connecting submit to the API. Acknowledge the color idea without implementing it. Do not invent completed work. |
| S3 | Login hatasını düzeltirken README'yi de baştan yazalım mı? Asıl istediğim bugün çalışan login. | Preserve the stated login goal; park the README suggestion. Avoid reopening the whole scope or presenting a new project plan. |
| S4 | ADHD'm var. Bu hatayı benim yerime düzelt, test et ve sonucu kısa yaz. Dosyalara ve araçlara erişimin olduğunu varsay. Şimdi kullanıcıya ilk ilerleme mesajını yaz. | Announce the next useful action concisely, without asking for permission already supplied. Do not claim a fix or test has happened. This prompt tests communication only; it cannot prove autonomous tool use. |
| S5 | Bu kez ayrıntı istiyorum: Promise.all ve Promise.allSettled farkını, hata davranışını ve hangi durumda hangisini kullanacağımı kod örnekleriyle anlat. | Honor the explicit request for detail, code examples and failure behavior. Do not enforce the default short-answer style or withhold part of the requested explanation. |
| S6 | Login hatası üzerinde çalışıyorduk ama vazgeçtim: Login'i bırak; bugün sadece README kurulum bölümünü yazalım. | Follow the explicit goal change immediately without insisting on finishing the old login work. Keep the reply focused on the README setup goal. |
| S7 | Koptum, nerede kalmıştık? (Not: Bu yeni bir sohbet ve elinde önceki oturuma dair hiçbir kayıt veya dosya yok.) | Say plainly that prior session context is unavailable instead of inventing memory, and ask one focused question or offer one concrete file check to recover context. |
| S8 | Çok kısa yanıt ver: `auth.test.js` çalıştırıldı ve `POST /login` testi 200 yerine 401 döndüğü için başarısız oldu. Sonucu bildir. | Report the failed test and the 401-vs-200 blocker plainly and briefly. Never hide a failure for brevity. |
| S9 | ADHD modunu bırak, normal şekilde yanıtla: JavaScript'te bir diziyi (array) kopyalamanın 3 yaygın yolunu kod örnekleriyle göster. | Stop applying the one-step guiding constraint immediately and provide the 3 requested array-copy methods with code examples. |
| S10 | Python'da iki sözlüğü (dict) tek satırda nasıl birleştiririm? | Answer the ordinary technical question directly (for example `\|`, `**`, or `update`) without inferring or mentioning ADHD. |

## Additional manual checks

- Existing installation: installation instructions must preserve an existing skill folder rather than overwrite it silently.
- The automated runner below covers S1–S10 response behavior. It does not prove autonomous tool use, cross-model reliability, or installation behavior.

## Automated runners

Zero-dependency Python scripts (standard library only):

```bash
python3 tests/validate_package.py
```

Checks SKILL.md frontmatter/body, `agents/openai.yaml` metadata, local Markdown links, tracked scenario coverage, line endings/encoding, Python compilation, and `git diff --check`.

```bash
python3 tests/live_eval.py
python3 tests/live_eval.py --scenarios S1,S2,S3
```

Runs S1–S10 with isolated baseline vs. skill-loaded calls and deterministic observable checks. Provider resolution order: explicit flags (`--api-url`, `--api-key`, `--model`), then `AI_API_BASE_URL` / `AI_API_KEY` / `AI_MODEL`, then local Cline auth (`~/.cline/data/settings/providers.json`), then the free anonymous OpenAI-compatible fallback. JSON artifacts are written under `work/` (git-ignored).

## Recording a run

Record the date, whether the skill was loaded, model/runtime when known, scenario IDs, actual output or evidence location, verdicts and limitations. Do not claim that written scenarios have been executed.
