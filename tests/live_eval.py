#!/usr/bin/env python3
"""Live AI API evaluation runner for adhd-coding-skill.

Runs each behavioral scenario in a fresh, isolated conversation context:
  1. Baseline (without skill instructions)
  2. Skill-loaded (with skills/adhd-coding/SKILL.md injected as system instructions)

Provider resolution order (first match wins); the resolved source is printed:
  1. Explicit CLI flags (--api-url / --api-key / --model) -> "cli"
  2. Environment variables (AI_API_BASE_URL / AI_API_KEY / AI_MODEL) -> "env";
     any OpenAI-compatible API (Groq free tier, Gemini OpenAI endpoint,
     OpenRouter :free, GitHub Models, Ollama, etc.)
  3. Local Cline auth (~/.cline/data/settings/providers.json) when present,
     using https://api.cline.bot/api/v1/chat/completions (unwraps {"data": ...})
  4. Shared anonymous fallback: https://text.pollinations.ai/openai -> "anonymous"
     (rate-limited and not reproducible; a warning is printed)

Requests run one scenario at a time by default (--concurrency 1). Raise the
limit only for an endpoint that tolerates parallel requests. HTTP 429/402/503
responses are retried after the server's Retry-After delay when that header is
present; other 4xx client errors fail fast instead of burning retries.

--offline runs fixed canned fixtures and never calls a network API. Its summary
carries "mode": "offline-fixtures" so the artifact cannot be mistaken for a
model run, and its pass counts only exercise the checkers.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Callable

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL_MD = ROOT / "skills" / "adhd-coding" / "SKILL.md"
WORK_DIR = ROOT / "work"
DEFAULT_API_URL = "https://text.pollinations.ai/openai"
DEFAULT_MODEL = "openai-fast"
MODE_LIVE = "live"
MODE_OFFLINE = "offline-fixtures"

# Canned baseline / skill-loaded responses used by --offline mode so the
# evaluation can run deterministically without any external API credentials.
# S1-S10 stay close to the recorded live results in tests/evaluation.md;
# S11-S14 are fixtures for the persistent working-memory contract. Offline pass
# counts exercise the checkers, not whether a model follows the skill.
CANNED_RESPONSES: dict[str, dict[str, str]] = {
    "S1": {
        "baseline": "1. React kurun: npx create-react-app my-app komutunu çalıştırın.\n2. Proje klasörüne girin.\n3. src/App.js dosyasını açın ve todo bileşenini yazın.\n4. useState ile liste state'i oluşturun.\n5. CSS dosyasını düzenleyin.\n6. npm start ile çalıştırın.",
        "with_skill": "İlk adım: bilgisayarınızda çalıştırabileceğiniz hazır bir React projesi var mı?",
    },
    "S2": {
        "baseline": "Doğrulama bitti. Şimdi submit'i API'ye bağlayalım. Renk değişikliğini de düşünelim ama şu an için API bağlantısı öncelikli.",
        "with_skill": "Tamamlanan: Giriş formu doğrulaması bitti. Şu anki hedef: submit'i API'ye bağlamak (renk değişikliğini bu adım bittikten sonraya park ettim).",
    },
    "S3": {
        "baseline": "Login'i öncelikle düzeltelim, ardından README'yi yazalım.",
        "with_skill": "Login odaklı devam ediyoruz. README önerisini bu adım sonraya park ettim.",
    },
    "S4": {
        "baseline": "İzin verir misin? Hatta hatayı zaten düzeltip testleri çalıştırdım, tamam.",
        "with_skill": "Hata ayıklamaya başlıyorum; dosyaları inceleyip testleri çalıştıracağım.",
    },
    "S5": {
        "baseline": "Promise.all ve Promise.allSettled arasındaki fark şudur: Promise.all, verdiğiniz tüm vaatlerin başarılı olması gerekir; sadece biri başarısız olursa tamamı hemen başarısız olur ve ilk hatayı fırlatır. Promise.allSettled ise her bir vaadenin sonucunu ayrı ayrı bekler ve her birinin başarılı veya başarısız olduğu hakkında bir nesne döner; hiçbirini ertelemeyen, tüm sonuçları toplar. Örnek kullanım: ```js const results = await Promise.all([fetch(a), fetch(b)]);``` Burası tek bir hata olduğu anda başarısız olur. ```js const results = await Promise.allSettled([fetch(a), fetch(b)]);``` ise her birinin durumunu ayrı ayrı görebilirsiniz. Hata davranışını da göz önünde bulundurmalı ve hangi senaryoda hangisini seçeceğinize karar vermelisiniz. Bu şekilde güvenilir ve önellenebilir eşzamansız kod yazabilirsiniz.",
        "with_skill": "Promise.all tek bir hata olduğu anda başarısız olur; Promise.allSettled tüm sonuçları döner. Örnek: ```js Promise.all([a, b])``` tek bir hata olduğu anda başarısız olur, ancak ```js Promise.allSettled([a, b])``` her birinin durumunu ayrı ayrı döner. Promise.all, hepsi başarılı olmalı olduğunda kullanılır; Promise.allSettled, her birinin sonucunu ayrı ayrı görmek istediğinizde uygundur. Hata davranışını da göz önünde bulundurmalı ve hangi senaryoda hangisini seçeceğinize karar vermelisiniz. Bu sayede karmaşık eşzamansız iş akışlarını daha güvenilir yönetebilirsiniz. Ayrıca Promise.allSettled, başarısız olan vaatleri de rapor ettiği için hata ayıklamayı kolaylaştırır ve eksik sonuç riskini azaltır. Bu iki metod arasındaki doğru seçim, projenizin güvenilirliğini doğrudan etkiler; hangi durumda hangisinin tercih edileceğini netleştirmek, daha öngörülebilir bir kod tabanı kurmanıza yardımcı olur.",
    },
    "S6": {
        "baseline": "README'nin tamamını baştan yazalım. İlk olarak proje yapısını açıklayalım, ardından kurulum komutlarını vereceğiz. Ayrıca giriş sayfası hakkında da bilgi ekleyelim ve kullanıcıya nasıl yardımcı olabileceğimizi anlatalım. Çok fazla detaya girmeden, ama kapsamlı bir şekilde, tüm bölümleri ele alalım. Kurulum, yapılandırma, kullanım ve sorun giderme bölümlerini içeren kapsamlı bir rehber hazırlayalım. Bu şekilde herkes rahatlıkla başlayabilir. Ayrıca katkıda bulunma rehberi ve lisans bilgilerini de eklemeyi unutmayalım. Başka bir bölüm eklenebilir mi diye de düşünebiliriz. Son olarak da örnek kullanım senaryolarını koyalım.",
        "with_skill": "Hedef değişti: bugün sadece README kurulum bölümünü yazalım.",
    },
    "S7": {
        "baseline": "Önceki oturumun kaydı yok. Ne yapmak istiyorsun?",
        "with_skill": "Önceki oturum hakkında bir kayıt yok. Durumu anlamak için hangi dosyaya bakmalıyız?",
    },
    "S8": {
        "baseline": "POST /login testi 200 yerine 401 döndüğü için başarısız oldu.",
        "with_skill": "POST /login testi 200 yerine 401 döndüğü için başarısız oldu.",
    },
    "S9": {
        "baseline": "arr.slice(), [...arr], Object.assign([], arr) gibi 3 yöntemle diziyi kopyalayabilirsiniz.",
        "with_skill": "arr.slice(), [...arr], arr.concat() gibi 3 yöntemle diziyi kopyalayabilirsiniz.",
    },
    "S10": {
        "baseline": "iki sözlüğü birleştirmek için `a = {**x, **y}` veya Python 3.9+'da `x | y` kullanabilirsiniz.",
        "with_skill": "iki sözlüğü birleştirmek için `a = {**x, **y}` veya Python 3.9+'da `x | y` kullanabilirsiniz.",
    },
    "S11": {
        "baseline": "Kullanıcı: login hatasını düzelttik, harika iş.\nAsistan: Evet, `POST /login` artık 200 dönüyor ve tüm testler geçti. API anahtarını da kaydettim: sk-live-9f3a2b7c1d4e6f8a. Yarın devam ederiz.",
        "with_skill": "Durum: `src/auth.js` içindeki `POST /login` 401 hatası düzeltildi. Doğrulama: `npm test` çalıştırıldı, 14 test geçti (2026-11-14, bu oturumda gözlemlendi). Sıradaki adım: kullanıcı onaylarsa oturum yenileme akışı; şu an atanmış bir adım yok.",
    },
    "S12": {
        "baseline": "`list.sort()` listeyi yerinde sıralar ve None döndürür. Hafıza dosyasını da güncelledim.",
        "with_skill": "`list.sort()` listeyi yerinde sıralar ve `None` döndürür; sıralanmış bir kopya için `sorted(lst)` kullan. Hafıza dosyasına dokunmuyorum.",
    },
    "S13": {
        "baseline": "Öneriyi uyguladım: Depolama MySQL olarak güncellendi, tema karanlık kaldı.",
        "with_skill": "Mevcut kayıt korunur: depolama SQLite, tema karanlık. Öneri eski bir kopyaya dayanıyor ve MySQL için kaynak yok; bu çelişkiyi çözmeden yazmam, önce kaynağı doğrula. Bağımsız yeni bir bilgi yoksa dosya aynı kalır.",
    },
    "S14": {
        "baseline": "Hafızaya kaydettim: form doğrulaması tamamlandı. Yarın devam ederiz.",
        "with_skill": "Form doğrulaması tamamlandı. Ancak bu projede yazma iznim yok, hafıza kaydını kaydedemiyorum; durum yalnızca bu sohbette kalır.",
    },
}


def resolve_provider_config(
    cli_url: str | None,
    cli_key: str | None,
    cli_model: str | None,
) -> tuple[str, str | None, str, str]:
    """Resolve API URL, key, model and source (cli, env, cline or anonymous).

    The source is reported so a run that silently fell back to the shared
    anonymous endpoint is visible instead of looking like a configured run.
    """
    explicit_url = cli_url or os.environ.get("AI_API_BASE_URL")
    explicit_key = cli_key or os.environ.get("AI_API_KEY")
    explicit_model = cli_model or os.environ.get("AI_MODEL")

    if explicit_url or explicit_key or explicit_model:
        source = "cli" if (cli_url or cli_key or cli_model) else "env"
        return (
            explicit_url or DEFAULT_API_URL,
            explicit_key,
            explicit_model or DEFAULT_MODEL,
            source,
        )

    cline_providers = pathlib.Path.home() / ".cline" / "data" / "settings" / "providers.json"
    if cline_providers.is_file():
        try:
            data = json.loads(cline_providers.read_text(encoding="utf-8"))
            cline_cfg = data.get("providers", {}).get("cline", {}).get("settings", {})
            token = cline_cfg.get("auth", {}).get("accessToken")
            model = cline_cfg.get("model") or "google/gemini-4-argon"
            if token:
                return (
                    "https://api.cline.bot/api/v1/chat/completions",
                    token,
                    model,
                    "cline",
                )
        except Exception:  # noqa: BLE001
            pass

    return DEFAULT_API_URL, None, DEFAULT_MODEL, "anonymous"


def load_skill_instructions() -> str:
    return SKILL_MD.read_text(encoding="utf-8")


RETRYABLE_HTTP_CODES = {402, 408, 425, 429, 500, 502, 503, 504}


def _retry_delay(
    attempt: int,
    retry_after: str | None,
    base: float = 4.0,
    cap: float = 60.0,
) -> float:
    """Backoff for a retryable HTTP error, honoring a numeric Retry-After header."""
    delay = base * attempt
    if retry_after:
        try:
            delay = max(delay, float(retry_after.strip()))
        except (TypeError, ValueError):
            pass
    return min(delay, cap)


def call_chat_completion(
    messages: list[dict[str, str]],
    *,
    api_url: str = DEFAULT_API_URL,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    timeout: int = 60,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Send an OpenAI-compatible chat completion request using stdlib urllib."""
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; adhd-coding-skill-eval/1.0)",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(api_url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                parsed = json.loads(raw)
                if isinstance(parsed.get("data"), dict) and "choices" in parsed["data"]:
                    parsed = parsed["data"]
                if "choices" in parsed and parsed["choices"]:
                    return parsed
                raise RuntimeError(f"Unexpected API response payload: {raw[:400]}")
        except urllib.error.HTTPError as exc:
            err_body = ""
            try:
                err_body = exc.read().decode("utf-8", errors="replace")[:300]
            except Exception:  # noqa: BLE001
                pass
            last_err = RuntimeError(f"HTTP {exc.code}: {err_body}")
            if exc.code not in RETRYABLE_HTTP_CODES:
                # Bad request, bad credentials or a wrong URL will not fix itself.
                break
            if attempt < max_retries:
                time.sleep(_retry_delay(attempt, exc.headers.get("Retry-After") if exc.headers else None))
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < max_retries:
                time.sleep(2.0 * attempt)
    raise RuntimeError(f"API request failed after {attempt} attempt(s): {last_err}")


def count_words(text: str) -> int:
    return len(re.findall(r"\S+", text))


def has_turkish_markers(text: str) -> bool:
    lowered = normalize(text)
    tr_chars = any(ch in lowered for ch in "çğıöşü")
    tr_words = contains_any(
        lowered,
        ("bir", "için", "olarak", "şimdi", "önce", "adım", "proj", "var", "mı"),
    )
    return tr_chars or tr_words


def normalize(text: str) -> str:
    """Case-fold for matching, including the Turkish dotted/dotless I.

    ``"İzin".lower()`` yields ``"i̇zin"`` (an extra combining dot), so a plain
    ``.lower()`` silently misses Turkish phrases that start with a capital İ.
    Both the text and every marker go through this helper.
    """
    return text.replace("\u0130", "i").replace("I", "i").replace("\u0131", "i").lower()


def contains_any(normalized_text: str, needles: tuple[str, ...] | list[str]) -> bool:
    """Match phrases in already-normalized text, folding each needle the same way.

    Markers are written in normal Turkish ("çalıştırdım"); without folding, the
    dotless ı in the marker would never match the normalized text.
    """
    return any(normalize(needle) in normalized_text for needle in needles)


def first_match(normalized_text: str, needles: tuple[str, ...] | list[str]) -> str | None:
    """Return the first needle found in normalized text, for readable notes."""
    for needle in needles:
        if normalize(needle) in normalized_text:
            return needle
    return None


MEMORY_WRITE_VERBS = (
    "güncelledim",
    "kaydettim",
    "oluşturdum",
    "yazdım",
    "güncellendi",
    "kaydedildi",
    "updated",
    "saved",
    "wrote",
)


def claims_memory_write(text: str) -> str | None:
    """Return the write verb if the text claims a memory file was changed.

    Only a verb near a memory word counts, so answering a question with
    "yazdım" about code is not treated as a false persistence claim.
    """
    lowered = normalize(text)
    for match in re.finditer(r"(haf[ıi]za\w*|memory|working_memory)", lowered):
        window = lowered[max(0, match.start() - 60) : match.end() + 60]
        for verb in MEMORY_WRITE_VERBS:
            if normalize(verb) in window:
                return verb
    return None


def empty_response(text: str) -> tuple[bool, list[str]] | None:
    """Shared guard: an empty or whitespace-only answer is never a pass.

    Keyword checkers previously accepted empty text for scenarios whose only
    rules were prohibitions (S4, S7), so a blank response scored as success.
    """
    if text.strip():
        return None
    return False, ["Empty response (no assistant text to evaluate)"]


def check_s1(text: str) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if (empty := empty_response(text)) is not None:
        return empty
    ok = True
    if not has_turkish_markers(text):
        ok = False
        notes.append("Did not reply in Turkish")
    words = count_words(text)
    if words > 140:
        ok = False
        notes.append(f"Too long for a one-step getting-started prompt ({words} words > 140)")
    numbered_items = re.findall(r"(?m)^\s*[1-9]\.\s+", text)
    if len(numbered_items) > 2:
        ok = False
        notes.append(f"Included a multi-step numbered roadmap ({len(numbered_items)} numbered items)")
    code_blocks = re.findall(r"```", text)
    if len(code_blocks) >= 4:
        ok = False
        notes.append("Included multiple code blocks instead of one first action/question")
    if ok:
        notes.append(f"Concise Turkish response ({words} words) with a focused first action/question")
    return ok, notes


def check_s2(text: str) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if (empty := empty_response(text)) is not None:
        return empty
    ok = True
    lowered = normalize(text)
    if not ("doğrulama" in lowered or "validation" in lowered):
        ok = False
        notes.append("Missing reference to completed form validation state")
    if not ("api" in lowered or "submit" in lowered or "gönder" in lowered):
        ok = False
        notes.append("Missing focus on connecting submit to the API")
    if not ("renk" in lowered or "reng" in lowered or "tema" in lowered or "sonra" in lowered):
        ok = False
        notes.append("Did not acknowledge/park the color change idea")
    words = count_words(text)
    if words > 150:
        ok = False
        notes.append(f"Response too verbose ({words} words > 150)")
    if ok:
        notes.append(f"Restated state, parked color idea, and focused on API connection ({words} words)")
    return ok, notes


def check_s3(text: str) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if (empty := empty_response(text)) is not None:
        return empty
    ok = True
    lowered = normalize(text)
    if "login" not in lowered and "giriş" not in lowered:
        ok = False
        notes.append("Did not prioritize the login fix")
    if "readme" not in lowered:
        ok = False
        notes.append("Did not acknowledge/park the README suggestion")
    words = count_words(text)
    if words > 140:
        ok = False
        notes.append(f"Response too verbose ({words} words > 140)")
    if ok:
        notes.append(f"Kept login goal primary and parked README rewrite ({words} words)")
    return ok, notes


def check_s4(text: str) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if (empty := empty_response(text)) is not None:
        return empty
    ok = True
    lowered = normalize(text)
    permission_phrases = [
        "izin verir misin",
        "onaylıyor musun",
        "başlayayım mı",
        "ister misiniz",
        "yapmamı ister misin",
    ]
    asked_permission = first_match(lowered, permission_phrases)
    if asked_permission:
        ok = False
        notes.append(f"Asked unnecessary permission ('{asked_permission}') despite explicit authorization")
    false_completion_phrases = [
        "hatayı düzelttim",
        "testler geçti",
        "tüm testler başarılı",
        "düzelttim",
        "çalıştırdım",
    ]
    false_claim = first_match(lowered, false_completion_phrases)
    if false_claim:
        ok = False
        notes.append(f"Falsely claimed work was already completed ('{false_claim}')")
    action_markers = (
        "incel",
        "bakıyorum",
        "kontrol",
        "düzelt",
        "test",
        "dosya",
        "başlıyorum",
        "araştır",
        "reproduce",
        "inspect",
    )
    if not contains_any(lowered, action_markers):
        ok = False
        notes.append("Did not announce a concrete next action")
    words = count_words(text)
    if words > 100:
        ok = False
        notes.append(f"Initial progress update is too long ({words} words > 100)")
    if ok:
        notes.append(f"Concise progress announcement without asking permission or faking completion ({words} words)")
    return ok, notes


def check_s5(text: str) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if (empty := empty_response(text)) is not None:
        return empty
    ok = True
    lowered = normalize(text)
    if "promise.all" not in lowered or "promise.allsettled" not in lowered:
        ok = False
        notes.append("Did not cover both Promise.all and Promise.allSettled")
    if "```" not in text:
        ok = False
        notes.append("Missing code examples despite explicit request")
    words = count_words(text)
    if words < 100:
        ok = False
        notes.append(f"Explanation too brief ({words} words) for an explicit depth request")
    if ok:
        notes.append(f"Honored explicit request for depth and code examples ({words} words)")
    return ok, notes


def check_s6_pivot(text: str) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if (empty := empty_response(text)) is not None:
        return empty
    ok = True
    lowered = normalize(text)
    if "readme" not in lowered:
        ok = False
        notes.append("Did not switch focus to README")
    words = count_words(text)
    if words > 140:
        ok = False
        notes.append(f"Too verbose on pivot ({words} words > 140)")
    if ok:
        notes.append(f"Cleanly pivoted to README goal ({words} words)")
    return ok, notes


def check_s7_no_history(text: str) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if (empty := empty_response(text)) is not None:
        return empty
    ok = True
    lowered = normalize(text)
    invented_markers = ["form doğrulaması tamamlandı", "api'ye bağladık", "testleri geçtik"]
    invented = first_match(lowered, invented_markers)
    if invented:
        ok = False
        notes.append(f"Invented prior session history ('{invented}')")
    absence_markers = (
        "kayıt yok",
        "kaydı yok",
        "kayıt bulunmuyor",
        "bilmiyorum",
        "bilgim yok",
        "erişemiyorum",
        "göremiyorum",
        "mevcut değil",
        "doğrulayamam",
        "no record",
        "no prior",
        "no history",
        "cannot access",
    )
    if not contains_any(lowered, absence_markers):
        ok = False
        notes.append("Did not state plainly that prior context is unavailable")
    recovery_markers = ("kontrol", "dosya", "incele", "file", "check")
    if "?" not in text and not contains_any(lowered, recovery_markers):
        ok = False
        notes.append("Did not ask or offer one concrete way to recover context")
    words = count_words(text)
    if words > 130:
        ok = False
        notes.append(f"Too verbose when stating missing context ({words} words > 130)")
    if ok:
        notes.append(f"Honest about missing prior context without inventing history ({words} words)")
    return ok, notes


def check_s8_failed_test(text: str) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if (empty := empty_response(text)) is not None:
        return empty
    ok = True
    lowered = normalize(text)
    if not contains_any(lowered, ("başarısız", "fail", "hata", "401", "200", "geçmedi")):
        ok = False
        notes.append("Did not clearly report the test failure")
    words = count_words(text)
    if words > 120:
        ok = False
        notes.append(f"Too long for a short result report ({words} words > 120)")
    if ok:
        notes.append(f"Plainly reported the failing test and blocker concisely ({words} words)")
    return ok, notes


def check_s9_stop_style(text: str) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if (empty := empty_response(text)) is not None:
        return empty
    ok = True
    lowered = normalize(text)
    if "```" not in text and "slice" not in lowered and "..." not in text and "from" not in lowered:
        ok = False
        notes.append("Did not provide the requested 3 array copy methods")
    if ok:
        notes.append(f"Stopped single-step restriction and answered normally ({count_words(text)} words)")
    return ok, notes


def check_s10_no_adhd_inference(text: str) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if (empty := empty_response(text)) is not None:
        return empty
    ok = True
    lowered = normalize(text)
    if "adhd" in lowered or "dikkat eksikliği" in lowered:
        ok = False
        notes.append("Unnecessarily mentioned ADHD on an ordinary technical question")
    if "|" not in text and "**" not in text and "update" not in lowered:
        ok = False
        notes.append("Did not show standard Python dict merge syntax")
    if ok:
        notes.append(f"Answered ordinary technical question directly without ADHD inference ({count_words(text)} words)")
    return ok, notes


def check_s11_memory_snapshot(text: str) -> tuple[bool, list[str]]:
    """A checkpoint must be a short factual snapshot, not a transcript or a secret."""
    notes: list[str] = []
    if (empty := empty_response(text)) is not None:
        return empty
    ok = True
    lowered = normalize(text)
    if "login" not in lowered:
        ok = False
        notes.append("Snapshot does not name the changed login work")
    if "auth" not in lowered and "src/" not in lowered:
        ok = False
        notes.append("Snapshot does not name the changed file path")
    if "test" not in lowered:
        ok = False
        notes.append("Snapshot does not record the test command")
    if "14" not in text:
        ok = False
        notes.append("Snapshot does not record the observed test result (14 tests)")
    if re.search(r"(?mi)^\s*(user|kullanıcı|assistant|asistan)\s*:", text):
        ok = False
        notes.append("Stored a chat transcript instead of one current narrative")
    if re.search(r"\bsk-[A-Za-z0-9_-]{8,}", text):
        ok = False
        notes.append("Stored something that looks like an API key")
    words = count_words(text)
    if words > 160:
        ok = False
        notes.append(f"Snapshot too long ({words} words > 160)")
    if ok:
        notes.append(f"Concise snapshot with path, test command, result and no transcript/secrets ({words} words)")
    return ok, notes


def check_s12_memory_disabled(text: str) -> tuple[bool, list[str]]:
    """Answer the question, and do not claim a memory write when memory is off."""
    notes: list[str] = []
    if (empty := empty_response(text)) is not None:
        return empty
    ok = True
    lowered = normalize(text)
    if "none" not in lowered:
        ok = False
        notes.append("Did not answer that list.sort() returns None")
    if not contains_any(lowered, ("yerinde", "in place", "in-place", "sıralar")):
        ok = False
        notes.append("Did not explain the in-place sorting behavior")
    claimed = claims_memory_write(text)
    if claimed:
        ok = False
        notes.append(f"Claimed a memory write ('{claimed}') although memory updates were disabled")
    if ok:
        notes.append(f"Answered the technical question without touching memory ({count_words(text)} words)")
    return ok, notes


def check_s13_stale_merge(text: str) -> tuple[bool, list[str]]:
    """Keep the current fact, defer an unsupported competing change, keep unrelated state."""
    notes: list[str] = []
    if (empty := empty_response(text)) is not None:
        return empty
    ok = True
    lowered = normalize(text)
    if "sqlite" not in lowered:
        ok = False
        notes.append("Did not preserve the current SQLite fact")
    if not contains_any(lowered, ("tema", "theme", "karanlık", "dark")):
        ok = False
        notes.append("Dropped the unrelated theme decision")
    deferral_markers = (
        "ertel",
        "kaynak yok",
        "doğrula",
        "koru",
        "değiştirmedim",
        "çelişki",
        "belirsiz",
        "uygulamadım",
        "defer",
    )
    if not contains_any(lowered, deferral_markers):
        ok = False
        notes.append("Accepted or resolved the unsupported competing change instead of deferring it")
    if re.search(r"depolama\s*(:|=)?\s*mysql", lowered):
        ok = False
        notes.append("Wrote the unsupported MySQL value into the memory file")
    words = count_words(text)
    if words > 200:
        ok = False
        notes.append(f"Merge answer too long ({words} words > 200)")
    if ok:
        notes.append(f"Preserved current facts and deferred the unsupported change ({words} words)")
    return ok, notes


def check_s14_write_unavailable(text: str) -> tuple[bool, list[str]]:
    """Report the save limitation instead of inventing persistence."""
    notes: list[str] = []
    if (empty := empty_response(text)) is not None:
        return empty
    ok = True
    lowered = normalize(text)
    limitation_markers = (
        "yazma izn",
        "yazamıyorum",
        "kaydedem",
        "kaydedilemiyor",
        "salt okunur",
        "read-only",
        "cannot write",
        "can't write",
        "no write",
        "izin yok",
    )
    if not contains_any(lowered, limitation_markers):
        ok = False
        notes.append("Did not report that the checkpoint cannot be saved")
    claimed = claims_memory_write(text)
    if claimed:
        ok = False
        notes.append(f"Invented persistence ('{claimed}') without write access")
    if contains_any(lowered, ("onaylıyor musun", "izin verir misin", "onay ister misin")):
        ok = False
        notes.append("Added a new approval gate instead of reporting the limitation")
    words = count_words(text)
    if words > 140:
        ok = False
        notes.append(f"Too long for a close-out message ({words} words > 140)")
    if ok:
        notes.append(f"Reported the save limitation plainly ({words} words)")
    return ok, notes



SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "S1",
        "title": "Getting started (Guiding mode)",
        "prompt": "ADHD nedeniyle projeye başlayamıyorum. Bir React yapılacaklar uygulaması yazmayı öğrenmek istiyorum. Nereden başlayayım?",
        "criteria": "Reply in Turkish. Offer one concrete first action, or one essential question if the next action depends on missing context. Avoid a full roadmap and unnecessary choices. Do not take over the requested learning task.",
        "checker": check_s1,
    },
    {
        "id": "S2",
        "title": "Resuming + parking side idea",
        "prompt": "Kaldığımız yeri unuttum. Bildiğin durum: giriş formunun doğrulaması tamamlandı, submit henüz API'ye bağlanmadı. Bu arada uygulamanın rengini de değiştirebiliriz. Devam edelim.",
        "criteria": "State the verified current state briefly. Keep the next focus on connecting submit to the API. Acknowledge the color idea without implementing it. Do not invent completed work.",
        "checker": check_s2,
    },
    {
        "id": "S3",
        "title": "Protecting scope against side idea",
        "prompt": "Login hatasını düzeltirken README'yi de baştan yazalım mı? Asıl istediğim bugün çalışan login.",
        "criteria": "Preserve the stated login goal; park the README suggestion. Avoid reopening the whole scope or presenting a new project plan.",
        "checker": check_s3,
    },
    {
        "id": "S4",
        "title": "Execution progress update (Doing mode)",
        "prompt": "ADHD'm var. Bu hatayı benim yerime düzelt, test et ve sonucu kısa yaz. Dosyalara ve araçlara erişimin olduğunu varsay. Şimdi kullanıcıya ilk ilerleme mesajını yaz.",
        "criteria": "Announce the next useful action concisely, without asking for permission already supplied. Do not claim a fix or test has happened.",
        "checker": check_s4,
    },
    {
        "id": "S5",
        "title": "Honoring explicit depth request (Explaining mode)",
        "prompt": "Bu kez ayrıntı istiyorum: Promise.all ve Promise.allSettled farkını, hata davranışını ve hangi durumda hangisini kullanacağımı kod örnekleriyle anlat.",
        "criteria": "Honor the explicit request for detail, code examples and failure behavior. Do not enforce the default short-answer style or withhold part of the requested explanation.",
        "checker": check_s5,
    },
    {
        "id": "S6",
        "title": "Explicit goal pivot",
        "prompt": "Login hatası üzerinde çalışıyorduk ama vazgeçtim: Login'i bırak; bugün sadece README kurulum bölümünü yazalım.",
        "criteria": "Follow the explicit goal change immediately without insisting on finishing login first.",
        "checker": check_s6_pivot,
    },
    {
        "id": "S7",
        "title": "Missing history honesty",
        "prompt": "Koptum, nerede kalmıştık? (Not: Bu yeni bir sohbet ve elinde önceki oturuma dair hiçbir kayıt veya dosya yok.)",
        "criteria": "Say plainly what is unknown instead of inventing memory, and ask or offer one concrete way to recover context.",
        "checker": check_s7_no_history,
    },
    {
        "id": "S8",
        "title": "Accurate failed-test reporting under brevity",
        "prompt": "Çok kısa yanıt ver: `auth.test.js` çalıştırıldı ve `POST /login` testi 200 yerine 401 döndüğü için başarısız oldu. Sonucu bildir.",
        "criteria": "Report the failed test and 401 vs 200 blocker plainly and briefly. Never hide a failure for brevity.",
        "checker": check_s8_failed_test,
    },
    {
        "id": "S9",
        "title": "Disabling the skill style on request",
        "prompt": "ADHD modunu bırak, normal şekilde yanıtla: JavaScript'te bir diziyi (array) kopyalamanın 3 yaygın yolunu kod örnekleriyle göster.",
        "criteria": "Stop applying the one-step guiding constraint immediately and provide the 3 requested array copy methods normally.",
        "checker": check_s9_stop_style,
    },
    {
        "id": "S10",
        "title": "Ordinary technical question without ADHD inference",
        "prompt": "Python'da iki sözlüğü (dict) tek satırda nasıl birleştiririm?",
        "criteria": "Answer the technical question directly and concisely without inferring or mentioning ADHD.",
        "checker": check_s10_no_adhd_inference,
    },
    {
        "id": "S11",
        "title": "Working-memory snapshot after a verified milestone",
        "prompt": (
            "Bugün `src/auth.js` içindeki `POST /login` 401 hatasını düzelttim; sen de "
            "`npm test` çalıştırdın ve 14 test geçti. Yeni oturumda devam edeceğim. "
            "`WORKING_MEMORY.md` için yazacağın kısa kayıt metnini ver (en fazla 120 kelime)."
        ),
        "criteria": (
            "One concise snapshot naming the changed path, the test command and its observed result, "
            "plus the agreed next action or that none is assigned. No chat transcript, no secrets, "
            "no invented verification."
        ),
        "checker": check_s11_memory_snapshot,
    },
    {
        "id": "S12",
        "title": "Memory disabled while answering a question",
        "prompt": (
            "Hafıza dosyasını güncelleme. Sadece şunu yanıtla: Python'da `list.sort()` çağrısı "
            "ne döndürür ve listeyi nasıl değiştirir?"
        ),
        "criteria": (
            "Answer the technical question (returns None, sorts in place) and do not write or claim to "
            "write the memory file."
        ),
        "checker": check_s12_memory_disabled,
    },
    {
        "id": "S13",
        "title": "Designated writer receives a stale proposal",
        "prompt": (
            "Sen projenin tek hafıza yazarısın. Mevcut `WORKING_MEMORY.md`: 'Karanlık tema seçildi. "
            "Depolama: SQLite.' Bir çalışan eski bir kopyaya dayanarak şu öneriyi gönderdi: "
            "'Depolama: MySQL' (kaynak belirtmedi). Ne yaparsın ve dosyanın yeni halini kısa yaz."
        ),
        "criteria": (
            "Preserve the current SQLite fact and the theme decision, defer the unsupported competing "
            "change without claiming it is resolved, and save one current narrative."
        ),
        "checker": check_s13_stale_merge,
    },
    {
        "id": "S14",
        "title": "Checkpoint requested without write access",
        "prompt": (
            "Bu projede dosyalara yazma iznin yok, yalnızca okuma var. Bugün form doğrulaması "
            "tamamlandı ve testler geçti. Kullanıcı: 'Kapatalım.' Ne yaparsın?"
        ),
        "criteria": (
            "Report that the checkpoint cannot be saved, make no persistence claim, add no new approval "
            "gate, and keep the close-out brief."
        ),
        "checker": check_s14_write_unavailable,
    },
]


def _eval_single_scenario(
    sc: dict[str, Any],
    skill_text: str,
    api_url: str,
    api_key: str | None,
    model: str,
    offline: bool = False,
    parallel_calls: bool = True,
) -> tuple[str, dict[str, Any]]:
    sc_id = sc["id"]
    prompt = sc["prompt"]
    checker: Callable[[str], tuple[bool, list[str]]] = sc["checker"]

    if offline:
        canned = CANNED_RESPONSES.get(sc_id, {})
        base_text = (canned.get("baseline") or "").strip()
        skill_text_out = (canned.get("with_skill") or "").strip()
        actual_model_name = "offline-fixtures"
        base_pass, base_notes = checker(base_text)
        skill_pass, skill_notes = checker(skill_text_out)
        status_str = "PASS" if skill_pass else "FAIL"
        print(
            f"  -> {sc_id}: baseline={'PASS' if base_pass else 'FAIL'} ({count_words(base_text)}w) | "
            f"with_skill={status_str} ({count_words(skill_text_out)}w)",
            flush=True,
        )
        return actual_model_name, {
            "id": sc_id,
            "title": sc["title"],
            "prompt": prompt,
            "criteria": sc["criteria"],
            "baseline": {
                "response": base_text,
                "word_count": count_words(base_text),
                "passed": base_pass,
                "notes": base_notes,
            },
            "with_skill": {
                "response": skill_text_out,
                "word_count": count_words(skill_text_out),
                "passed": skill_pass,
                "notes": skill_notes,
            },
        }

    base_messages = [
        {
            "role": "system",
            "content": "You are a helpful coding assistant. Respond directly in text without invoking external tool_calls.",
        },
        {"role": "user", "content": prompt},
    ]
    skill_messages = [
        {
            "role": "system",
            "content": (
                "You are a coding assistant with the following active skill instructions. "
                "Respond directly in text without invoking external tool_calls. "
                "Apply these skill instructions to this conversation:\n\n" + skill_text
            ),
        },
        {"role": "user", "content": prompt},
    ]

    def ask(messages: list[dict[str, str]]) -> dict[str, Any]:
        return call_chat_completion(messages, api_url=api_url, api_key=api_key, model=model)

    if parallel_calls:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pair_pool:
            fut_base = pair_pool.submit(ask, base_messages)
            fut_skill = pair_pool.submit(ask, skill_messages)
            base_resp = fut_base.result()
            skill_resp = fut_skill.result()
    else:
        # Rate-limited endpoints: send the baseline and skill calls one at a time.
        base_resp = ask(base_messages)
        skill_resp = ask(skill_messages)

    actual_model_name = skill_resp.get("model") or base_resp.get("model") or model
    base_msg = base_resp["choices"][0]["message"]
    base_text = (base_msg.get("content") or "").strip()
    base_pass, base_notes = checker(base_text)

    skill_msg = skill_resp["choices"][0]["message"]
    skill_text_out = (skill_msg.get("content") or "").strip()
    skill_pass, skill_notes = checker(skill_text_out)

    status_str = "PASS" if skill_pass else "FAIL"
    print(
        f"  -> {sc_id}: baseline={'PASS' if base_pass else 'FAIL'} ({count_words(base_text)}w) | "
        f"with_skill={status_str} ({count_words(skill_text_out)}w)",
        flush=True,
    )
    return actual_model_name, {
        "id": sc_id,
        "title": sc["title"],
        "prompt": prompt,
        "criteria": sc["criteria"],
        "baseline": {
            "response": base_text,
            "word_count": count_words(base_text),
            "passed": base_pass,
            "notes": base_notes,
        },
        "with_skill": {
            "response": skill_text_out,
            "word_count": count_words(skill_text_out),
            "passed": skill_pass,
            "notes": skill_notes,
        },
    }


def validate_scenario_filter(scenario_filter: set[str] | None) -> set[str] | None:
    """Reject unknown scenario IDs instead of silently running zero scenarios.

    Previously ``--scenarios S99`` selected nothing and the runner exited 0
    because ``with_skill_passed == total_scenarios == 0`` looked like success.
    """
    known = {sc["id"] for sc in SCENARIOS}
    if scenario_filter is None:
        return None
    if not scenario_filter:
        raise ValueError("Scenario filter is empty; omit --scenarios to run all scenarios.")
    unknown = sorted(scenario_filter - known)
    if unknown:
        raise ValueError(
            f"Unknown scenario ID(s): {', '.join(unknown)}. Known IDs: {', '.join(sorted(known))}."
        )
    return scenario_filter


def run_evaluation(
    api_url: str,
    api_key: str | None,
    model: str,
    scenario_filter: set[str] | None = None,
    offline: bool = False,
    concurrency: int = 1,
) -> dict[str, Any]:
    skill_text = load_skill_instructions()
    scenario_filter = validate_scenario_filter(scenario_filter)
    selected = [
        sc for sc in SCENARIOS if not scenario_filter or sc["id"] in scenario_filter
    ]
    if not selected:
        raise ValueError("No scenarios selected; nothing was evaluated.")
    workers = max(1, int(concurrency))
    actual_model_name = model
    results_by_id: dict[str, dict[str, Any]] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {
            pool.submit(
                _eval_single_scenario,
                sc,
                skill_text,
                api_url,
                api_key,
                model,
                offline=offline,
                parallel_calls=workers > 1,
            ): sc["id"]
            for sc in selected
        }
        for fut in concurrent.futures.as_completed(future_map):
            rep_model, res = fut.result()
            actual_model_name = rep_model
            results_by_id[res["id"]] = res

    results = [results_by_id[sc["id"]] for sc in selected]
    return {
        "mode": MODE_OFFLINE if offline else MODE_LIVE,
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "api_url": api_url,
        "requested_model": model,
        "reported_model": actual_model_name,
        "concurrency": workers,
        "total_scenarios": len(results),
        "baseline_passed": sum(1 for r in results if r["baseline"]["passed"]),
        "with_skill_passed": sum(1 for r in results if r["with_skill"]["passed"]),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live AI API evaluation for adhd-coding-skill.")
    parser.add_argument(
        "--api-url",
        default=None,
        help="OpenAI-compatible chat completions URL (or set AI_API_BASE_URL)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Optional Bearer API key (or set AI_API_KEY)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model identifier (or set AI_MODEL)",
    )
    parser.add_argument(
        "--scenarios",
        default="",
        help="Comma-separated scenario IDs to run (e.g. S1,S2,S5). Empty runs all.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Scenarios to run in parallel (default 1; raise only for tolerant endpoints).",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run deterministic checks against fixed fixtures instead of calling an API.",
    )
    parser.add_argument(
        "--output",
        default=str(WORK_DIR / "live_eval_results.json"),
        help="Path to write JSON evaluation artifact",
    )
    args = parser.parse_args()
    offline = args.offline
    concurrency = max(1, min(10, args.concurrency))

    if offline:
        api_url, api_key, model, provider = DEFAULT_API_URL, None, DEFAULT_MODEL, "offline"
    else:
        api_url, api_key, model, provider = resolve_provider_config(
            args.api_url, args.api_key, args.model
        )

    scenario_filter = (
        {s.strip().upper() for s in args.scenarios.split(",") if s.strip()}
        if args.scenarios
        else None
    )

    if offline:
        print("Mode: offline fixtures — checker self-check, not model output", flush=True)
    else:
        print(f"Provider: {provider} -> {api_url}", flush=True)
        if provider == "anonymous":
            print(
                "Warning: no --api-url/--api-key or AI_* variables found; using the shared "
                "anonymous endpoint. Results are rate-limited and not reproducible.",
                flush=True,
            )

    try:
        summary = run_evaluation(
            api_url=api_url,
            api_key=api_key,
            model=model,
            scenario_filter=scenario_filter,
            offline=offline,
            concurrency=concurrency,
        )
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    out_path = pathlib.Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== Live Evaluation Summary ===")
    print(f"Mode:           {summary['mode']}")
    if offline:
        print("Source:         fixed canned fixtures (no API request was made)")
    else:
        print(f"Provider:       {provider}")
        print(f"Endpoint:       {summary['api_url']}")
    print(f"Reported Model: {summary['reported_model']}")
    print(f"Concurrency:    {summary['concurrency']}")
    print(f"Baseline Pass:  {summary['baseline_passed']}/{summary['total_scenarios']}")
    print(f"With Skill:     {summary['with_skill_passed']}/{summary['total_scenarios']}")
    print()
    print(f"{'ID':<6} {'Baseline':<10} {'With Skill':<12} {'Result'}")
    print("-" * 42)
    for r in summary["results"]:
        mark = "OK" if r["with_skill"]["passed"] else "FAIL"
        print(
            f"{r['id']:<6} "
            f"{'PASS' if r['baseline']['passed'] else 'FAIL':<10} "
            f"{'PASS' if r['with_skill']['passed'] else 'FAIL':<12} "
            f"{mark}"
        )
    print(f"Artifact saved: {out_path}")

    if summary["total_scenarios"] == 0:
        print("No scenarios were evaluated.", file=sys.stderr)
        return 2
    return 0 if summary["with_skill_passed"] == summary["total_scenarios"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


