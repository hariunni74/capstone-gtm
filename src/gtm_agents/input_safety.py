"""Screen research briefs before either workflow starts."""

import os

import httpx


class SafetyCheckUnavailable(RuntimeError):
    """Raised when the app cannot obtain a valid safety decision."""


def check_brief_safety(
    topic: str,
    geography: str,
    target_customer: str,
) -> bool:
    """Return True if flagged; raise if screening is unavailable.

    Send the complete brief for context. Do not log its contents or
    expose provider errors, which might contain sensitive information.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise SafetyCheckUnavailable("Safety screening is unavailable.")

    brief = (
        f"Product or market: {topic}\n"
        f"Geography: {geography}\n"
        f"Target customer: {target_customer}"
    )

    try:
        with httpx.Client(
            timeout=httpx.Timeout(20.0, connect=5.0)
        ) as client:
            response = client.post(
                "https://api.openai.com/v1/moderations",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "omni-moderation-latest",
                    "input": brief,
                },
            )
            response.raise_for_status()
            results = response.json()["results"]

        if not isinstance(results, list) or len(results) != 1:
            raise ValueError("Unexpected moderation response.")

        flagged = results[0]["flagged"]
        if not isinstance(flagged, bool):
            raise ValueError("Missing moderation decision.")

        return flagged

    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise SafetyCheckUnavailable(
            "Safety screening is unavailable."
        ) from None