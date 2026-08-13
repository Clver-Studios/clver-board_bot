from __future__ import annotations

from .models import Candidate


def analyze(candidates: list[Candidate], reaction_threshold: int) -> list[Candidate]:
    """Filter scanned candidates down to qualifying posts, ranked highest reactions first.

    Scanning already drops zero-reaction posts; this stage applies the configured
    minimum-reaction threshold and produces the final ranked candidate list that
    gets sent to staff for verification.
    """
    qualifying = [c for c in candidates if c.reaction_count >= reaction_threshold]
    qualifying.sort(key=lambda c: c.reaction_count, reverse=True)
    return qualifying
