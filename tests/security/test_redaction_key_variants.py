import pytest

from reproagent.security import Redactor


@pytest.mark.parametrize(
    "sensitive_key",
    [
        "apiKey",
        "API.KEY",
        "x api key",
        "clientSecret",
        "accessToken",
        "refresh.token",
        "proxyAuthorization",
        "setCookie",
        "connectionString",
    ],
)
def test_common_sensitive_key_spelling_variants_are_redacted(sensitive_key: str) -> None:
    synthetic_secret = "synthetic-secret-that-must-not-survive"

    result = Redactor().redact({sensitive_key: synthetic_secret})

    assert isinstance(result.value, dict)
    assert result.value[sensitive_key] == "[REDACTED:sensitive-key]"
    assert synthetic_secret not in repr(result.value)
    assert len(result.hits) == 1
    assert result.hits[0].rule_id == "default.sensitive-key"


def test_nearby_non_sensitive_key_is_not_over_redacted() -> None:
    result = Redactor().redact(
        {
            "token_count": 42,
            "secretary": "visible",
            "authorization_mode": "delegated",
        }
    )

    assert result.value == {
        "token_count": 42,
        "secretary": "visible",
        "authorization_mode": "delegated",
    }
    assert result.hits == ()
