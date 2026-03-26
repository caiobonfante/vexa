# Telegram Bot

## Why

Agents are only useful if you can reach them where you already are. The dashboard requires a browser, and raw API calls require a terminal. Telegram puts your agent in your pocket — message it from your phone to join a meeting, ask about a transcript, or trigger automation. It's also the entry point for the scheduler: when a scheduled job completes, it sends results back through Telegram so you see them without checking a dashboard.

## What

Telegram interface for the Vexa Agent. Receives messages from Telegram users, forwards them to the Agent API, and streams responses back with progressive message editing. Also exposes an internal trigger API for scheduled messages.

## What

### Commands

| Command | Description |
|---------|-------------|
| `/start` | Show bot info and user ID |
| `/reset` | Reset the chat session (keeps workspace files) |

Text messages are forwarded to the Agent API as chat turns. Responses stream back with a stop button for interruption.

## Internal Trigger API

A FastAPI server runs alongside the Telegram bot for programmatic message injection (used by the scheduler).

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/internal/trigger` | Send a message to a user's agent via Telegram |
| `GET` | `/health` | Health check |

## How

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | — | **Required.** Telegram Bot API token |
| `CHAT_API_URL` | `http://agent-api:8100` | Agent API base URL |
| `BOT_API_TOKEN` | — | API key for authenticating with the Agent API |
| `CHAT_DEFAULT_USER_ID` | — | Default Vexa user ID (all chats map to this user) |
| `CHAT_USER_MAP` | `{}` | JSON map of `{"telegram_chat_id": "vexa_user_id"}` |
| `TELEGRAM_BOT_PORT` | `8200` | Port for the internal trigger API |
| `LOG_LEVEL` | `INFO` | Log level |

### Run

```bash
cd services/telegram-bot
pip install -r requirements.txt
python bot.py
```

Requires the Agent API to be running. Set `TELEGRAM_BOT_TOKEN` to a valid bot token from [@BotFather](https://t.me/BotFather).
