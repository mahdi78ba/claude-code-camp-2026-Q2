"""Sends a PromptBuilder's payload to the provider and returns the raw response.

Python port of Boukensha::Client. Uses only the standard library
(urllib.request), matching the Ruby reference's stdlib-only net/http choice —
no HTTP library dependency, intentionally.

Ruby's Net::HTTP does not raise on a non-2xx response (it returns a response
object the caller inspects); Python's urllib.request.urlopen raises
urllib.error.HTTPError for any status >= 400, and wraps lower-level
connection/timeout/SSL failures in urllib.error.URLError. The two except
clauses below map onto Ruby's two retry paths (retryable status codes vs.
transient connection errors) using each language's own error-surfacing
convention rather than a literal exception-class-for-exception-class
translation.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from .errors import ApiError


class Client:
    RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 0.5

    def __init__(self, builder) -> None:
        self.builder = builder

    def call(self, *, max_output_tokens=1024, tools=None):
        body = json.dumps(
            self.builder.to_api_payload(
                max_output_tokens=max_output_tokens, tools=tools
            )
        ).encode("utf-8")
        request = urllib.request.Request(
            self.builder.url,
            data=body,
            headers=self.builder.headers,
            method="POST",
        )

        attempts = 0
        while True:
            attempts += 1

            try:
                with urllib.request.urlopen(request) as response:
                    return json.loads(response.read())
            except urllib.error.HTTPError as e:
                if self._retryable_status(e.code) and attempts <= self.MAX_RETRIES:
                    time.sleep(self._retry_delay(attempts))
                    continue

                body_text = e.read().decode("utf-8", errors="replace")
                suffix = "" if attempts == 1 else "s"
                raise ApiError(
                    f"API request failed after {attempts} attempt{suffix} "
                    f"({e.code}): {body_text}"
                ) from e
            except urllib.error.URLError as e:
                if attempts > self.MAX_RETRIES:
                    raise ApiError(
                        f"API request failed after {attempts} attempts: "
                        f"{type(e.reason).__name__}: {e.reason}"
                    ) from e

                time.sleep(self._retry_delay(attempts))

    @classmethod
    def _retryable_status(cls, status_code) -> bool:
        return status_code in cls.RETRYABLE_STATUS_CODES

    @classmethod
    def _retry_delay(cls, attempt) -> float:
        return cls.BASE_RETRY_DELAY * (2 ** (attempt - 1))
