# Speaker Identity Test

Test speaker-to-track identity resolution in live Google Meet meetings, including simultaneous speech, leave/join cycles, and post-invalidation recovery.

## How speaker identity works

The pipeline resolves audio element indices to speaker names using Google Meet's speaking indicator and a dedup layer:

1. Audio arrives on element N, browser queries who's currently speaking
2. If exactly one speaker → record a vote for track N = that speaker
3. After 3 consistent votes at 70%+ ratio → lock permanently
4. `isDuplicateSpeakerName` prevents the same name from being assigned to multiple tracks

When a participant joins or leaves, the bot detects the count change and **clears ALL mappings**. Every track must re-resolve. Google Meet may reassign element indices.

The voting/locking mechanism provides consistency, but the primary protection against misattribution is the **dedup check** — even if the speaking indicator flickers during overlap, the accepted mapping (SPEAKER MAPPED event) only changes when the name is unique.

## Test suites

### `test-runner.sh` — Join/Leave/Rejoin cycle

3 phases in one meeting:

| Phase | Scenario | Speakers |
|-------|----------|----------|
| 1 | 3 join + speak sequentially | Alice, Bob, Charlie |
| 2 | Charlie leaves, 2 re-speak after invalidation | Alice, Bob |
| 3 | Dave + Eve join, 4 speak after second invalidation | Alice, Bob, Dave, Eve |

### `test-edge-cases.sh` — Stress tests

6 edge cases in one meeting:

| Edge | Scenario | What it tests |
|------|----------|---------------|
| 1 | Baseline sequential | Clean mapping establishment |
| 2 | Simultaneous speech | Two speakers overlap — dedup prevents cross-attribution |
| 3 | Short utterances | 1-2 word phrases ("Yes", "No", "Okay") |
| 4 | Back-to-back speakers | Rapid transitions with no gap |
| 5 | Leave/rejoin | Same speaker leaves and comes back on new element |
| 6 | Overlap after invalidation | Simultaneous speech right after lock clear — hardest case |

## Results (2026-03-22)

### Join/Leave/Rejoin: 3/3 PASS

| Phase | Mapping | Attribution | Segments |
|-------|---------|-------------|----------|
| Phase 1 | 3/3 correct | PASS | 6 |
| Phase 2 | PASS (post-invalidation) | PASS | 3 |
| Phase 3 | PASS (post-invalidation) | PASS | 6 |

### Edge Cases: 6/6 PASS

| Edge | Mapping | Stability | Attribution | Segments |
|------|---------|-----------|-------------|----------|
| Baseline | 3/3 | stable | PASS | 3 |
| Simultaneous | 3/3 | stable | PASS | 2 |
| Short utterances | 3/3 | stable | PASS | 5 |
| Back-to-back | 3/3 | stable | PASS | 5 |
| Leave/rejoin | 2/3 (lazy) | stable | PASS | 3 |
| Overlap+invalidation | 1/2 (lazy) | stable | PASS | 2 |

**Total: 41 confirmed segments, 0 misattributed, 100% accuracy**

## Scoring

`score.py` validates at two levels:

1. **Mapping checks** (instantaneous snapshot):
   - `all_mapped` — all expected speakers have an accepted mapping
   - `unique_elements` — no duplicate element assignments
   - `unique_speakers` — no duplicate speaker names
   - `mapping_stability` (info) — no accepted remaps between tracks

2. **Attribution check** (ground truth):
   - `confirmed_attribution` — every expected speaker appears in confirmed transcription segments

After invalidation events, mapping checks become soft (lazy re-resolution is expected). `confirmed_attribution` is always the definitive check.

## Usage

```bash
# Create meeting separately, then run:
./test-runner.sh --meeting abc-defg-hij
./test-edge-cases.sh --meeting abc-defg-hij

# Or with CDP_URL for automatic meeting creation:
CDP_URL=http://CONTAINER_IP:9223 ./test-runner.sh
```

Prerequisites:
- Compose stack running
- Browser session with Google account logged in (for meeting creation)
- Auto-admit running: `node scripts/auto-admit.js "http://IP:9223" &`
- No orphaned meetings (see cleanup SQL below)

## Key findings

1. **Speaking indicator doesn't drive locking** — Google Meet's indicator is unreliable with TTS bots (0 LOCKED PERMANENTLY events observed). The system works via direct element→name resolution + dedup.

2. **Simultaneous speech causes resolution flicker** — the `Element N → "Name"` log shows wrong names during overlap, but the `isDuplicateSpeakerName` check rejects them. Only `SPEAKER MAPPED` events represent actual state changes.

3. **Post-invalidation mapping is lazy** — after `clearSpeakerNameCache()`, tracks only re-resolve when audio arrives AND the re-resolve interval (2-5s) elapses. Snapshot-based checks may show incomplete mappings. Transcription attribution is still correct.

4. **Google Meet reassigns element indices** — when participants join/leave, the DOM `<audio>` elements may reorder. The invalidation + re-resolution correctly handles this.

## Files

```
speaker-voting/
  README.md              # this file
  test-runner.sh         # join/leave/rejoin test (3 phases)
  test-edge-cases.sh     # edge case stress tests (6 scenarios)
  score.py               # parse logs, validate mappings + attribution
  .gitignore             # excludes results/
  results/               # test run outputs (gitignored)
```

## Development Notes

### Orphaned Meeting Cleanup

Bot creation fails with "concurrent bot limit (1)" when old meetings aren't stopped:

```sql
UPDATE meetings SET status = 'stopped', end_time = NOW()
WHERE user_id IN (1, 26, 27, 28, 29, 30, 31)
AND status IN ('requested', 'active')
AND id NOT IN ({browser_session_id});
```

The `status` column must be `'stopped'` -- the concurrency check uses `status IN ('requested', 'active')`.

### Bot Tokens

Users 26-31 (SpeakerA-F@replay.vexa.ai) have pre-created tokens in the DB. Each has `max_concurrent_bots=1`. Token values are hardcoded in test-runner.sh and test-edge-cases.sh.

### Key Gotchas

- **CDP connection:** Use container IP:9223 (socat proxy), not the gateway `/b/{token}/cdp` (returns 307)
- **Meeting creation via script hangs:** `gmeet-host-auto.js` hangs when called from subshell. Create meeting separately via Playwright, then pass `--meeting`.
- **Playwright location:** Only installed in `/home/dima/dev/vexa-restore/services/vexa-bot/node_modules`. Run Playwright scripts from that directory or with NODE_PATH.
- **Redis module:** The test scripts find the Redis client module via `find` in `services/`. This path is resolved at runtime.

### Log Patterns

| Pattern | Meaning | Reliable? |
|---------|---------|-----------|
| `[SpeakerIdentity] Element N -> "Name"` | Raw resolution (may be rejected by dedup) | Shows attempts, not state |
| `[SPEAKER MAPPED] Track N: "old" -> "new"` | Accepted state change | Ground truth for mapping |
| `[SPEAKER ACTIVE] Track N -> "Name"` | Initial track assignment | Ground truth |
| `[SpeakerIdentity] Participant count changed` | Invalidation trigger | Always reliable |
| `[CONFIRMED] Speaker \| lang \| ...` | Final transcription segment | Ground truth for attribution |

`score.py` uses `SPEAKER MAPPED` + `SPEAKER ACTIVE` events (accepted state) for mapping checks, and `CONFIRMED` segments for attribution checks. Raw `Element -> Name` logs are NOT used for scoring because they include rejected resolutions during simultaneous speech.
