#!/usr/bin/env python3
"""
Claude API-driven daily dashboard updater, with free open-model fallback.

Runs inside GitHub Actions (or anywhere with ANTHROPIC_API_KEY and/or
PUTER_TOKEN set). Calls Anthropic's Messages API with the prompt in
scripts/prompt_template.md, gives Claude the web_search server tool, and
writes back the refreshed HTML.

If the Claude API call fails (rate limit, outage, auth error, etc.) or
returns something that doesn't look like a valid dashboard, the script
falls back to web-grounded open models served for free via Puter.com's
OpenAI-compatible API (Perplexity Sonar family) using the exact same
prompt, so the dashboard still gets its market commentary/news/portfolio
analysis for the day instead of going stale.

No browser, no laptop, no Cowork — purely server-to-server.

Environment:
  ANTHROPIC_API_KEY  (optional*) — your Anthropic API key
  CLAUDE_MODEL       (optional)  — defaults to claude-sonnet-4-6
  MAX_TOKENS         (optional)  — defaults to 32000
  MAX_WEB_SEARCHES   (optional)  — defaults to 12

  PUTER_TOKEN        (optional*) — free Puter.com token, used for fallback
  FALLBACK_MODELS    (optional)  — comma-separated Puter model ids, defaults
                                    to "perplexity/sonar-pro,
                                    perplexity/sonar-reasoning-pro,
                                    perplexity/sonar"
  FALLBACK_MAX_TOKENS (optional) — defaults to 8000

  * at least one of ANTHROPIC_API_KEY / PUTER_TOKEN must be set.

Exit codes:
  0  success, index.html written (by Claude or a fallback model)
  1  config error (no credentials, missing files)
  5  every provider (Claude + all fallbacks) failed — see logs
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx

try:
    import anthropic as _anthropic_pkg
    from anthropic import Anthropic, APIError
except ImportError:
    _anthropic_pkg = None
    Anthropic = None
    APIError = None


def _dump_exception(e: Exception) -> None:
    """Verbose error dump for any API exception — print everything useful."""
    sys.stderr.write(f"\n--- API CALL FAILED ---\n")
    sys.stderr.write(f"Exception class: {e.__class__.__module__}.{e.__class__.__name__}\n")
    sys.stderr.write(f"Exception str:   {str(e)}\n")
    for attr in ("status_code", "message", "type"):
        if hasattr(e, attr):
            sys.stderr.write(f"  .{attr}: {getattr(e, attr)!r}\n")
    body = getattr(e, "body", None)
    if body is not None:
        sys.stderr.write(f"  .body: {body!r}\n")
    resp = getattr(e, "response", None)
    if resp is not None:
        sys.stderr.write(f"  .response: {resp!r}\n")
        text = getattr(resp, "text", None)
        if text:
            sys.stderr.write(f"  .response.text: {text[:2000]}\n")
    req = getattr(e, "request", None)
    if req is not None:
        sys.stderr.write(f"  .request.url: {getattr(req, 'url', '?')}\n")
        sys.stderr.write(f"  .request.method: {getattr(req, 'method', '?')}\n")
    sys.stderr.write(f"--- END ERROR DUMP ---\n\n")


# ---------- Config ----------

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = REPO_ROOT / "index.html"
PROMPT_PATH = REPO_ROOT / "scripts" / "prompt_template.md"

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 32000
DEFAULT_MAX_SEARCHES = 12

PUTER_API_URL = "https://api.puter.com/puterai/openai/v1/chat/completions"
DEFAULT_FALLBACK_MODELS = (
    "perplexity/sonar-pro,perplexity/sonar-reasoning-pro,perplexity/sonar"
)
DEFAULT_FALLBACK_MAX_TOKENS = 16000

IST = timezone(timedelta(hours=5, minutes=30))


# ---------- Helpers ----------

def log(msg: str) -> None:
    ts = datetime.now(IST).strftime("%H:%M:%S IST")
    print(f"[{ts}] {msg}", flush=True)


def load_text(path: Path, label: str) -> str:
    if not path.exists():
        sys.stderr.write(f"ERROR: {label} not found at {path}\n")
        sys.exit(1)
    return path.read_text(encoding="utf-8")


def extract_html_block(text: str) -> str | None:
    """Pull the first ```html ... ``` block out of a model's response."""
    # Try fenced html block first
    m = re.search(r"```html\s*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1)
    # Fallback: bare ``` block
    m = re.search(r"```\s*\n(<!DOCTYPE.*?)\n```", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1)
    # Fallback: raw <!DOCTYPE ... </html>
    m = re.search(r"(<!DOCTYPE html.*?</html>)", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def looks_like_dashboard_html(html: str) -> tuple[bool, str]:
    """Lightweight sanity checks so we don't push garbage to main."""
    if len(html) < 5000:
        return False, f"too short ({len(html)} bytes — expected > 5000)"
    if "<!DOCTYPE" not in html[:200].upper().replace(" ", ""):
        # Some models emit <!doctype lowercase, normalize check
        if "<!DOCTYPE" not in html[:200] and "<!doctype" not in html[:200]:
            return False, "missing <!DOCTYPE declaration in first 200 bytes"
    if "</html>" not in html[-500:].lower():
        return False, "missing </html> in last 500 bytes"
    # Sanity: must contain a few expected sections
    must_have = ["Nifty", "Sensex"]
    missing = [tok for tok in must_have if tok.lower() not in html.lower()]
    if missing:
        return False, f"missing expected tokens: {missing}"
    return True, "ok"


# ---------- Providers ----------

def call_anthropic(api_key: str, model: str, max_tokens: int, max_searches: int, user_message: str) -> str:
    """Call Claude with the web_search tool, retrying transient failures.

    Returns the concatenated assistant text. Raises RuntimeError if every
    retry is exhausted.
    """
    if Anthropic is None:
        raise RuntimeError("anthropic SDK not installed (pip install anthropic)")

    log(f"anthropic SDK version: {getattr(_anthropic_pkg, '__version__', 'unknown')}")
    log(f"API key prefix: {api_key[:8]}…{api_key[-4:]} (len={len(api_key)})")

    # Use a generous timeout — web_search + 32k tokens can take 10-15 min.
    client = Anthropic(
        api_key=api_key,
        timeout=httpx.Timeout(1200.0, connect=30.0),  # 20 min total, 30s connect
    )

    MAX_RETRIES = 3
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log(f"Calling Anthropic Messages API (streaming, attempt {attempt}/{MAX_RETRIES})...")
            with client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                tools=[
                    {
                        "type": "web_search_20250305",
                        "name": "web_search",
                        "max_uses": max_searches,
                    }
                ],
                messages=[
                    {"role": "user", "content": user_message},
                ],
            ) as stream:
                for _event in stream:
                    pass
                response = stream.get_final_message()

            log(f"Response received. stop_reason={response.stop_reason}")
            log(
                f"Usage: input={response.usage.input_tokens} "
                f"output={response.usage.output_tokens} "
                f"(server tools may add to billing)"
            )

            full_text_parts: list[str] = []
            for block in response.content:
                btype = getattr(block, "type", "")
                if btype == "text" and hasattr(block, "text"):
                    full_text_parts.append(block.text)
                elif btype == "server_tool_use":
                    log(f"  [web_search used: {getattr(block, 'name', '?')}]")
            full_text = "\n".join(full_text_parts)

            if not full_text.strip():
                raise RuntimeError(f"assistant returned no text content: {response.content!r}")

            return full_text
        except (APIError, Exception) as e:  # noqa: BLE001 — we re-raise after retries
            sys.stderr.write(f"ERROR: Anthropic call failed on attempt {attempt}.\n")
            _dump_exception(e)
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"Anthropic API exhausted {MAX_RETRIES} retries") from e
            wait = 15 * attempt
            log(f"Retrying in {wait}s...")
            time.sleep(wait)

    raise RuntimeError("Anthropic API exhausted retries")  # unreachable, satisfies type checkers


def call_puter(model: str, puter_token: str, max_tokens: int, user_message: str) -> str:
    """Call a free open/web-grounded model via Puter.com's OpenAI-compatible API.

    Used as a fallback when Claude is unavailable or returns a bad response.
    Perplexity's Sonar models do real-time web search natively, which is
    what this dashboard needs for fresh market data and news.
    """
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a meticulous financial markets research assistant. "
                    "Use real-time web search results, not training data, for any "
                    "numbers or news. Follow the user's output-format instructions exactly."
                ),
            },
            {"role": "user", "content": user_message},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }

    # Puter's free shared pool occasionally returns 402 "insufficient_funds" for
    # a specific model even though the account/token is fine — a quick retry
    # often lands on a moment where that model's pool has headroom again.
    MAX_RETRIES = 2
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        log(f"Calling Puter.com fallback model '{model}' (attempt {attempt}/{MAX_RETRIES})...")
        try:
            resp = httpx.post(
                PUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {puter_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=httpx.Timeout(300.0, connect=30.0),
            )
            resp.raise_for_status()
            data = resp.json()
            if "choices" not in data or not data["choices"]:
                raise RuntimeError(f"Puter API returned no choices: {data.get('error', data)!r}")

            usage = data.get("usage", {})
            if usage:
                log(f"Usage: {json.dumps(usage)}")
            finish_reason = data["choices"][0].get("finish_reason")
            if finish_reason and finish_reason not in ("stop", "end_turn"):
                log(f"  [finish_reason={finish_reason!r} — response may be truncated]")

            return data["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001 — retried below, re-raised after last attempt
            last_error = e
            if attempt < MAX_RETRIES:
                log(f"  Puter call failed ({e}); retrying in 8s...")
                time.sleep(8)

    raise last_error  # type: ignore[misc]


# ---------- Main ----------

def main() -> int:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    puter_token = os.environ.get("PUTER_TOKEN", "").strip()

    if not api_key and not puter_token:
        sys.stderr.write(
            "ERROR: neither ANTHROPIC_API_KEY nor PUTER_TOKEN is set — "
            "need at least one credential to generate the dashboard.\n"
        )
        return 1

    model = os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    try:
        max_tokens = int(os.environ.get("MAX_TOKENS", DEFAULT_MAX_TOKENS))
    except ValueError:
        max_tokens = DEFAULT_MAX_TOKENS
    try:
        max_searches = int(os.environ.get("MAX_WEB_SEARCHES", DEFAULT_MAX_SEARCHES))
    except ValueError:
        max_searches = DEFAULT_MAX_SEARCHES

    fallback_models = [
        m.strip()
        for m in os.environ.get("FALLBACK_MODELS", DEFAULT_FALLBACK_MODELS).split(",")
        if m.strip()
    ]
    try:
        fallback_max_tokens = int(os.environ.get("FALLBACK_MAX_TOKENS", DEFAULT_FALLBACK_MAX_TOKENS))
    except ValueError:
        fallback_max_tokens = DEFAULT_FALLBACK_MAX_TOKENS

    now_ist = datetime.now(IST)
    if now_ist.weekday() >= 5:  # 5=Saturday, 6=Sunday IST
        log(f"Today is {now_ist.strftime('%A')} — skipping update (markets closed on weekends).")
        log("This run was likely a delayed GitHub Actions job from a weekday cron trigger.")
        return 0

    log(f"Model: {model} | max_tokens: {max_tokens} | max_searches: {max_searches}")
    if not api_key:
        log("ANTHROPIC_API_KEY not set — skipping Claude, going straight to fallback models.")
    if puter_token:
        log(f"Fallback models configured: {', '.join(fallback_models)}")
    else:
        log("PUTER_TOKEN not set — no fallback available if Claude fails.")

    prompt_template = load_text(PROMPT_PATH, "prompt template")

    context_block = (
        f"RUN TIMESTAMP (IST): {now_ist.strftime('%Y-%m-%d %H:%M:%S %A')}\n"
        f"RUN TIMESTAMP (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n"
    )

    user_message = (
        f"{context_block}\n"
        f"{prompt_template}\n\n"
        f"---\n"
        f"IMPORTANT: Do NOT use or reference the previous index.html content. "
        f"Generate a completely fresh index.html from scratch using the structure "
        f"and sections defined in the prompt template above. All CSS, layout, "
        f"fonts, and section structure must match the template spec exactly.\n\n"
        f"RETURN: the complete index.html as a single ```html ... ``` "
        f"fenced code block. No prose before or after the code block."
    )

    log(f"Prompt size: ~{len(user_message)} chars (~{len(user_message) // 4} tokens estimated)")

    # Build the ordered list of providers to try: Claude first, then fallbacks.
    attempts: list[tuple[str, "callable"]] = []
    if api_key:
        attempts.append(
            (f"anthropic:{model}", lambda: call_anthropic(api_key, model, max_tokens, max_searches, user_message))
        )
    if puter_token:
        for fb_model in fallback_models:
            attempts.append(
                (f"puter:{fb_model}", lambda m=fb_model: call_puter(m, puter_token, fallback_max_tokens, user_message))
            )

    for name, fn in attempts:
        log(f"--- Attempting provider: {name} ---")
        try:
            full_text = fn()
        except Exception as e:  # noqa: BLE001 — try the next provider
            sys.stderr.write(f"ERROR: provider '{name}' failed: {e}\n")
            continue

        new_html = extract_html_block(full_text)
        if new_html is None:
            sys.stderr.write(f"ERROR: provider '{name}' — could not extract HTML block from response\n")
            sys.stderr.write(f"Response length: {len(full_text)} chars\n")
            sys.stderr.write(f"First 500 chars of response:\n{full_text[:500]}\n")
            sys.stderr.write(f"Last 500 chars of response:\n{full_text[-500:]}\n")
            continue

        ok, reason = looks_like_dashboard_html(new_html)
        if not ok:
            sys.stderr.write(f"ERROR: provider '{name}' — HTML validation failed: {reason}\n")
            sys.stderr.write(f"First 500 chars of extracted HTML:\n{new_html[:500]}\n")
            continue

        INDEX_PATH.write_text(new_html, encoding="utf-8")
        log(f"index.html written ({len(new_html):,} bytes) via '{name}'")
        log("Done.")
        return 0

    sys.stderr.write("ERROR: every provider failed (Claude + all fallbacks) — see logs above.\n")
    return 5


if __name__ == "__main__":
    sys.exit(main())
