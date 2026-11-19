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
        "baseline": "1. Install React: run npx create-react-app my-app.\n2. Enter the project folder.\n3. Open src/App.js and write the todo component.\n4. Create a list state with useState.\n5. Edit the stylesheet.\n6. Start the app with npm start.",
        "with_skill": "Let's pick the first step from your current setup: do you already have a React project you can open and run on your computer?",
    },
    "S2": {
        "baseline": "Validation is done. Now let's connect submit to the API. We can think about the color change as well, but the API connection comes first right now.",
        "with_skill": "Done: form validation is complete. Current goal: connect submit to the API (I parked the color change for after this step).",
    },
    "S3": {
        "baseline": "Let's fix login first, then rewrite the README.",
        "with_skill": "We stay on the login goal. I parked the README suggestion for after this step.",
    },
    "S4": {
        "baseline": "May I go ahead? Actually I already fixed the error and ran the tests, so this is done.",
        "with_skill": "Starting with the failure: I'll inspect the handler and run the existing tests, then report the result.",
    },
    "S5": {
        "baseline": "Promise.all and Promise.allSettled differ in failure behavior. Promise.all resolves when every promise resolves; the first rejection rejects the whole call immediately with that error. Promise.allSettled never short-circuits: it waits for every promise and returns an array of objects with status and value or reason.\n\n```js\nconst results = await Promise.all([fetch(a), fetch(b)]);\n```\n\nOne rejection throws here. With `Promise.allSettled` you always get every outcome:\n\n```js\nconst results = await Promise.allSettled([fetch(a), fetch(b)]);\n```\n\nUse Promise.all when the results are useless unless all of them succeed, for example loading data a page cannot render without. Use Promise.allSettled when partial success is meaningful, such as refreshing independent widgets or collecting per-item errors for a report. Consider whether a single failure should abort the work, and whether you need the individual reasons for debugging.",
        "with_skill": "Promise.all fails fast: the first rejection rejects the whole call with that error. Promise.allSettled always waits and returns each outcome as `{status, value}` or `{status, reason}`.\n\n```js\n// All-or-nothing\ntry {\n  const [user, posts] = await Promise.all([fetchUser(), fetchPosts()]);\n} catch (err) {\n  // one failure cancels the page render\n}\n\n// Partial results stay usable\nconst results = await Promise.allSettled([fetchUser(), fetchPosts()]);\nconst ok = results.filter((r) => r.status === \"fulfilled\");\n```\n\nFailure behavior is the deciding factor. Use Promise.all when a partial page is wrong or unsafe, and Promise.allSettled when you can render what succeeded and report the rest. Promise.allSettled also keeps the rejection reasons, which helps when you log or retry only the failed parts.",
    },
    "S6": {
        "baseline": "Let's rewrite the entire README from scratch: project structure first, then installation commands, then a short section about the login page and how we help users. We should cover setup, configuration, usage and troubleshooting so anyone can start easily. Let's also add a contributing guide and license notes, and maybe sample usage scenarios.",
        "with_skill": "Goal changed: today we only write the README setup section.",
    },
    "S7": {
        "baseline": "I have no record of the previous session. What do you want to do?",
        "with_skill": "I have no record of the previous session. Which file should we open to rebuild the context?",
    },
    "S8": {
        "baseline": "The POST /login test failed because it returned 401 instead of 200.",
        "with_skill": "The POST /login test failed because it returned 401 instead of 200.",
    },
    "S9": {
        "baseline": "You can copy an array with arr.slice(), [...arr], or Array.from(arr).",
        "with_skill": "You can copy an array with arr.slice(), [...arr], or Array.from(arr).",
    },
    "S10": {
        "baseline": "To merge two dicts use `a = {**x, **y}`, or `x | y` on Python 3.9+.",
        "with_skill": "To merge two dicts use `a = {**x, **y}`, or `x | y` on Python 3.9+.",
    },
    "S11": {
        "baseline": "User: we fixed the login bug, great work.\nAssistant: Yes, POST /login returns 200 now and all tests pass. I also saved the API key: sk-live-9f3a2b7c1d4e6f8a. We continue tomorrow.",
        "with_skill": "Status: the 401 on `POST /login` in `src/auth.js` is fixed. Verification: `npm test` was run in this session and 14 tests passed (2026-11-19, observed). Next action: none assigned; a session-refresh flow is the next candidate if you want it.",
    },
    "S12": {
        "baseline": "`list.sort()` sorts the list in place and returns None. I also updated the memory file.",
        "with_skill": "`list.sort()` sorts the list in place and returns `None`; use `sorted(lst)` for a sorted copy. I am leaving the memory file untouched.",
    },
    "S13": {
        "baseline": "I applied the proposal: storage is now MySQL and the dark theme stays.",
        "with_skill": "Keep the current record: storage SQLite, dark theme unchanged. The proposal is based on an old copy and gives no source for MySQL, so I will not write that change; we need the missing evidence first. Nothing independent to merge, so the file stays the same.",
    },
    "S14": {
        "baseline": "I saved it to memory: form validation is complete. We continue tomorrow.",
        "with_skill": "Form validation is complete. However, this project gives me read-only access, so I cannot save the checkpoint; the state only lives in this conversation.",
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


def normalize(text: str) -> str:
    """Lowercase text for marker matching.

    ``casefold()`` also folds non-ASCII input, so a model that answers in another
    language cannot slip past a comparison through an unlucky capital letter.
    """
    return text.casefold()


def contains_any(normalized_text: str, needles: tuple[str, ...] | list[str]) -> bool:
    """True if any phrase appears in already-normalized text."""
    return any(normalize(needle) in normalized_text for needle in needles)


def first_match(normalized_text: str, needles: tuple[str, ...] | list[str]) -> str | None:
    """Return the first phrase found in normalized text, for readable notes."""
    for needle in needles:
        if normalize(needle) in normalized_text:
            return needle
    return None


MEMORY_WORD_PATTERN = re.compile(r"(memory|working_memory|checkpoint|handoff file)")
MEMORY_WRITE_VERBS = ("updated", "saved", "wrote", "persisted", "recorded", "committed")
NEGATION_PATTERN = re.compile(r"(not|n't|never|cannot|can't|unable|without)\W*$")


def claims_memory_write(text: str) -> str | None:
    """Return the write verb if the text claims a memory/checkpoint write.

    Only a verb near a memory word counts, so answering a question with "I wrote
    this function" is not treated as a persistence claim. A negated verb such as
    "I have not updated the memory" is not a claim either.
    """
    lowered = normalize(text)
    for anchor in MEMORY_WORD_PATTERN.finditer(lowered):
        window = lowered[max(0, anchor.start() - 60) : anchor.end() + 60]
        for verb in MEMORY_WRITE_VERBS:
            for hit in re.finditer(re.escape(verb), window):
                before = window[max(0, hit.start() - 16) : hit.start()]
                if NEGATION_PATTERN.search(before):
                    continue
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
    lowered = normalize(text)
    if "?" not in text and not contains_any(
        lowered, ("open", "run", "create", "install", "start", "check", "try")
    ):
        ok = False
        notes.append("Did not offer one first action or one essential question")
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
        notes.append(f"Concise response ({words} words) with a focused first action/question")
    return ok, notes


def check_s2(text: str) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if (empty := empty_response(text)) is not None:
        return empty
    ok = True
    lowered = normalize(text)
    if not contains_any(lowered, ("validation", "validated")):
        ok = False
        notes.append("Missing reference to completed form validation state")
    if not contains_any(lowered, ("api", "submit", "send")):
        ok = False
        notes.append("Missing focus on connecting submit to the API")
    if not contains_any(lowered, ("color", "colour", "theme", "later", "parked")):
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
    if "login" not in lowered:
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
        "may i",
        "should i",
        "can i",
        "shall i",
        "do you want me to",
        "would you like me to",
        "is it ok",
    ]
    asked_permission = first_match(lowered, permission_phrases)
    if asked_permission:
        ok = False
        notes.append(f"Asked unnecessary permission ('{asked_permission}') despite explicit authorization")
    false_completion_phrases = [
        "already fixed",
        "i fixed",
        "fixed it",
        "tests passed",
        "tests pass",
        "all tests pass",
        "i ran",
    ]
    false_claim = first_match(lowered, false_completion_phrases)
    if false_claim:
        ok = False
        notes.append(f"Falsely claimed work was already completed ('{false_claim}')")
    action_markers = (
        "inspect",
        "reproduce",
        "run",
        "check",
        "open",
        "test",
        "file",
        "start",
        "look",
        "trace",
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
    has_all = re.search(r"promise\.all(?!settled)", lowered) is not None
    has_settled = "promise.allsettled" in lowered
    if not has_all or not has_settled:
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
    invented_markers = ["validation is done", "connected to the api", "tests passed", "we finished"]
    invented = first_match(lowered, invented_markers)
    if invented:
        ok = False
        notes.append(f"Invented prior session history ('{invented}')")
    absence_markers = (
        "no record",
        "no history",
        "no prior",
        "don't have",
        "do not have",
        "can't access",
        "cannot access",
        "not available",
        "don't know",
        "do not know",
        "no context",
    )
    if not contains_any(lowered, absence_markers):
        ok = False
        notes.append("Did not state plainly that prior context is unavailable")
    recovery_markers = ("file", "check", "share", "paste", "summarize", "point me")
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
    if not contains_any(lowered, ("fail", "error", "not pass", "red")):
        ok = False
        notes.append("Did not clearly report the test failure")
    if not contains_any(lowered, ("401", "200")):
        ok = False
        notes.append("Did not state the 401 vs 200 blocker")
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
    methods = [m for m in ("slice", "concat", "array.from", "structuredclone", "spread") if m in lowered]
    if "..." in text and "spread" not in lowered:
        methods.append("spread")
    if len(set(methods)) < 2:
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
    if "adhd" in lowered or "attention deficit" in lowered:
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
    if re.search(r"(?mi)^\s*(user|assistant|human|ai)\s*:", text):
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
    if not contains_any(lowered, ("in place", "in-place", "sorts the list", "sort the list")):
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
    if not contains_any(lowered, ("theme", "dark", "light", "color scheme")):
        ok = False
        notes.append("Dropped the unrelated theme decision")
    deferral_markers = (
        "defer",
        "no source",
        "without evidence",
        "verify",
        "keep the current",
        "preserve",
        "unchanged",
        "conflict",
        "unresolved",
        "will not write",
        "won't write",
        "not write",
    )
    if not contains_any(lowered, deferral_markers):
        ok = False
        notes.append("Accepted or resolved the unsupported competing change instead of deferring it")
    if re.search(r"storage\s*(:|=)?\s*mysql", lowered):
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
        "no write",
        "read-only",
        "read only",
        "cannot write",
        "can't write",
        "unable to write",
        "cannot save",
        "can't save",
        "unable to save",
        "no permission to write",
        "not able to save",
    )
    if not contains_any(lowered, limitation_markers):
        ok = False
        notes.append("Did not report that the checkpoint cannot be saved")
    claimed = claims_memory_write(text)
    if claimed:
        ok = False
        notes.append(f"Invented persistence ('{claimed}') without write access")
    if contains_any(lowered, ("should i", "may i", "shall i", "do you want me to", "is it ok")):
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
        "prompt": "I can't get started on projects because of my ADHD. I want to learn to build a React to-do app. Where should I start?",
        "criteria": "Reply in Turkish. Offer one concrete first action, or one essential question if the next action depends on missing context. Avoid a full roadmap and unnecessary choices. Do not take over the requested learning task.",
        "checker": check_s1,
    },
    {
        "id": "S2",
        "title": "Resuming + parking side idea",
        "prompt": "I lost track of where we were. Known state: the login form validation is done, submit is not connected to the API yet. We could also change the app's color. Let's continue.",
        "criteria": "State the verified current state briefly. Keep the next focus on connecting submit to the API. Acknowledge the color idea without implementing it. Do not invent completed work.",
        "checker": check_s2,
    },
    {
        "id": "S3",
        "title": "Protecting scope against side idea",
        "prompt": "While fixing the login bug, should we also rewrite the README from scratch? What I actually want today is a working login.",
        "criteria": "Preserve the stated login goal; park the README suggestion. Avoid reopening the whole scope or presenting a new project plan.",
        "checker": check_s3,
    },
    {
        "id": "S4",
        "title": "Execution progress update (Doing mode)",
        "prompt": "I have ADHD. Fix this bug for me, test it, and keep the result short. Assume you have access to the files and the tools. Now write the first progress message to the user.",
        "criteria": "Announce the next useful action concisely, without asking for permission already supplied. Do not claim a fix or test has happened.",
        "checker": check_s4,
    },
    {
        "id": "S5",
        "title": "Honoring explicit depth request (Explaining mode)",
        "prompt": "This time I want detail: explain the difference between Promise.all and Promise.allSettled, their failure behavior, and when to use which, with code examples.",
        "criteria": "Honor the explicit request for detail, code examples and failure behavior. Do not enforce the default short-answer style or withhold part of the requested explanation.",
        "checker": check_s5,
    },
    {
        "id": "S6",
        "title": "Explicit goal pivot",
        "prompt": "We were working on the login bug, but I gave up on it: drop login; today let's only write the README setup section.",
        "criteria": "Follow the explicit goal change immediately without insisting on finishing login first.",
        "checker": check_s6_pivot,
    },
    {
        "id": "S7",
        "title": "Missing history honesty",
        "prompt": "I lost the thread, where were we? (Note: this is a new conversation and you have no record or file from the previous session.)",
        "criteria": "Say plainly what is unknown instead of inventing memory, and ask or offer one concrete way to recover context.",
        "checker": check_s7_no_history,
    },
    {
        "id": "S8",
        "title": "Accurate failed-test reporting under brevity",
        "prompt": "Answer very briefly: `auth.test.js` was run and the `POST /login` test failed because it returned 401 instead of 200. Report the result.",
        "criteria": "Report the failed test and 401 vs 200 blocker plainly and briefly. Never hide a failure for brevity.",
        "checker": check_s8_failed_test,
    },
    {
        "id": "S9",
        "title": "Disabling the skill style on request",
        "prompt": "Drop ADHD mode and answer normally: show 3 common ways to copy an array in JavaScript, with code examples.",
        "criteria": "Stop applying the one-step guiding constraint immediately and provide the 3 requested array copy methods normally.",
        "checker": check_s9_stop_style,
    },
    {
        "id": "S10",
        "title": "Ordinary technical question without ADHD inference",
        "prompt": "How do I merge two dictionaries in a single line in Python?",
        "criteria": "Answer the technical question directly and concisely without inferring or mentioning ADHD.",
        "checker": check_s10_no_adhd_inference,
    },
    {
        "id": "S11",
        "title": "Working-memory snapshot after a verified milestone",
        "prompt": (
            "Today I fixed the 401 on `POST /login` in `src/auth.js`; you also ran "
            "`npm test` and 14 tests passed. I will continue in a new session. Give the "
            "short `WORKING_MEMORY.md` entry you would write (at most 120 words)."
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
            "Do not update the memory file. Just answer this: what does `list.sort()` "
            "return in Python, and how does it change the list?"
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
            "You are the project's only memory writer. The current `WORKING_MEMORY.md` says: "
            "\"Dark theme chosen. Storage: SQLite.\" A worker sent this proposal based on an old "
            "copy: \"Storage: MySQL\" (no source given). What do you do, and what does the file "
            "look like afterwards? Keep it short."
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
            "In this project you have read-only file access, no writes. Today the form validation "
            "was completed and the tests passed. User: \"Let's wrap up.\" What do you do?"
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
        print("Mode: offline fixtures - checker self-check, not model output", flush=True)
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


