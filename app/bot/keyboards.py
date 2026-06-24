"""Inline keyboard builders for a clean, professional bot UI."""
from __future__ import annotations

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.models import Content


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("\U0001F4C1 My Content", callback_data="menu:content"),
                InlineKeyboardButton("\U0001F39E My Videos", callback_data="menu:videos"),
            ],
            [
                InlineKeyboardButton("\u2795 New Content", callback_data="menu:new"),
                InlineKeyboardButton("\U0001F517 Links", callback_data="menu:links"),
            ],
            [InlineKeyboardButton("\u2139\uFE0F Help", callback_data="menu:help")],
        ]
    )


def content_list(items: list[Content], back: str | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for c in items:
        rows.append(
            [InlineKeyboardButton(f"{c.title}", callback_data=f"open:{c.id}")]
        )
    if back is not None:
        rows.append([InlineKeyboardButton("\u2B05\uFE0F Back", callback_data=back)])
    rows.append([InlineKeyboardButton("\U0001F3E0 Menu", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


def content_actions(content: Content) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                "\u2795 Add Sub-content", callback_data=f"sub:{content.id}"
            ),
            InlineKeyboardButton(
                "\U0001F4E4 Upload Here", callback_data=f"upload:{content.id}"
            ),
        ],
        [
            InlineKeyboardButton(
                "\U0001F517 Get Link", callback_data=f"link:{content.id}"
            ),
            InlineKeyboardButton(
                "\U0001F5D1 Delete", callback_data=f"del:{content.id}"
            ),
        ],
    ]
    if content.parent_id:
        rows.append(
            [InlineKeyboardButton("\u2B05\uFE0F Back", callback_data=f"open:{content.parent_id}")]
        )
    rows.append([InlineKeyboardButton("\U0001F3E0 Menu", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


def confirm_delete(content_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("\u2705 Yes, delete", callback_data=f"delyes:{content_id}"),
                InlineKeyboardButton("\u274C Cancel", callback_data=f"open:{content_id}"),
            ]
        ]
    )
