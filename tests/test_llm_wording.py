import io
import json
import urllib.error

import pytest

from ai import llm_wording as L


class Fake:
    def __init__(self, text=None, exc=None):
        self.text, self.exc, self.calls = text, exc, []

    def complete(self, system, user):
        self.calls.append((system, user))
        if self.exc:
            raise self.exc
        return self.text


ANSWER = "Peak demand is 18:00-19:00 with 2,160 bookings (9.3% of all)."


def test_number_normalisation():
    assert L.extract_numbers("2,160 and 30.0 and 9.30") == {"2160", "30", "9.3"}
    assert L.extract_numbers("١٨:٠٠ و٢٬١٦٠") == {"18", "0", "2160"}
    assert L.extract_numbers("no digits here") == set()


def test_numbers_preserved_rules():
    assert L.numbers_preserved(ANSWER, "Busiest at 18:00-19:00: 2160 bookings, 9.3% of all.")
    assert not L.numbers_preserved(ANSWER, "Busiest at 18:00-19:00: 2,600 bookings, 9.3%.")     # changed
    assert not L.numbers_preserved(ANSWER, "Busiest at 18:00-19:00 with 2,160 bookings.")        # dropped 9.3
    assert not L.numbers_preserved(ANSWER, ANSWER + " That is 3 times the quiet hours.")         # added 3


def test_good_rewrite_is_used_and_prompt_is_safe():
    f = Fake("The rush is 18:00-19:00: 2,160 bookings, 9.3% of all.")
    r = L.rephrase(ANSWER, "when is the peak?", f)
    assert r.used_llm and r.reason == "ok" and r.text.startswith("The rush")
    system, user = f.calls[0]
    assert "EXACTLY the numbers" in system and ANSWER in user and "when is the peak?" in user


def test_hallucinated_numbers_fall_back_to_original():
    r = L.rephrase(ANSWER, "q", Fake("Peak is at 18:00-19:00 with 3,000 bookings (9.3%)."))
    assert not r.used_llm and r.text == ANSWER and "numbers changed" in r.reason


@pytest.mark.parametrize("exc", [L.LLMError("HTTP 500"), RuntimeError("boom"), ValueError("x")])
def test_client_failures_fall_back(exc):
    r = L.rephrase(ANSWER, "q", Fake(exc=exc))
    assert not r.used_llm and r.text == ANSWER


def test_empty_reply_falls_back():
    assert not L.rephrase(ANSWER, "q", Fake("   ")).used_llm


def test_no_key_means_original_answer(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = L.rephrase(ANSWER, "q")
    assert not r.used_llm and r.text == ANSWER and "no API key" in r.reason
    assert L.default_client() is None


def test_default_client_uses_environment_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", " sk-test ")
    c = L.default_client()
    assert isinstance(c, L.AnthropicHTTPClient) and c.api_key == "sk-test"


class FakeResp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_http_client_builds_correct_request_and_parses_reply(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen.update(url=req.full_url, headers={k.lower(): v for k, v in req.header_items()},
                    body=json.loads(req.data), timeout=timeout, method=req.get_method())
        return FakeResp(json.dumps({"content": [{"type": "text", "text": "Hello 18:00"}]}).encode())

    monkeypatch.setattr(L.urllib.request, "urlopen", fake_urlopen)
    out = L.AnthropicHTTPClient("sk-secret", model="m-test", timeout=7).complete("SYS", "USR")
    assert out == "Hello 18:00" and seen["method"] == "POST" and seen["url"] == L.API_URL
    assert seen["headers"]["x-api-key"] == "sk-secret" and seen["headers"]["anthropic-version"] == L.API_VERSION
    assert seen["body"]["model"] == "m-test" and seen["body"]["system"] == "SYS"
    assert seen["body"]["messages"] == [{"role": "user", "content": "USR"}] and seen["timeout"] == 7
    assert "sk-secret" not in json.dumps(seen["body"])                 # key only in the header


@pytest.mark.parametrize("raiser", [
    lambda *a, **k: (_ for _ in ()).throw(urllib.error.HTTPError("u", 429, "rate", {}, None)),
    lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("no internet")),
    lambda *a, **k: (_ for _ in ()).throw(TimeoutError()),
    lambda *a, **k: FakeResp(b"not json"),
    lambda *a, **k: FakeResp(json.dumps({"content": []}).encode()),
])
def test_http_client_errors_become_llm_error(monkeypatch, raiser):
    monkeypatch.setattr(L.urllib.request, "urlopen", raiser)
    with pytest.raises(L.LLMError):
        L.AnthropicHTTPClient("k").complete("s", "u")
    assert not L.rephrase(ANSWER, "q", L.AnthropicHTTPClient("k")).used_llm      # and rephrase never raises
