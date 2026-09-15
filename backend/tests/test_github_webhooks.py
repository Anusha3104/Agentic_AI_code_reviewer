import hashlib
import hmac

from app.github.webhooks import parse_pull_request_event, verify_signature

SECRET = "test-webhook-secret"


def _sign(body: bytes, secret: str = SECRET) -> str:
    digest = hmac.new(secret.encode(), msg=body, digestmod=hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_valid_signature_passes():
    body = b'{"action": "opened"}'
    sig = _sign(body)
    assert verify_signature(body, sig, SECRET) is True


def test_invalid_signature_fails():
    body = b'{"action": "opened"}'
    assert verify_signature(body, "sha256=deadbeef", SECRET) is False


def test_tampered_body_fails():
    body = b'{"action": "opened"}'
    sig = _sign(body)
    tampered_body = b'{"action": "closed"}'
    assert verify_signature(tampered_body, sig, SECRET) is False


def test_missing_header_fails():
    assert verify_signature(b"{}", None, SECRET) is False


def test_missing_secret_fails():
    body = b"{}"
    sig = _sign(body, secret="whatever")
    assert verify_signature(body, sig, "") is False


def test_wrong_prefix_fails():
    assert verify_signature(b"{}", "sha1=abcd", SECRET) is False


def _sample_payload(action="opened", with_installation=True):
    payload = {
        "action": action,
        "pull_request": {"number": 42},
        "repository": {"full_name": "octocat/hello-world"},
    }
    if with_installation:
        payload["installation"] = {"id": 12345}
    return payload


def test_parse_pull_request_event_opened():
    event = parse_pull_request_event(_sample_payload("opened"))
    assert event.owner == "octocat"
    assert event.repo == "hello-world"
    assert event.pr_number == 42
    assert event.is_relevant is True
    assert event.installation_id == "12345"


def test_parse_pull_request_event_irrelevant_action():
    event = parse_pull_request_event(_sample_payload("labeled"))
    assert event.is_relevant is False


def test_parse_pull_request_event_missing_fields_returns_none():
    assert parse_pull_request_event({"action": "opened"}) is None


def test_parse_pull_request_event_without_installation():
    event = parse_pull_request_event(_sample_payload("synchronize", with_installation=False))
    assert event.installation_id is None
    assert event.is_relevant is True
