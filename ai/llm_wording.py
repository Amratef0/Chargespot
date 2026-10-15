"""Optional LLM wording on top of the rule-based assistant (Member 4).

The rule-based assistant COMPUTES the answer. The LLM may only REPHRASE it
in friendlier language. Safety design:

1. Numbers are verified: every number in the rephrased text must exist in the
   original answer and none may be added or dropped (Arabic-Indic digits are
   normalised). Otherwise the original answer is shown.
2. Any failure (no key, no internet, timeout, HTTP error, empty reply) falls
   back to the original answer - the demo never breaks.
3. Privacy: only the question and the already-aggregated answer text are sent.
   No booking rows, no driver names. The API key comes from the environment
   variable ANTHROPIC_API_KEY or Streamlit secrets - never from code.
4. Off by default; the app only offers it when a key is available.

No SDK needed: a plain HTTPS request via urllib (Anthropic Messages API).
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = os.environ.get("CHARGESPOT_LLM_MODEL", "claude-haiku-5-5")

SYSTEM_PROMPT = (
    "You rewrite analytics answers for an EV-charging dashboard. Rewrite the given answer in one "
    "or two friendly, clear sentences, in the same language as the user's question. "
    "Use EXACTLY the numbers from the answer: do not change, round, add or remove any number. "
    "Do not add facts, advice or opinions that are not in the answer. Return only the rewritten text."
)


class LLMError(RuntimeError):
    """Any problem talking to the LLM (the caller falls back to the original text)."""


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str: ...


@dataclass
class RephraseResult:
    text: str
    used_llm: bool
    reason: str            # "ok" or why the original answer is shown


# ---------------------------------------------------------------- key handling
def get_api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key.strip()
    try:                                                   # optional: Streamlit secrets
        import streamlit as st
        return str(st.secrets["ANTHROPIC_API_KEY"]).strip() or None
    except Exception:
        return None


# ---------------------------------------------------------------- HTTP client
class AnthropicHTTPClient:
    """Minimal Messages-API client (no SDK dependency)."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, timeout: float = 15.0,
                 max_tokens: int = 200):
        self.api_key, self.model, self.timeout, self.max_tokens = api_key, model, timeout, max_tokens

    def complete(self, system: str, user: str) -> str:
        body = json.dumps({"model": self.model, "max_tokens": self.max_tokens,
                           "system": system,
                           "messages": [{"role": "user", "content": user}]}).encode("utf-8")
        req = urllib.request.Request(API_URL, data=body, method="POST", headers={
            "content-type": "application/json", "x-api-key": self.api_key,
            "anthropic-version": API_VERSION})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise LLMError(f"HTTP {e.code}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise LLMError(f"network error: {type(e).__name__}") from e
        except json.JSONDecodeError as e:
            raise LLMError("invalid JSON in reply") from e
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
        if not text:
            raise LLMError("empty reply")
        return text


def default_client() -> LLMClient | None:
    key = get_api_key()
    return AnthropicHTTPClient(key) if key else None


# ---------------------------------------------------------------- number guard
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789.,")
_NUM = re.compile(r"\d+(?:[.,]\d+)*")


def extract_numbers(text: str) -> set[str]:
    """Normalised set of numeric tokens: '2,160' -> '2160', '30.0' -> '30', Arabic digits -> ASCII."""
    out = set()
    for tok in _NUM.findall(text.translate(_ARABIC_DIGITS)):
        tok = tok.replace(",", "")
        try:
            f = float(tok)
            out.add(str(int(f)) if f == int(f) else str(f))
        except ValueError:
            out.add(tok)
    return out


def numbers_preserved(original: str, candidate: str) -> bool:
    """True only if both texts contain exactly the same set of numbers."""
    return extract_numbers(original) == extract_numbers(candidate)


# ---------------------------------------------------------------- public API
def rephrase(answer: str, question: str, client: LLMClient | None = None) -> RephraseResult:
    """Rephrase `answer` with the LLM if possible and safe; otherwise return it unchanged."""
    if client is None:
        client = default_client()
    if client is None:
        return RephraseResult(answer, False, "no API key configured")
    try:
        candidate = client.complete(SYSTEM_PROMPT, f"Question: {question}\nAnswer to rewrite: {answer}")
    except LLMError as e:
        return RephraseResult(answer, False, f"LLM unavailable ({e})")
    except Exception as e:                                  # never let a client bug break the app
        return RephraseResult(answer, False, f"LLM error ({type(e).__name__})")
    candidate = (candidate or "").strip()
    if not candidate:
        return RephraseResult(answer, False, "empty LLM reply")
    if not numbers_preserved(answer, candidate):
        return RephraseResult(answer, False, "numbers changed by the LLM - original kept")
    return RephraseResult(candidate, True, "ok")
