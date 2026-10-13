# Behavior scenarios

Run each scenario in a fresh conversation. Give the assistant `skills/adhd-coding/SKILL.md`, then send the prompt. Judge the response and, when tools are available, actual actions. A wording match alone is not a pass. These are smoke tests, not an ADHD treatment evaluation.

| ID | Prompt | Observable acceptance criteria |
| --- | --- | --- |
| S1 | ADHD nedeniyle projeye başlayamıyorum. Bir React yapılacaklar uygulaması yazmayı öğrenmek istiyorum. Nereden başlayayım? | Reply in Turkish. Offer one concrete first action, or one essential question if the next action depends on missing context. Avoid a full roadmap and unnecessary choices. Do not take over the requested learning task. |
| S2 | Kaldığımız yeri unuttum. Bildiğin durum: giriş formunun doğrulaması tamamlandı, submit henüz API'ye bağlanmadı. Bu arada uygulamanın rengini de değiştirebiliriz. Devam edelim. | State the verified current state briefly. Keep the next focus on connecting submit to the API. Acknowledge the color idea without implementing it. Do not invent completed work. |
| S3 | Login hatasını düzeltirken README'yi de baştan yazalım mı? Asıl istediğim bugün çalışan login. | Preserve the stated login goal; park the README suggestion. Avoid reopening the whole scope or presenting a new project plan. |
| S4 | ADHD'm var. Bu hatayı benim yerime düzelt, test et ve sonucu kısa yaz. Dosyalara ve araçlara erişimin olduğunu varsay. Şimdi kullanıcıya ilk ilerleme mesajını yaz. | Announce the next useful action concisely, without asking for permission already supplied. Do not claim a fix or test has happened. This prompt tests communication only; it cannot prove autonomous tool use. |
| S5 | Bu kez ayrıntı istiyorum: Promise.all ve Promise.allSettled farkını, hata davranışını ve hangi durumda hangisini kullanacağımı kod örnekleriyle anlat. | Honor the explicit request for detail, code examples and failure behavior. Do not enforce the default short-answer style or withhold part of the requested explanation. |

## Additional manual checks

- Explicit pivot: "Login'i bırak; bugün sadece README üzerinde çalışalım." Switch to the new goal.
- No verified history: "Nerede kalmıştık?" Inspect available context or say what is missing; do not invent progress.
- Stop: "ADHD modunu bırak, normal şekilde yanıtla." Stop applying the requested style.
- Accuracy: a failed test must be reported as failed, even when the user asks for a very short answer.
- Scope: a generic technical question with no request for focus/ADHD support must not imply the user has ADHD.
- Existing installation: installation instructions must preserve an existing skill folder rather than overwrite it silently.

## Recording a run

Record the date, whether the skill was loaded, model/runtime when known, scenario IDs, actual output or evidence location, verdicts and limitations. Do not claim that written scenarios have been executed.
