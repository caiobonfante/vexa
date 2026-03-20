# Teams Live Caption Behavior — Observed Patterns

Reference data collected 2026-03-20 from real Teams meetings with TTS speaker bots.
Source: `tests/reference-caption-data.json` (273 events, 3 speakers).

## Caption Event Model

Every caption event is an atomic `(author, text, timestamp)` triple from the DOM:
```
[data-tid="author"]:              "Alice (Guest)"
[data-tid="closed-caption-text"]: "Hello everyone I want to start"
```

These always appear together. There is no "author-only" or "text-only" event.

## Text Growth Pattern

Text grows **word-by-word** within a caption entry. Each update adds 1-3 words:

```
"Good morning"
"Good morning everyone"
"Good morning everyone I want"
"Good morning everyone I want to start"
```

**Update cadence:** ~400ms between updates (~25 updates per 10s utterance).

### Sentence Splitting

Teams reformats in-place when it detects a sentence boundary. The text **shrinks** — Teams adds punctuation to the previous sentence and starts a new caption entry:

```
"Good morning everyone I want to start"     ← growing
"Good morning, everyone."                    ← REFORMATTED (shorter! punctuation added)
"I want to start by review"                  ← NEW ENTRY (text reset to new sentence)
"I want to start by reviewing"               ← continues growing
```

The text length sequence shows this clearly: `37 → 23 → 25 → 28 → 32 → 40...`

This means: **text getting shorter = Teams split the sentence**. The author stays the same. This is NOT a speaker change.

### Partial Words

Teams sometimes shows partial words that get completed on the next update:

```
"I want to start by review"     ← partial "review"
"I want to start by reviewing"  ← completed
```

```
"We had over 50,000 active us"  ← partial "us"
"We had over 50,000 active users" ← completed
```

## Speaker Change Behavior

### Author Switch is Atomic

When a new speaker starts, the caption author changes between consecutive events. No overlap:

```
event 24: [Alice (Guest)] "We had over 50,000 active users, which is a new record for us."
event 25: [Bob (Guest)]   "Those"
```

There is **never** a period where two authors appear simultaneously. Teams shows one active speaker at a time.

### No Non-Active Speaker Refinements

Once a speaker's turn ends (new author appears), their old caption entries do NOT get further text updates. The DOM mutations only fire for the current caption entry.

Verified: in 273 events across 9 speaker changes, zero events from a non-active speaker after they were superseded.

## Overlapping Speech

When two speakers talk simultaneously:

1. The first speaker's caption continues growing
2. When Teams ASR recognizes the second speaker, it **cuts off** the first speaker's text mid-word
3. The author switches to the new speaker
4. The first speaker's unfinished text is lost from captions

Example:
```
[Alice] "We are planning to release version 3.0 in April with a completely redesigned das..."
[Bob]   "I have a question about the API changes"     ← Alice cut off, Bob takes over
```

Alice's remaining words ("dashboard") never appear in captions. **Overlapping speech causes the first speaker to be truncated.**

### Overlap Detection

The last caption from the truncated speaker will have text that ends mid-word (partial). This is how you detect that an overlap occurred:
- Normal end: text ends with `.` or `?` or `!` (punctuation)
- Truncated by overlap: text ends mid-word or with `...`

## Caption Delay

Captions arrive **after** the speech they transcribe. The delay varies:

- Typical: 1-2s from speech to first caption appearance
- First word of a new speaker: slightly longer (~2s) because Teams needs to identify the new voice
- Within a turn: shorter delays as Teams has context (~400ms between word-by-word updates)

The delay is NOT fixed — it varies per utterance and per word. Our test simulation should use a distribution (e.g., Normal(mean=1.5, std=0.5), clamped [0.5, 3.0]).

## Numbers and Formatting

Teams ASR converts spoken numbers to digits:
- "fifty thousand" → "50,000"
- "twenty percent" → "20%"
- "three point zero" → "3.0" (sometimes "3 point" → "3.0" across two updates)
- "fifteen" → "15"

## Meeting-Specific Observations

### Guest vs Host

- Guest bots appear as "Alice (Guest)", "Bob (Guest)" in captions
- Host appears as full name (e.g., "Speaker D")
- Caption DOM structure differs between host and guest views, but `[data-tid="author"]` and `[data-tid="closed-caption-text"]` are stable across both

### Caption Enablement

- Captions must be enabled per-participant — the bot enables its own captions after joining
- Guest path: More → Captions (direct toggle)
- Host path: More → Language and speech → Show live captions

### MutationObserver Behavior

- `childList:true, subtree:true, characterData:true` on the wrapper catches all updates
- Teams may use virtual DOM updates that don't trigger mutations — 200ms polling as backup
- MutationObserver fires frequently during active speech (~every 300-500ms)

## Key Constants for Test Simulation

| Parameter | Observed Value | Notes |
|-----------|---------------|-------|
| Update cadence | ~400ms | Time between consecutive text updates |
| Updates per 10s turn | ~25 | Word-by-word growth |
| Caption delay (first word) | 1.5-2.5s | From speech start to first caption |
| Caption delay (within turn) | 0.3-0.5s | From word spoken to word appearing |
| Sentence split frequency | Every 5-8s | Teams adds punctuation, starts new entry |
| Text shrink on split | 30-60% | New entry much shorter than previous |
| Overlap truncation | Immediate | First speaker cut mid-word |
| Speaker change events | 1 per transition | Atomic, no overlap |
| Non-active refinements | 0 | Never observed |
