---
title: 'Claude Desktop MCP Setup with Vexa (Google Meet Transcripts)'
date: '2025-08-28'
author: 'Dmitry Grankin'
authorImage: '/dmitry-grankin.jpg'
authorLinkedIn: 'https://www.linkedin.com/in/dmitry-grankin/'
heroImage: '/assets/claude-desktop-vexa-mcp.png?v=3'
slug: 'claude-desktop-vexa-mcp-google-meet-transcripts'
summary: "Step‑by‑step tutorial: add Vexa MCP to Claude Desktop for real‑time Google Meet transcripts. Launch a bot, ask mid‑call, generate AI notes."
---

Looking for the easiest way to get **real‑time Google Meet transcripts inside Claude Desktop**?  
With the open‑source **[Vexa MCP](https://github.com/Vexa-ai/vexa)** server, you can drop a bot into any Meet, capture transcripts live, and ask Claude questions *during* or *after* the call.

---


- **Join & transcribe in minutes** – no Chrome extensions or hacks
- **Ask Claude during calls** – “Summarize last 5 mins,” “What objections did we hear?”
- **After‑call automation** – summaries, CRM updates, Notion/Slack/HubSpot


---

## Prerequisites
1. Get a **Vexa API key** → [Dashboard](https://vexa.ai/dashboard/api-keys)  
   *(one‑click pre‑configured config file available)*
2. Install **Claude Desktop** (macOS/Windows/Linux)

---

## Setup in Claude Desktop
Open **Settings → Developer → Edit Config** and paste:

```json
{
  "mcpServers": {
    "Vexa": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://api.cloud.vexa.ai/mcp",
        "--allow-http",
        "--header",
        "Authorization:${VEXA_API_KEY}"
      ],
      "env": {
        "VEXA_API_KEY": "YOUR_VEXA_API_KEY_HERE"
      }
    }
  }
}
```

Save → Restart Claude.

### Config file locations
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `C:\\Users\\<YOU>\\AppData\\Roaming\\Claude\\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

---

## First‑Run Demo (5 Minutes)

### Step 1: Get a Meeting URL
**Option A:** Copy an existing Google Meet URL, for example:  
`https://meet.google.com/oyz-gsah-ijt`

**Option B:** Start a new meeting at [meet.new](https://meet.new) and copy the URL

### Step 2: Drop Bot into Meeting
In Claude, you can ask something like:
- **"Drop a bot to https://meet.google.com/oyz-gsah-ijt using Vexa"**


The exact wording doesn't matter - Claude will understand what you want!

### Step 3: Wait for Bot to Join
Wait about **10 seconds** for the bot to join the meeting.

### Step 4: Admit the Bot
When you see the bot trying to join, **admit it** in your Google Meet interface.

### Step 5: Start Using Transcripts
Once admitted, you can ask Claude questions like:
- **"Request transcripts and summarize John's biography"**
- **"Summarize the last 5 minutes"**
- **"List blockers and owners so far"**
- **"What did the customer object to?"**

### Mid‑call prompts
- “Summarize the last 5 minutes.”
- “List blockers and owners so far.”
- “What did the customer object to?”

### After‑call prompts
- “Create a customer‑ready summary.”
- “Draft a follow‑up email.”
- “Push notes to Slack/Notion/HubSpot.”

---

## Popular Use Cases
1. **Sales meetings** – objection handling, CRM notes, follow‑up emails
2. **Team dailies** – auto‑summaries, sprint recaps
3. **HR interviews** – skills highlights, structured ATS notes

---





## Join the Community
- [Discord](https://discord.com/channels/1337394383888060436/1370732215415210044)
- ⭐ Star the [GitHub repo](https://github.com/Vexa-ai/vexa)

---

## Next Steps
1. [Get your API key](https://vexa.ai/dashboard/api-keys)  
2. Paste JSON into Claude Desktop config  
3. Open a Meet and say:  
   **“Use the Vexa MCP to join this meeting and take live notes.”**

