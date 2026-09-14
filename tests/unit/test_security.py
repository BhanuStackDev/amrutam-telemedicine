from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_password_hash_and_verify():
    password = "StrongPassword123!"

    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash)
    assert not verify_password("WrongPassword123!", password_hash)


def test_access_token_contains_identity_and_role():
    token = create_access_token(
        subject="test-user-id",
        role="patient",
    )

    payload = decode_token(token)

    assert payload["sub"] == "test-user-id"
    assert payload["role"] == "patient"
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload


def test_refresh_token_contains_jti_and_hashed_value_is_deterministic():
    token = create_refresh_token(
        subject="test-user-id",
        token_id="test-token-id",
    )

    payload = decode_token(token)

    assert payload["sub"] == "test-user-id"
    assert payload["jti"] == "test-token-id"
    assert payload["type"] == "refresh"

    assert hash_refresh_token(token) == hash_refresh_token(token)
    assert hash_refresh_token(token) != hash_refresh_token(
        token + "different"
    )
