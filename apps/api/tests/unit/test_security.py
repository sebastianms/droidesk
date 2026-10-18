import secrets
from datetime import timedelta
from typing import Any

import jwt
import pytest

from droidesk_api.core.errors import NotAuthenticatedError
from droidesk_api.core.security import TOKEN_LIFETIME, TokenService
from tests.fakes import FakeClock

SECRET = secrets.token_hex(32)


@pytest.fixture
def tokens(clock: FakeClock) -> TokenService:
    return TokenService(SECRET, clock)


def encode(
    claims: dict[str, Any], secret: str = SECRET, algorithm: str = "HS256"
) -> str:
    return jwt.encode(claims, secret, algorithm=algorithm)


def decode_claims(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        SECRET,
        algorithms=["HS256"],
        options={"verify_exp": False, "verify_iat": False},
    )


def test_a_token_gives_back_the_user_it_was_issued_for(tokens: TokenService) -> None:
    assert tokens.read_user_id(tokens.issue(7).value) == 7


def test_token_carries_exactly_sub_iat_and_exp(tokens: TokenService) -> None:
    assert set(decode_claims(tokens.issue(7).value)) == {"sub", "iat", "exp"}


def test_token_subject_is_the_user_id_as_text(tokens: TokenService) -> None:
    assert decode_claims(tokens.issue(7).value)["sub"] == "7"


def test_token_is_signed_with_hs256(tokens: TokenService) -> None:
    header = jwt.get_unverified_header(tokens.issue(7).value)
    assert header["alg"] == "HS256"


def test_token_is_issued_at_the_clock_time(
    tokens: TokenService, clock: FakeClock
) -> None:
    issued_at = decode_claims(tokens.issue(7).value)["iat"]
    assert issued_at == int(clock.now().timestamp())


def test_token_expires_eight_hours_after_issue(
    tokens: TokenService, clock: FakeClock
) -> None:
    assert tokens.issue(7).expires_at == clock.now() + timedelta(hours=8)


def test_reported_expiry_matches_the_exp_claim(tokens: TokenService) -> None:
    token = tokens.issue(7)
    assert decode_claims(token.value)["exp"] == int(token.expires_at.timestamp())


def test_expiry_drops_the_fraction_of_a_second(clock: FakeClock) -> None:
    clock.set(clock.now().replace(microsecond=999_999))
    assert TokenService(SECRET, clock).issue(7).expires_at.microsecond == 0


def test_token_is_valid_until_the_last_second(
    tokens: TokenService, clock: FakeClock
) -> None:
    token = tokens.issue(7)
    clock.advance(TOKEN_LIFETIME - timedelta(seconds=1))
    assert tokens.read_user_id(token.value) == 7


def test_token_is_rejected_at_expiry(tokens: TokenService, clock: FakeClock) -> None:
    token = tokens.issue(7)
    clock.advance(TOKEN_LIFETIME)
    with pytest.raises(NotAuthenticatedError):
        tokens.read_user_id(token.value)


def test_token_signed_with_another_secret_is_rejected(
    tokens: TokenService, clock: FakeClock
) -> None:
    foreign = TokenService(secrets.token_hex(32), clock).issue(7)
    with pytest.raises(NotAuthenticatedError):
        tokens.read_user_id(foreign.value)


def test_unsigned_token_is_rejected(tokens: TokenService, clock: FakeClock) -> None:
    claims = {"sub": "7", "iat": 1, "exp": int(clock.now().timestamp()) + 3600}
    unsigned = jwt.encode(claims, None, algorithm="none")
    with pytest.raises(NotAuthenticatedError):
        tokens.read_user_id(unsigned)


def test_token_with_another_algorithm_is_rejected(
    tokens: TokenService, clock: FakeClock
) -> None:
    claims = {"sub": "7", "iat": 1, "exp": int(clock.now().timestamp()) + 3600}
    with pytest.raises(NotAuthenticatedError):
        tokens.read_user_id(encode(claims, algorithm="HS512"))


def test_malformed_token_is_rejected(tokens: TokenService) -> None:
    with pytest.raises(NotAuthenticatedError):
        tokens.read_user_id("not-a-token")


@pytest.mark.parametrize("missing", ["sub", "iat", "exp"])
def test_token_without_a_required_claim_is_rejected(
    tokens: TokenService, clock: FakeClock, missing: str
) -> None:
    claims = {"sub": "7", "iat": 1, "exp": int(clock.now().timestamp()) + 3600}
    del claims[missing]
    with pytest.raises(NotAuthenticatedError):
        tokens.read_user_id(encode(claims))


def test_token_with_a_non_numeric_subject_is_rejected(
    tokens: TokenService, clock: FakeClock
) -> None:
    claims = {"sub": "ana", "iat": 1, "exp": int(clock.now().timestamp()) + 3600}
    with pytest.raises(NotAuthenticatedError):
        tokens.read_user_id(encode(claims))
