"""OpenRouter account validation via the public ``/auth/key`` endpoint.

Uses ``urllib`` from the standard library so this check has no third-party
dependencies and can run from the bootstrap engine's own venv.

OpenRouter's ``GET /auth/key`` returns a JSON document like::

    {
      "data": {
        "label": "sk-or-v1-... (display name)",
        "limit": null,
        "usage": 0.123,
        "is_free_tier": false,
        "rate_limit": {"requests": 200, "interval": "10s"}
      }
    }

A 401 means the key is bad or revoked; 402 means the OpenRouter account is
out of credit; other non-2xx responses are surfaced verbatim so the caller
can decide whether to retry or fail.
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .constants import BASE_URL


class AccountCheckError(Exception):
    """Raised when the account check fails for a non-credential reason.

    For credential-specific failures (401, 402), prefer reading
    ``AccountStatus.ok`` and ``AccountStatus.failure_reason`` -- the call
    still returns a status object so the caller can render a fix-all hint.
    """


@dataclass(frozen=True)
class AccountStatus:
    """Snapshot of an OpenRouter account's credential health.

    ``ok`` is True when the key authenticated successfully and the account
    can make API calls. ``failure_reason`` is one of:

    - ``"auth"``       -- HTTP 401 (bad or revoked key)
    - ``"no_credit"``  -- HTTP 402 (account out of credit)
    - ``None``         -- success
    """

    ok: bool
    label: Optional[str]
    usage: Optional[float]
    limit: Optional[float]
    is_free_tier: Optional[bool]
    rate_limit: Optional[Dict[str, Any]]
    failure_reason: Optional[str]
    raw: Optional[Dict[str, Any]]


def check_account(api_key: str, *, timeout: float = 10.0) -> AccountStatus:
    """Validate ``api_key`` against the OpenRouter ``/auth/key`` endpoint.

    Args:
        api_key: The key to validate. An empty string or None raises
            ``AccountCheckError`` immediately rather than wasting a request.
        timeout: Socket timeout in seconds. Defaults to 10s -- the bootstrap
            session-start hook should not stall longer than that on a network
            hiccup.

    Returns:
        AccountStatus describing the key's health.

    Raises:
        AccountCheckError: For network/transport errors and unexpected HTTP
            statuses (anything other than 200, 401, 402). Use this to
            distinguish "the user's key is bad" (returns ok=False) from
            "we could not reach OpenRouter" (raises).
    """
    if not api_key:
        raise AccountCheckError("api_key is empty -- nothing to check")

    req = urllib.request.Request(
        f"{BASE_URL}/auth/key",
        headers={"Authorization": f"Bearer {api_key}"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            payload = json.loads(body)
            data = payload.get("data", {}) if isinstance(payload, dict) else {}
            return AccountStatus(
                ok=True,
                label=data.get("label"),
                usage=data.get("usage"),
                limit=data.get("limit"),
                is_free_tier=data.get("is_free_tier"),
                rate_limit=data.get("rate_limit"),
                failure_reason=None,
                raw=payload if isinstance(payload, dict) else None,
            )
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return _failure("auth")
        if e.code == 402:
            return _failure("no_credit")
        raise AccountCheckError(
            f"OpenRouter /auth/key returned HTTP {e.code}: {e.reason}"
        ) from e
    except urllib.error.URLError as e:
        raise AccountCheckError(f"Network error contacting OpenRouter: {e.reason}") from e
    except (TimeoutError, OSError) as e:
        raise AccountCheckError(f"Transport error contacting OpenRouter: {e}") from e
    except json.JSONDecodeError as e:
        raise AccountCheckError(f"OpenRouter returned non-JSON body: {e}") from e


def _failure(reason: str) -> AccountStatus:
    return AccountStatus(
        ok=False,
        label=None,
        usage=None,
        limit=None,
        is_free_tier=None,
        rate_limit=None,
        failure_reason=reason,
        raw=None,
    )
