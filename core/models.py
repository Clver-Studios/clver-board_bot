from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Candidate:
    message_id: int
    author_id: int
    author_name: str
    channel_id: int
    channel_name: str
    is_thread: bool
    content: str
    reaction_count: int
    timestamp: str  # ISO 8601
    jump_url: str
    image_url: str | None
    # Verification-stage state (unset until the candidate enters review).
    status: str = "pending"  # "pending" | "approved" | "rejected"
    approval_message_id: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Candidate":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})
