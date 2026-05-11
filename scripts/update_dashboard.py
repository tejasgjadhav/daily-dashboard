#!/usr/bin/env python3
"""
Claude API-driven daily dashboard updater.

Runs inside GitHub Actions (or anywhere with ANTHROPIC_API_KEY set).
Calls Anthropic's Messages API with the prompt in scripts/prompt_template.md,
gives Claude the current index.html + the web_search server tool, and writes
back the refreshed HTML.

No browser, no laptop, no Cowork — purely server-to-server.

Environment:
  ANTHROPIC_API_KEY  (required) — your Anthropic API key
  CLAUDE_MODEL       (optional) — defaults to claude-sonnet-4-6
  MAX_TOKENS         (optional) — defaults to 32000
  MAX_WEB_SEARCHES   (optional) — defaults to 12

Exit codes:
  0  success, index.html written
  1  config error (missing key, missing files)
  2  API error
  3  response parsing error (no HTML block found)
  4  validation error (HTML doesn't look right)
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import anthropic as _anthropic_pkg
    from anthropic import Anthropic, APIError
except ImportError:
    sys.stderr.write(
        "ERROR: anthropic SDK not installed. Run: pip install anthropic\n"
    )
    sys.exit(1)


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
    """Pull the first ```html ... ``` block out of Claude's response."""
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


# ---------- Main ----------

def main() -> int:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        sys.stderr.write("ERROR: ANTHROPIC_API_KEY env var not set\n")
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

    log(f"Model: {model} | max_tokens: {max_tokens} | max_searches: {max_searches}")
    log(f"anthropic SDK version: {getattr(_anthropic_pkg, '__version__', 'unknown')}")
    log(f"API key prefix: {api_key[:8]}…{api_key[-4:]} (len={len(api_key)})")

    current_html = load_text(INDEX_PATH, "index.html")
    prompt_template = load_text(PROMPT_PATH, "prompt template")

    now_ist = datetime.now(IST)
    context_block = (
        f"RUN TIMESTAMP (IST): {now_ist.strftime('%Y-%m-%d %H:%M:%S %A')}\n"
        f"RUN TIMESTAMP (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n"
    )

    user_message = (
        f"{context_block}\n"
        f"{prompt_template}\n\n"
        f"---\n"
        f"CURRENT index.html (preserve all CSS, layout, and structural markup — "
        f"only refresh content/data/text):\n\n"
        f"```html\n{current_html}\n```\n\n"
        f"---\n"
        f"RETURN: the complete updated index.html as a single ```html ... ``` "
        f"fenced code block. No prose before or after the code block."
    )

    log(f"Prompt size: ~{len(user_message)} chars (~{len(user_message) // 4} tokens estimated)")

    client = Anthropic(api_key=api_key)

    try:
        log("Calling Anthropic Messages API (streaming)...")
        # Streaming is REQUIRED here. With max_tokens this large + the
        # web_search server tool, the SDK's client-side guard estimates the
        # request could exceed 10 min and refuses non-streaming. The
        # streaming context manager bypasses that check and gives us the
        # same final-message shape via .get_final_message().
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
            # Drain the stream — we don't need to do anything per-event,
            # just let it accumulate. Optionally we could log progress.
            for _event in stream:
                pass
            response = stream.get_final_message()
    except APIError as e:
        sys.stderr.write("ERROR: Anthropic API call failed (APIError).\n")
        _dump_exception(e)
        return 2
    except Exception as e:
        sys.stderr.write("ERROR: unexpected exception during API call.\n")
        _dump_exception(e)
        return 2

    log(f"Response received. stop_reason={response.stop_reason}")
    log(
        f"Usage: input={response.usage.input_tokens} "
        f"output={response.usage.output_tokens} "
        f"(server tools may add to billing)"
    )

    # Concatenate all text blocks from the assistant response
    full_text_parts: list[str] = []
    for block in response.content:
        btype = getattr(block, "type", "")
        if btype == "text" and hasattr(block, "text"):
            full_text_parts.append(block.text)
        elif btype == "server_tool_use":
            log(f"  [web_search used: {getattr(block, 'name', '?')}]")
    full_text = "\n".join(full_text_parts)

    if not full_text.strip():
        sys.stderr.write("ERROR: assistant returned no text content\n")
        sys.stderr.write(f"Raw response.content: {response.content!r}\n")
        return 3

    new_html = extract_html_block(full_text)
    if new_html is None:
        sys.stderr.write("ERROR: could not extract HTML block from response\n")
        sys.stderr.write(f"First 1000 chars of response:\n{full_text[:1000]}\n")
        return 3

    ok, reason = looks_like_dashboard_html(new_html)
    if not ok:
        sys.stderr.write(f"ERROR: HTML validation failed — {reason}\n")
        sys.stderr.write(f"First 500 chars of extracted HTML:\n{new_html[:500]}\n")
        return 4

    INDEX_PATH.write_text(new_html, encoding="utf-8")
    log(f"index.html written ({len(new_html):,} bytes)")
    log("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
