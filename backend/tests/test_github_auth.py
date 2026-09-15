from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.github.auth import GitHubAuthError, create_app_jwt, get_installation_token


@pytest.fixture(scope="module")
def rsa_private_key_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pem.decode("utf-8")


def test_create_app_jwt_produces_valid_token(rsa_private_key_pem):
    token = create_app_jwt("12345", rsa_private_key_pem)
    decoded = jwt.decode(token, options={"verify_signature": False})
    assert decoded["iss"] == "12345"
    assert decoded["exp"] > decoded["iat"]


def test_create_app_jwt_requires_app_id_and_key():
    with pytest.raises(GitHubAuthError):
        create_app_jwt("", "some-key")
    with pytest.raises(GitHubAuthError):
        create_app_jwt("123", "")


def test_create_app_jwt_rejects_invalid_key():
    with pytest.raises(GitHubAuthError):
        create_app_jwt("123", "not-a-real-pem-key")


def test_get_installation_token_success(rsa_private_key_pem):
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"token": "ghs_faketoken", "expires_at": "2099-01-01T00:00:00Z"}
    mock_session.post.return_value = mock_resp

    result = get_installation_token("123", rsa_private_key_pem, "999", session=mock_session)
    assert result.token == "ghs_faketoken"


def test_get_installation_token_failure_raises(rsa_private_key_pem):
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.text = "Not Found"
    mock_session.post.return_value = mock_resp

    with pytest.raises(GitHubAuthError):
        get_installation_token("123", rsa_private_key_pem, "999", session=mock_session)
