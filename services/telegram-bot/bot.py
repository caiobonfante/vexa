"""Vexa Telegram Bot — thin client on the Agent API.

Adapted from Quorum's bot.py. Receives Telegram messages,
streams them through the Agent API, progressively edits responses.
"""

import asyncio
import html
import json
import logging
import os
import re
from dataclasses import dataclass, field

import httpx
from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("vexa_tg_bot")

# --- Config ---

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_API_URL = os.getenv("CHAT_API_URL", "http://agent-api:8100")
BOT_API_TOKEN = os.getenv("BOT_API_TOKEN", "")
DEFAULT_USER_ID = os.getenv("CHAT_DEFAULT_USER_ID", "")

# JSON map: {"telegram_chat_id": "vexa_user_id", ...}
_raw_map = os.getenv("CHAT_USER_MAP", "{}")
USER_MAP: dict[int, str] = {}
try:
    for k, v in json.loads(_raw_map).items():
        USER_MAP[int(k)] = str(v)
except Exception:
    pass

EDIT_INTERVAL = 1.0  # seconds between Telegram message edits

# --- Tool labels ---

_TOOL_LABELS = {
    "Read": "Reading",
    "Write": "Writing",
    "Edit": "Editing",
    "Glob": "Finding files",
    "Grep": "Searching",
    "WebSearch": "Searching web",
    "WebFetch": "Fetching page",
    "Bash": "Running command",
}


def _format_activity(tool: str, summary: str) -> str:
    label = _TOOL_LABELS.get(tool, tool)
    if summary:
        short = summary[:50] + "\u2026" if len(summary) > 50 else summary
        return f"{label}: {short}"
    return f"{label}\u2026"


# --- Markdown to Telegram HTML ---

def _to_html(text: str) -> str:
    text = html.escape(text)
    # Code blocks
    text = re.sub(
        r"```(?:\w+)?\n(.*?)```",
        lambda m: f"<pre>{m.group(1)}</pre>",
        text, flags=re.DOTALL,
    )
    # Inline code
    text = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", text)
    # Headers
    text = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)
    # Italic
    text = re.sub(r"\*([^*\n]+)\*", r"<i>\1</i>", text)
    # Links
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def _truncate(text: str, limit: int = 4000) -> str:
    """Telegram messages max 4096 chars. Truncate with indicator."""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n<i>[truncated]</i>"


# --- Per-chat state ---

@dataclass
class ChatState:
    user_id: str
    stream_task: asyncio.Task | None = None
    bot_msg_id: int | None = None
    accumulated: str = ""
    pending: str | None = None


_states: dict[int, ChatState] = {}


def _get_state(chat_id: int, user_id: str) -> ChatState:
    if chat_id not in _states:
        _states[chat_id] = ChatState(user_id=user_id)
    return _states[chat_id]


def _get_user_id(update: Update) -> str:
    if DEFAULT_USER_ID:
        return DEFAULT_USER_ID
    chat_id = update.effective_chat.id if update.effective_chat else 0
    if chat_id in USER_MAP:
        return USER_MAP[chat_id]
    tg_user = update.effective_user
    if tg_user:
        return f"tg_{tg_user.id}"
    return f"tg_{chat_id}"


# --- Keyboard helpers ---

def _kb_stop():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\u23f9 Stop", callback_data="stop")]
    ])


# --- SSE streaming ---

async def _stream_response(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    state: ChatState,
    message: str,
) -> None:
    bot = context.bot
    payload = {"user_id": state.user_id, "message": message}

    state.accumulated = ""
    last_edit = 0.0
    current_activity = ""

    try:
        _headers = {"X-API-Key": BOT_API_TOKEN} if BOT_API_TOKEN else {}
        async with httpx.AsyncClient(timeout=None, headers=_headers) as client:
            async with client.stream("POST", f"{CHAT_API_URL}/api/chat", json=payload) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise RuntimeError(f"API error {resp.status_code}: {body.decode()[:200]}")

                # Manual SSE parsing (handles large lines)
                buf = b""
                async for chunk in resp.aiter_bytes():
                    buf += chunk
                    while b"\n" in buf:
                        raw_line, buf = buf.split(b"\n", 1)
                        line = raw_line.decode("utf-8", errors="replace").rstrip("\r")
                        if not line.startswith("data: "):
                            continue
                        try:
                            event = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue

                        etype = event.get("type")

                        if etype == "text_delta":
                            state.accumulated += event.get("text", "")
                            current_activity = ""

                            now = asyncio.get_event_loop().time()
                            if now - last_edit >= EDIT_INTERVAL:
                                display = f"\u23f3 {state.accumulated}"
                                await _safe_edit(bot, chat_id, state, display)
                                last_edit = now

                        elif etype == "tool_use":
                            current_activity = _format_activity(
                                event.get("tool", ""), event.get("summary", "")
                            )
                            now = asyncio.get_event_loop().time()
                            if now - last_edit >= EDIT_INTERVAL:
                                prefix = state.accumulated + "\n\n" if state.accumulated else ""
                                display = f"\u23f3 {prefix}\u2699\ufe0f {current_activity}"
                                await _safe_edit(bot, chat_id, state, display)
                                last_edit = now

                        elif etype in ("done", "stream_end"):
                            break

                        elif etype == "error":
                            state.accumulated += f"\n\n\u26a0\ufe0f {event.get('message', 'Unknown error')}"
                            break

        # Final formatted message
        final = state.accumulated or "(no response)"
        final_html = _truncate(_to_html(final))
        await _safe_edit(bot, chat_id, state, final_html, parse_mode="HTML", markup=None)

    except asyncio.CancelledError:
        # Interrupted — show partial
        partial = state.accumulated or "\u2026"
        partial_html = _truncate(_to_html(partial) + "\n\n<i>[stopped]</i>")
        await _safe_edit(bot, chat_id, state, partial_html, parse_mode="HTML", markup=None)
    except Exception as e:
        logger.error(f"Stream error for {state.user_id}: {e}", exc_info=True)
        await _safe_edit(bot, chat_id, state, f"\u26a0\ufe0f Error: {html.escape(str(e))}", parse_mode="HTML", markup=None)


async def _safe_edit(
    bot: Bot,
    chat_id: int,
    state: ChatState,
    text: str,
    parse_mode: str | None = None,
    markup=_kb_stop,
):
    """Edit or send message, swallowing transient errors."""
    if markup is _kb_stop:
        markup = _kb_stop()
    try:
        if state.bot_msg_id:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=state.bot_msg_id,
                text=text[:4096],
                parse_mode=parse_mode,
                reply_markup=markup,
                disable_web_page_preview=True,
            )
        else:
            msg = await bot.send_message(
                chat_id=chat_id,
                text=text[:4096],
                parse_mode=parse_mode,
                reply_markup=markup,
                disable_web_page_preview=True,
            )
            state.bot_msg_id = msg.message_id
    except Exception:
        pass


# --- Start stream with typing indicator ---

async def _start_stream(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    state: ChatState,
    message: str,
) -> None:
    bot = context.bot

    # Typing keepalive
    async def _typing():
        while True:
            try:
                await bot.send_chat_action(chat_id=chat_id, action="typing")
            except Exception:
                pass
            await asyncio.sleep(4)

    # Send initial hourglass
    thinking = await bot.send_message(chat_id=chat_id, text="\u23f3", reply_markup=_kb_stop())
    state.bot_msg_id = thinking.message_id

    typing_task = asyncio.create_task(_typing())

    async def _run():
        try:
            await _stream_response(chat_id, context, state, message)
        finally:
            typing_task.cancel()

    state.stream_task = asyncio.create_task(_run())


# --- Interrupt ---

async def _interrupt(state: ChatState):
    try:
        _headers = {"X-API-Key": BOT_API_TOKEN} if BOT_API_TOKEN else {}
        async with httpx.AsyncClient(timeout=10, headers=_headers) as client:
            await client.request(
                "DELETE", f"{CHAT_API_URL}/api/chat",
                json={"user_id": state.user_id},
            )
    except Exception:
        pass
    if state.stream_task and not state.stream_task.done():
        state.stream_task.cancel()
        try:
            await state.stream_task
        except (asyncio.CancelledError, Exception):
            pass
    state.stream_task = None


# --- Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _get_user_id(update)
    await update.message.reply_text(
        f"Vexa Agent ready.\n\n"
        f"Your user ID: <code>{html.escape(user_id)}</code>\n"
        f"Send me a message and I'll forward it to your agent container.",
        parse_mode="HTML",
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _get_user_id(update)
    chat_id = update.effective_chat.id
    state = _get_state(chat_id, user_id)
    await _interrupt(state)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{CHAT_API_URL}/api/chat/reset",
                json={"user_id": user_id},
            )
    except Exception:
        pass
    await update.message.reply_text("Session reset. Files in workspace kept.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    user_id = _get_user_id(update)
    state = _get_state(chat_id, user_id)

    text = None
    if update.message.text:
        text = update.message.text.strip()

    if not text:
        await update.message.reply_text("Send me a text message.")
        return

    # If streaming: queue this message
    if state.stream_task and not state.stream_task.done():
        state.pending = text
        return

    await _start_stream(chat_id, context, state, text)


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    chat_id = query.message.chat_id
    user_id = _get_user_id(update)
    state = _get_state(chat_id, user_id)

    if query.data == "stop":
        await _interrupt(state)

        # If there was a pending message, start it
        pending = state.pending
        state.pending = None
        if pending:
            await _start_stream(chat_id, context, state, pending)


# --- Internal trigger API (for scheduler) ---

from fastapi import FastAPI as TriggerFastAPI
import uvicorn

trigger_app = TriggerFastAPI()

# Global ref to telegram app — set in main()
_tg_app: Application | None = None

TRIGGER_PORT = int(os.getenv("TELEGRAM_BOT_PORT", "8200"))


def _resolve_chat_id(user_id: str) -> int | None:
    """Find the Telegram chat_id for a given user_id."""
    # Check USER_MAP (reverse lookup)
    for chat_id, uid in USER_MAP.items():
        if uid == user_id:
            return chat_id
    # Check DEFAULT_USER_ID
    if DEFAULT_USER_ID == user_id:
        # Find any chat_id that has state with this user_id
        for chat_id, state in _states.items():
            if state.user_id == user_id:
                return chat_id
    # Check existing states
    for chat_id, state in _states.items():
        if state.user_id == user_id:
            return chat_id
    return None


@trigger_app.post("/internal/trigger")
async def trigger_chat(request: dict):
    """Receive a scheduled trigger and start a chat turn for the user."""
    user_id = request.get("user_id")
    message = request.get("message", "Scheduled reminder")

    if not user_id or not _tg_app:
        return {"status": "error", "detail": "bot not ready or missing user_id"}

    chat_id = _resolve_chat_id(user_id)
    if not chat_id:
        logger.warning(f"Trigger: no chat_id for user {user_id}")
        return {"status": "error", "detail": f"no chat_id for user {user_id}"}

    state = _get_state(chat_id, user_id)

    # If already streaming, queue it
    if state.stream_task and not state.stream_task.done():
        state.pending = message
        return {"status": "queued"}

    # Start a streaming turn using the global telegram app context
    context = _tg_app  # Application has .bot attribute
    await _start_stream_triggered(chat_id, context.bot, state, message)
    return {"status": "triggered"}


async def _start_stream_triggered(chat_id: int, bot: Bot, state: ChatState, message: str):
    """Start a chat stream from a trigger (no Update/context — use bot directly)."""

    # Create a minimal context-like wrapper
    class _FakeContext:
        def __init__(self, b):
            self.bot = b

    fake_ctx = _FakeContext(bot)

    async def _typing():
        while True:
            try:
                await bot.send_chat_action(chat_id=chat_id, action="typing")
            except Exception:
                pass
            await asyncio.sleep(4)

    # Send initial message
    prefix_html = f"\U0001f514 <i>{html.escape(message[:100])}</i>\n\n"
    thinking = await bot.send_message(chat_id=chat_id, text=f"\U0001f514 {message[:100]}\n\n\u23f3")
    state.bot_msg_id = thinking.message_id

    typing_task = asyncio.create_task(_typing())

    async def _run():
        try:
            await _stream_response(chat_id, fake_ctx, state, message)
        finally:
            typing_task.cancel()

    state.stream_task = asyncio.create_task(_run())


@trigger_app.get("/health")
async def trigger_health():
    return {"status": "ok", "bot_ready": _tg_app is not None}


# --- Main ---

async def main() -> None:
    global _tg_app

    from telegram.request import HTTPXRequest
    request = HTTPXRequest(connect_timeout=30, read_timeout=30)

    tg_app = Application.builder().token(BOT_TOKEN).request(request).build()
    _tg_app = tg_app

    tg_app.add_handler(CommandHandler("start", start_command))
    tg_app.add_handler(CommandHandler("reset", reset_command))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    tg_app.add_handler(CallbackQueryHandler(handle_button))

    logger.info(f"Bot starting (API: {CHAT_API_URL})")

    async with tg_app:
        await tg_app.bot.set_my_commands([
            ("start", "Show info"),
            ("reset", "Reset session (keeps files)"),
        ])
        await tg_app.start()
        await tg_app.updater.start_polling(drop_pending_updates=True)
        logger.info("Bot is polling. Ctrl+C to stop.")

        # Start trigger API server in background
        config = uvicorn.Config(trigger_app, host="0.0.0.0", port=TRIGGER_PORT, log_level="info")
        server = uvicorn.Server(config)
        trigger_task = asyncio.create_task(server.serve())
        logger.info(f"Trigger API listening on port {TRIGGER_PORT}")

        try:
            await asyncio.Event().wait()
        finally:
            server.should_exit = True
            await trigger_task
            await tg_app.updater.stop()
            await tg_app.stop()


if __name__ == "__main__":
    asyncio.run(main())
