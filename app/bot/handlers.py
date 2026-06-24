"""Telegram bot command, callback and media handlers.

Enforces strict user isolation: a Telegram user maps to one subadmin `User`
row, and every content/source operation is scoped to that user's `owner_id`.
Videos are copied into the configured storage channel; the channel message's
media metadata (`file_id`, `file_unique_id`, `file_size`, `channel_id`,
`message_id`) is then persisted into `video_sources`.
"""
from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from app.bot.keyboards import (
    confirm_delete,
    content_actions,
    content_list,
    main_menu,
)
from app.bot.state import PendingInput, UploadContext, bot_state
from app.bot.utils import human_size, parse_language, parse_quality
from app.config import get_settings
from app.core.security import create_stream_token
from app.db.base import AsyncSessionLocal
from app.services import content as content_svc
from app.services import password as pwd_svc
from app.services import subscription as sub_svc
from app.db.models import User

settings = get_settings()

WELCOME = (
    "\U0001F44B **Welcome to the Video Streaming Bot**\n\n"
    "Manage your content, upload videos (up to 4GB), and generate\n"
    "website player links \u2014 all from here.\n\n"
    "Use the buttons below to get started."
)

HELP = (
    "**Commands**\n\n"
    "\u2022 `/new Name` \u2014 create top-level content\n"
    "\u2022 `/new Movie/Season 1/Episode 1` \u2014 create a full path\n"
    "\u2022 `/subnew` \u2014 add nested content interactively\n"
    "\u2022 `/myvideos` \u2014 browse your content tree\n"
    "\u2022 `/links` \u2014 list your player links\n"
    "\u2022 `/setpassword` \u2014 set your web panel password\n\n"
    "**Uploading**\n"
    "Open a content item \u2192 tap *Upload Here* \u2192 send the video.\n"
    "Name files like `movie_hindi_720p.mp4` so language/quality are detected."
)


def _storage_channel() -> int:
    channels = settings.storage_channels
    if not channels:
        raise RuntimeError("STORAGE_CHANNEL_ID is not configured")
    return channels[0]


async def _resolve_user(message_or_cb) -> int:
    """Return the internal User.id for the Telegram sender (auto-registering)."""
    tg_user = message_or_cb.from_user
    async with AsyncSessionLocal() as db:
        user = await content_svc.get_or_create_user_by_tg(
            db, tg_user.id, tg_user.username or tg_user.first_name or "user"
        )
        await db.commit()
        return user.id


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
async def cmd_start(client: Client, message: Message) -> None:
    await _resolve_user(message)
    await message.reply_text(WELCOME, reply_markup=main_menu())


async def cmd_help(client: Client, message: Message) -> None:
    await message.reply_text(HELP)


async def cmd_new(client: Client, message: Message) -> None:
    owner_id = await _resolve_user(message)
    arg = message.text.split(maxsplit=1)
    if len(arg) < 2 or not arg[1].strip():
        bot_state.set_pending(
            message.from_user.id, PendingInput(action="new_root")
        )
        await message.reply_text(
            "Send the content name.\nTip: use `/new Movie/Season 1/Episode 1`"
            " to build a path in one go."
        )
        return
    await _create_path_and_reply(message, owner_id, arg[1].strip())


async def _create_path_and_reply(message: Message, owner_id: int, path: str) -> None:
    async with AsyncSessionLocal() as db:
        leaf = await content_svc.create_content_path(db, owner_id, path)
        await db.commit()
        await message.reply_text(
            f"\u2705 Created **{leaf.title}** (`{leaf.type.value}`).\n"
            f"Slug: `{leaf.slug}`",
            reply_markup=content_actions(leaf),
        )


async def cmd_subnew(client: Client, message: Message) -> None:
    owner_id = await _resolve_user(message)
    async with AsyncSessionLocal() as db:
        roots = await content_svc.list_user_contents(db, owner_id, parent_id=None)
    if not roots:
        await message.reply_text(
            "You have no content yet. Create one first with `/new Name`."
        )
        return
    await message.reply_text(
        "Choose a parent to add sub-content under:",
        reply_markup=content_list(roots),
    )


async def cmd_myvideos(client: Client, message: Message) -> None:
    owner_id = await _resolve_user(message)
    async with AsyncSessionLocal() as db:
        roots = await content_svc.list_user_contents(db, owner_id, parent_id=None)
        total = await content_svc.count_user_videos(db, owner_id)
    if not roots:
        await message.reply_text("You have no content yet. Use `/new Name`.")
        return
    await message.reply_text(
        f"**Your content** \u2014 {total} video source(s) total:",
        reply_markup=content_list(roots),
    )


async def cmd_setpassword(client: Client, message: Message) -> None:
    """Set/update the web panel password for the bot user."""
    await _resolve_user(message)
    arg = message.text.split(maxsplit=1)
    if len(arg) >= 2 and arg[1].strip():
        await _apply_password(message, arg[1].strip())
        return
    bot_state.set_pending(
        message.from_user.id, PendingInput(action="set_password")
    )
    await message.reply_text(
        "Send your new web panel password (min 6 chars).\n"
        "Your panel username is shown after it's set."
    )


async def _apply_password(message: Message, password: str) -> None:
    tg_id = message.from_user.id
    async with AsyncSessionLocal() as db:
        try:
            ok = await pwd_svc.set_password_by_tg(db, tg_id, password)
        except pwd_svc.PasswordError as exc:
            await message.reply_text(f"\u274C {exc}")
            return
        if not ok:
            await message.reply_text("\u274C Account not found. Send /start first.")
            return
        await db.commit()
        user = await content_svc.get_or_create_user_by_tg(
            db, tg_id, message.from_user.username or "user"
        )
    await message.reply_text(
        "\u2705 Password set.\n"
        f"Panel login \u2014 username: `{user.username}`\n"
        f"URL: `{settings.BASE_URL}/login`"
    )


async def cmd_links(client: Client, message: Message) -> None:
    owner_id = await _resolve_user(message)
    async with AsyncSessionLocal() as db:
        roots = await content_svc.list_user_contents(db, owner_id, parent_id=None)
    if not roots:
        await message.reply_text("No content yet. Use `/new Name`.")
        return
    lines = ["**\U0001F517 Your player links**\n"]
    for c in roots:
        lines.append(f"\u2022 **{c.title}**\n  `{settings.BASE_URL}/watch/{c.slug}`")
    await message.reply_text("\n".join(lines), disable_web_page_preview=True)


# --------------------------------------------------------------------------- #
# Media upload
# --------------------------------------------------------------------------- #
async def on_media(client: Client, message: Message) -> None:
    tg_id = message.from_user.id
    target = bot_state.get_upload_target(tg_id)
    if target is None:
        await message.reply_text(
            "Open a content item and tap *Upload Here* before sending a video."
        )
        return

    owner_id = await _resolve_user(message)
    media = message.video or message.document
    if media is None:
        await message.reply_text("Please send a video or document file.")
        return

    # Enforce subscription limits BEFORE storing anything in the channel.
    async with AsyncSessionLocal() as db:
        user = await db.get(User, owner_id)
        check = await sub_svc.can_upload(db, user)
    if not check.allowed:
        await message.reply_text(
            f"\u26D4 Upload blocked.\n{check.reason}\n\n"
            f"Used: {check.used}/{check.limit}. "
            "Upgrade your plan from the web panel to add more."
        )
        return

    status = await message.reply_text("\u23F3 Storing in channel...")
    try:
        channel_id = _storage_channel()
        # Copy the media into the storage channel; this gives us a stable
        # channel message we can stream from later via MTProto.
        stored = await message.copy(channel_id)
    except Exception as exc:  # noqa: BLE001
        await status.edit_text(f"\u274C Failed to store in channel: {exc}")
        return

    stored_media = stored.video or stored.document
    file_name = getattr(stored_media, "file_name", None) or getattr(media, "file_name", None)

    async with AsyncSessionLocal() as db:
        content = await content_svc.get_owned_content(db, owner_id, target.content_id)
        if content is None:
            await status.edit_text("\u274C Target content not found or not yours.")
            return
        source = await content_svc.add_video_source(
            db,
            content,
            channel_id=channel_id,
            message_id=stored.id,
            file_id=stored_media.file_id,
            file_unique_id=stored_media.file_unique_id,
            file_size=getattr(stored_media, "file_size", 0) or 0,
            file_name=file_name,
            mime_type=getattr(stored_media, "mime_type", None),
            language=parse_language(file_name),
            quality=parse_quality(file_name),
        )
        await db.commit()
        token = create_stream_token(source.id)
        await status.edit_text(
            "\u2705 **Video added**\n"
            f"\u2022 Content: **{content.title}**\n"
            f"\u2022 Language: `{source.language}`  Quality: `{source.quality}`\n"
            f"\u2022 Size: `{human_size(source.file_size)}`\n"
            f"\u2022 Stream test: `{settings.BASE_URL}/stream/{source.id}?token={token}`",
            disable_web_page_preview=True,
        )


# --------------------------------------------------------------------------- #
# Free-text replies (for /new and /subnew prompts)
# --------------------------------------------------------------------------- #
async def on_text(client: Client, message: Message) -> None:
    tg_id = message.from_user.id
    if not bot_state.has_pending(tg_id):
        return  # not awaiting input; ignore
    pending = bot_state.pop_pending(tg_id)
    owner_id = await _resolve_user(message)
    title = message.text.strip()
    if not title:
        await message.reply_text("Name cannot be empty.")
        return

    if pending.action == "set_password":
        await _apply_password(message, title)
        return
    if pending.action == "new_root":
        await _create_path_and_reply(message, owner_id, title)
    elif pending.action == "subnew_child":
        async with AsyncSessionLocal() as db:
            parent = await content_svc.get_owned_content(
                db, owner_id, pending.parent_id
            )
            if parent is None:
                await message.reply_text("\u274C Parent not found.")
                return
            child = await content_svc.create_content_node(
                db, owner_id, title, parent=parent
            )
            await db.commit()
            await message.reply_text(
                f"\u2705 Added **{child.title}** under **{parent.title}**.",
                reply_markup=content_actions(child),
            )


# --------------------------------------------------------------------------- #
# Callback queries (inline buttons)
# --------------------------------------------------------------------------- #
async def on_callback(client: Client, cb: CallbackQuery) -> None:
    data = cb.data or ""
    tg_id = cb.from_user.id
    owner_id = await _resolve_user(cb)

    if data == "menu:home":
        await cb.message.edit_text(WELCOME, reply_markup=main_menu())
    elif data in ("menu:content", "menu:videos"):
        async with AsyncSessionLocal() as db:
            roots = await content_svc.list_user_contents(db, owner_id, None)
        if not roots:
            await cb.answer("No content yet. Use /new", show_alert=True)
        else:
            await cb.message.edit_text(
                "**Your content:**", reply_markup=content_list(roots)
            )
    elif data == "menu:new":
        bot_state.set_pending(tg_id, PendingInput(action="new_root"))
        await cb.message.edit_text(
            "Send the content name (or a path like `Movie/Season 1/Episode 1`)."
        )
    elif data == "menu:links":
        await cmd_links(client, cb.message.reply_to_message or cb.message)
        await cb.answer()
    elif data == "menu:help":
        await cb.message.edit_text(HELP, reply_markup=main_menu())
    elif data.startswith("open:"):
        await _open_content(cb, owner_id, int(data.split(":", 1)[1]))
    elif data.startswith("sub:"):
        cid = int(data.split(":", 1)[1])
        bot_state.set_pending(
            tg_id, PendingInput(action="subnew_child", parent_id=cid)
        )
        await cb.message.reply_text("Send the name for the new sub-content:")
        await cb.answer()
    elif data.startswith("upload:"):
        cid = int(data.split(":", 1)[1])
        async with AsyncSessionLocal() as db:
            content = await content_svc.get_owned_content(db, owner_id, cid)
        if content is None:
            await cb.answer("Not found", show_alert=True)
            return
        bot_state.set_upload_target(
            tg_id, UploadContext(content_id=cid, content_title=content.title)
        )
        await cb.message.reply_text(
            f"\U0001F4E4 Send the video now \u2014 it will be attached to"
            f" **{content.title}**."
        )
        await cb.answer()
    elif data.startswith("link:"):
        cid = int(data.split(":", 1)[1])
        async with AsyncSessionLocal() as db:
            content = await content_svc.get_owned_content(db, owner_id, cid)
        if content is None:
            await cb.answer("Not found", show_alert=True)
            return
        await cb.message.reply_text(
            f"\U0001F517 **{content.title}**\n"
            f"Watch: `{settings.BASE_URL}/watch/{content.slug}`\n"
            f"Embed: `{settings.BASE_URL}/embed/{content.slug}`",
            disable_web_page_preview=True,
        )
        await cb.answer()
    elif data.startswith("del:"):
        cid = int(data.split(":", 1)[1])
        await cb.message.edit_text(
            "\u26A0\uFE0F Delete this content and all its sub-content/videos?",
            reply_markup=confirm_delete(cid),
        )
    elif data.startswith("delyes:"):
        cid = int(data.split(":", 1)[1])
        async with AsyncSessionLocal() as db:
            content = await content_svc.get_owned_content(db, owner_id, cid)
            if content is None:
                await cb.answer("Not found", show_alert=True)
                return
            await db.delete(content)
            await db.commit()
        await cb.message.edit_text("\U0001F5D1 Deleted.", reply_markup=main_menu())
    else:
        await cb.answer()


async def _open_content(cb: CallbackQuery, owner_id: int, content_id: int) -> None:
    async with AsyncSessionLocal() as db:
        content = await content_svc.get_owned_content(db, owner_id, content_id)
        if content is None:
            await cb.answer("Not found or not yours", show_alert=True)
            return
        children = await content_svc.list_user_contents(db, owner_id, content_id)
        sources = content.sources

    text = [f"**{content.title}**  (`{content.type.value}`)"]
    if sources:
        text.append("\n**Video sources:**")
        for s in sources:
            text.append(
                f"  \u2022 `{s.language}` / `{s.quality}` \u2014 {human_size(s.file_size)}"
            )
    if children:
        text.append(f"\n**Sub-content:** {len(children)} item(s) below.")
    if not sources and not children:
        text.append("\n_No videos or sub-content yet._")

    markup = content_actions(content)
    if children:
        # Append children as openable buttons.
        from pyrogram.types import InlineKeyboardButton

        rows = list(markup.inline_keyboard)
        child_rows = [
            [InlineKeyboardButton(f"\U0001F4C2 {c.title}", callback_data=f"open:{c.id}")]
            for c in children
        ]
        markup.inline_keyboard = child_rows + rows
    await cb.message.edit_text("\n".join(text), reply_markup=markup)
    await cb.answer()


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #
def register_handlers(app: Client) -> None:
    app.on_message(filters.command("start") & filters.private)(cmd_start)
    app.on_message(filters.command("help") & filters.private)(cmd_help)
    app.on_message(filters.command("new") & filters.private)(cmd_new)
    app.on_message(filters.command("subnew") & filters.private)(cmd_subnew)
    app.on_message(filters.command("myvideos") & filters.private)(cmd_myvideos)
    app.on_message(filters.command("links") & filters.private)(cmd_links)
    app.on_message(filters.command("setpassword") & filters.private)(cmd_setpassword)
    app.on_message(
        (filters.video | filters.document) & filters.private
    )(on_media)
    app.on_message(
        filters.text & filters.private & ~filters.command(
            ["start", "help", "new", "subnew", "myvideos", "links", "setpassword"]
        )
    )(on_text)
    app.on_callback_query()(on_callback)
