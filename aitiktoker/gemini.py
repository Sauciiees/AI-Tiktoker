"""Shared retry and model fallback for Gemini calls."""

import sys
import time
from typing import Callable, TypeVar

from google.genai import errors

T = TypeVar("T")

# Overloaded or rate limited: worth waiting and trying again.
RETRYABLE_CODES = {429, 500, 503, 504}


def call_with_fallback(
    models: list[str],
    call: Callable[[str], T],
    attempts_per_model: int = 3,
    first_wait_sec: float = 2.0,
) -> tuple[T, str]:
    """Runs call(model) for each model in turn, retrying busy ones with growing waits (2s, 4s, ...).

    Free-tier keys often get "high demand" errors, so a busy model falls through to the next.
    Returns the result and the model that produced it.
    """
    last_error: Exception | None = None

    for model in models:
        for attempt in range(1, attempts_per_model + 1):
            try:
                return call(model), model
            except errors.APIError as e:
                last_error = e
                if e.code not in RETRYABLE_CODES:
                    print(f"{model}: {e.code} {e.status}, skipping this model.", file=sys.stderr)
                    break
                if attempt == attempts_per_model:
                    print(f"{model}: still busy after {attempt} tries, moving on.", file=sys.stderr)
                    break
                wait = first_wait_sec * 2 ** (attempt - 1)
                print(f"{model}: {e.code} {e.status}, retrying in {wait:g}s...", file=sys.stderr)
                time.sleep(wait)

    raise RuntimeError(f"Every model failed. Last error: {last_error}")
