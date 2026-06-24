"""In-memory per-user interaction state for the bot.

Kept intentionally simple (process-local dict). For multi-process deployments
this would move to Redis, but a single bot process owns all updates so a dict is
correct and fast here.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class UploadContext:
    """Where the next uploaded video should be attached."""

    content_id: int
    content_title: str


@dataclass
class PendingInput:
    """A text prompt we are waiting for the user to answer."""

    action: str  # e.g. 'new_root', 'subnew_child', 'set_password'
    parent_id: int | None = None
    extra: dict = field(default_factory=dict)


class BotState:
    def __init__(self) -> None:
        self._upload: dict[int, UploadContext] = {}
        self._pending: dict[int, PendingInput] = {}

    # --- upload target ---
    def set_upload_target(self, tg_id: int, ctx: UploadContext) -> None:
        self._upload[tg_id] = ctx

    def get_upload_target(self, tg_id: int) -> UploadContext | None:
        return self._upload.get(tg_id)

    def clear_upload_target(self, tg_id: int) -> None:
        self._upload.pop(tg_id, None)

    # --- pending text input ---
    def set_pending(self, tg_id: int, pending: PendingInput) -> None:
        self._pending[tg_id] = pending

    def pop_pending(self, tg_id: int) -> PendingInput | None:
        return self._pending.pop(tg_id, None)

    def has_pending(self, tg_id: int) -> bool:
        return tg_id in self._pending


bot_state = BotState()
