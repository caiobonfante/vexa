---
title: 'Google Meet Transcription n8n workflow'
date: '2025-08-13'
author: 'Dmitry Grankin'
authorImage: '/dmitry-grankin.jpg'
authorLinkedIn: 'https://www.linkedin.com/in/dmitry-grankin/'
heroImage: '/assets/google-meet-transcription-n8n-workflow-diagram.png'
slug: 'google-meet-transcription-n8n-workflow'
summary: "Learn how to automate Google Meet transcripts in n8n with Vexa's open‑source, Apache‑2.0 API."
---

Looking for the easiest way to add **Google Meet transcription to your n8n workflows**?
With the open‑source **[Vexa API](https://github.com/Vexa-ai/vexa)** you can drop a bot into any Meet and capture **real‑time and post‑meeting transcripts**—all via **two REST calls** already wired into a ready‑to‑import workflow.

## Quick Overview (Why Teams Search "Google Meet Transcript Automation")

- **Join & transcribe in minutes** – No browser extensions or complex node setup
- **Real‑time triggers + full post‑meeting archive**  
- **Apache‑2.0 license** – fork it, self‑host it, scale it  
- **Plugs into any n8n flow** – Slack, Notion, CRM, AI agents

## How It Works (Under the Hood)

<table>
  <thead>
    <tr>
      <th>Node Name</th>
      <th>REST Call</th>
      <th>Function</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>Join Meet</code></td>
      <td><code>POST /bots</code></td>
      <td>Deploys a headless transcription bot into the specified Google Meet.</td>
    </tr>
    <tr>
      <td><code>Get Transcript</code></td>
      <td><code>GET /transcripts/google_meet/{meeting_id}</code></td>
      <td>Retrieves the <strong>full transcript</strong> after the meeting ends.</td>
    </tr>
  </tbody>
</table>

Both endpoints need one header:

```http
-H 'X-API-Key: YOUR_API_KEY_HERE'
```

Get your key in seconds → [https://vexa.ai/dashboard/api-keys](https://vexa.ai/dashboard/api-keys)

## 5‑Minute Setup (Video Demo Included)

1. Download the [workflow JSON](https://github.com/Vexa-ai/n8n/blob/main/google_meet_with_vexa_API.json)
2. Import into n8n (drag‑and‑drop)
3. Paste your API key in both HTTP Request nodes
4. Add a Google Meet link
5. Execute – the bot joins, the transcript flows

[Watch the setup demo »](https://youtu.be/xYiCZjfvGIM)

## Popular Workflows (Real‑Time & Post‑Meeting)

1. **Auto‑Join from Calendar (real‑time)**  
   Trigger: Google Calendar "Event started"  
   Action: `POST /bots`  
   Result: Transcription starts the moment the call begins

2. **Live Highlights to Slack (real‑time)**  
   Stream transcript → keyword filter → Slack message

3. **AI Summary to Notion (post‑meeting)**  
   `GET /transcripts/google_meet/{meeting_id}` → GPT‑4 → Notion page

4. **Compliance Archive (post‑meeting)**  
   Store JSON in S3 / BigQuery for audit & search



## Join the Community

Get support, share flows, request features:

[Discord](https://discord.com/channels/1337394383888060436/1370732215415210044)

## Next Steps

⭐ Star the [GitHub repo](https://github.com/Vexa-ai/vexa)

⬇️ Grab the [n8n workflow](https://github.com/Vexa-ai/n8n)

🎬 Watch the [demo](https://youtu.be/xYiCZjfvGIM)

Automate your Google Meet transcripts in n8n today—and turn every conversation into actionable data. 
