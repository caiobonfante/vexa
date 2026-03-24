---
title: 'How to Build a Meeting Bot with Python in 10 Minutes'
date: '2026-02-21'
author: 'Dmitry Grankin'
authorImage: '/dmitry-grankin.jpg'
authorLinkedIn: 'https://www.linkedin.com/in/dmitry-grankin/'
heroImage: '/assets/meeting-bot-python-tutorial.png'
slug: 'how-to-build-a-meeting-bot-with-python'
summary: "Build a meeting bot that joins Google Meet or Microsoft Teams, transcribes in real-time, and streams results via WebSocket — all in Python with 30 lines of code."
---

Want to build a **meeting bot with Python** that joins Google Meet or Microsoft Teams, captures audio, and delivers real-time transcripts? With the open-source **[Vexa API](https://github.com/Vexa-ai/vexa)**, you can do it in under 30 lines of code.

No browser automation hacks. No Selenium. No Puppeteer. Just a REST call to send the bot, and a WebSocket connection to stream transcripts in real-time.

---

## What You'll Build

By the end of this tutorial, you'll have a Python script that:

1. **Sends a bot** to any Google Meet or Microsoft Teams meeting
2. **Streams transcripts in real-time** via WebSocket (sub-second latency)
3. **Identifies speakers** automatically
4. **Retrieves the full transcript** after the meeting ends

All of this works with both the hosted API (free tier available) and the self-hosted open-source deployment.

---

## Prerequisites

- **Python 3.8+** installed
- **A Vexa API key** — get one free at [vexa.ai/dashboard/api-keys](https://vexa.ai/dashboard/api-keys)
- **A meeting link** to test with (Google Meet or Microsoft Teams)

Install the required packages:

```bash
pip install requests websockets
```

---

## Step 1: Send a Bot to a Meeting

The Vexa API works by sending a bot participant into your meeting. The bot joins like any other attendee, captures audio, and streams transcripts back to you via API.

```python
import requests

API_BASE = "https://api.cloud.vexa.ai"
API_KEY = "your-api-key-here"

# Send a bot to Google Meet
response = requests.post(
    f"{API_BASE}/bots",
    headers={
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    },
    json={
        "platform": "google_meet",
        "native_meeting_id": "abc-defg-hij",  # from meet.google.com/abc-defg-hij
        "transcribe_enabled": True,
        "transcription_tier": "realtime"
    }
)

bot = response.json()
print(f"Bot ID: {bot['id']}, Status: {bot['status']}")
```

That's it. The bot joins the meeting and starts transcribing.

### Meeting ID Reference

| Platform | Meeting URL | `native_meeting_id` |
|----------|------------|---------------------|
| Google Meet | `meet.google.com/abc-defg-hij` | `abc-defg-hij` |
| Microsoft Teams | `teams.live.com/meet/1234567890?p=XYZ` | `1234567890` |

For Teams, add the `passcode` field (the `p=` value from the URL):

```python
response = requests.post(
    f"{API_BASE}/bots",
    headers={
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    },
    json={
        "platform": "teams",
        "native_meeting_id": "1234567890",
        "passcode": "XYZ",
        "transcribe_enabled": True,
        "transcription_tier": "realtime"
    }
)
```

---

## Step 2: Stream Transcripts in Real-Time

Now connect via WebSocket to receive transcripts as people speak — with sub-second latency:

```python
import asyncio
import json
import websockets

API_KEY = "your-api-key-here"
WS_URL = "wss://api.cloud.vexa.ai/ws"

async def stream_transcript(meeting_id: str):
    async with websockets.connect(
        WS_URL,
        extra_headers=[("X-API-Key", API_KEY)]
    ) as ws:
        # Subscribe to the meeting
        await ws.send(json.dumps({
            "action": "subscribe",
            "meetings": [{
                "platform": "google_meet",
                "native_id": meeting_id
            }]
        }))

        # Receive live transcript updates
        async for message in ws:
            event = json.loads(message)

            if event["type"] == "transcript.mutable":
                for segment in event["payload"]["segments"]:
                    print(f'{segment["speaker"]}: {segment["text"]}')

            elif event["type"] == "meeting.status":
                status = event["payload"]["status"]
                print(f"[Meeting status: {status}]")
                if status == "completed":
                    break

asyncio.run(stream_transcript("abc-defg-hij"))
```

When you run this, you'll see output like:

```
[Meeting status: active]
Alice: Good morning everyone, let's get started.
Bob: Sure, I have the quarterly numbers ready.
Alice: Great, can you share your screen?
[Meeting status: completed]
```

Each transcript segment includes the speaker name, text, timestamps, and language — all delivered in real-time.

---

## Step 3: Get the Full Transcript

After the meeting ends, retrieve the complete transcript with all segments:

```python
response = requests.get(
    f"{API_BASE}/transcripts/google_meet/abc-defg-hij",
    headers={"X-API-Key": API_KEY}
)

transcript = response.json()

for segment in transcript["segments"]:
    timestamp = segment["absolute_start_time"][:19]
    print(f"[{timestamp}] {segment['speaker']}: {segment['text']}")
```

---

## Complete Script: Meeting Bot in 30 Lines

Here's everything combined into a single script:

```python
import requests
import asyncio
import json
import websockets

API_BASE = "https://api.cloud.vexa.ai"
API_KEY = "your-api-key-here"
WS_URL = "wss://api.cloud.vexa.ai/ws"
MEETING_ID = "abc-defg-hij"

# 1. Send bot to meeting
bot = requests.post(
    f"{API_BASE}/bots",
    headers={"Content-Type": "application/json", "X-API-Key": API_KEY},
    json={"platform": "google_meet", "native_meeting_id": MEETING_ID,
          "transcribe_enabled": True, "transcription_tier": "realtime"}
).json()
print(f"Bot sent: {bot['id']}")

# 2. Stream real-time transcripts
async def stream():
    async with websockets.connect(WS_URL, extra_headers=[("X-API-Key", API_KEY)]) as ws:
        await ws.send(json.dumps({
            "action": "subscribe",
            "meetings": [{"platform": "google_meet", "native_id": MEETING_ID}]
        }))
        async for msg in ws:
            event = json.loads(msg)
            if event["type"] == "transcript.mutable":
                for s in event["payload"]["segments"]:
                    print(f'{s["speaker"]}: {s["text"]}')
            elif event["type"] == "meeting.status" and event["payload"]["status"] == "completed":
                break

asyncio.run(stream())

# 3. Get full transcript
transcript = requests.get(
    f"{API_BASE}/transcripts/google_meet/{MEETING_ID}",
    headers={"X-API-Key": API_KEY}
).json()
print(f"\nFull transcript: {len(transcript['segments'])} segments")
```

Save as `meeting_bot.py`, replace `your-api-key-here` with your key and `abc-defg-hij` with a real meeting ID, and run:

```bash
python meeting_bot.py
```

---

## What Can You Build With This?

Once you have real-time meeting transcripts, the possibilities open up:

- **AI meeting notes** — pipe transcripts to GPT-4 or Claude for automatic summaries
- **CRM integration** — auto-log meeting notes to Salesforce or HubSpot
- **Slack alerts** — post key decisions to a channel in real-time
- **Compliance recording** — archive transcripts for regulated industries
- **Sales coaching** — analyze talk ratios and objection patterns
- **Custom meeting agents** — build AI that participates in meetings via the MCP server

---

## Self-Hosted Option

Don't want to send data to a cloud API? Vexa is fully open-source (Apache 2.0) and self-hostable. Deploy on your own infrastructure with Docker:

```bash
git clone https://github.com/Vexa-ai/vexa.git
cd vexa
make setup
make up
```

The API endpoints are identical — just change `API_BASE` to `http://localhost:8056`. Your data never leaves your network.

---

## Next Steps

- **[Get your API key](https://vexa.ai/dashboard/api-keys)** — free tier available, no credit card required
- **[Full API documentation](https://docs.vexa.ai)** — all endpoints, parameters, and examples
- **[GitHub repository](https://github.com/Vexa-ai/vexa)** — star the project, open issues, contribute
- **[MCP Server setup](https://vexa.ai/blog/claude-desktop-vexa-mcp-google-meet-transcripts)** — connect Vexa to Claude Desktop for AI-powered meeting analysis
- **[Self-hosted deployment guide](https://vexa.ai/blog/how-to-set-up-self-hosted-meeting-transcription-5-minutes)** — full setup walkthrough

---

## FAQ

### How much does the Vexa API cost?

The hosted API has a free trial with 1 hour of transcription. The Bot Service is $0.45/hr (including post-meeting transcription and 12 months of storage), with a real-time add-on at +$0.05/hr for sub-5s latency. Self-hosted is completely free (Apache 2.0).

### Which meeting platforms are supported?

Google Meet and Microsoft Teams, with Zoom support coming soon. The same API works across all platforms.

### Can I use this for production applications?

Yes. Vexa powers production workloads for enterprises. The hosted API includes SLA guarantees, and the self-hosted option gives you full control over uptime and scaling.

### How accurate is the transcription?

Vexa uses Whisper for transcription, supporting 100+ languages with industry-leading accuracy. Speaker diarization is included automatically.

### Is the meeting bot visible to participants?

Yes, the bot joins as a named participant (you can customize the name). Meeting organizers can see it in the participant list, which is important for consent and transparency.
