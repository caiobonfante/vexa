# Calendar Service

Syncs Google Calendar events and automatically schedules meeting bots to join upcoming calls. Runs a background sync loop that polls all connected users on a configurable interval.

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/calendar/connect` | Trigger initial sync after OAuth connection |
| `GET` | `/calendar/status` | Check if a user has a calendar connected |
| `GET` | `/calendar/events` | List upcoming calendar events for a user |
| `PUT` | `/calendar/preferences` | Set auto-join and lead time preferences |
| `DELETE` | `/calendar/disconnect` | Remove OAuth tokens and stop syncing |
| `GET` | `/health` | Health check |

All endpoints accept `user_id` as a query parameter.

## How It Works

1. Users connect their Google Calendar via OAuth (refresh token stored in the `users.data` JSONB column).
2. A background loop syncs calendar events for all connected users at a regular interval.
3. For events with meeting URLs (Zoom, Teams, Meet), bots are scheduled to join automatically based on user preferences (auto-join enabled, lead time in minutes).

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Log level |
| `SYNC_INTERVAL_SECONDS` | `300` | Seconds between calendar sync cycles |
| `DATABASE_URL` | — | PostgreSQL connection string (via shared_models) |

## Running Locally

```bash
cd services/calendar-service
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8050 --reload
```

Requires PostgreSQL with the shared database schema initialized.
