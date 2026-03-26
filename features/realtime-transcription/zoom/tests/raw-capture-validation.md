# Raw Capture Validation Report

**Date:** 2026-03-25
**Validator:** validator (team zoom-rawcap)
**Files reviewed:**
- `services/vexa-bot/core/src/services/raw-capture.ts` (new)
- `services/vexa-bot/core/src/index.ts` (modified)
- `services/vexa-bot/core/src/platforms/zoom/web/recording.ts` (modified)
- `services/vexa-bot/core/src/services/speaker-identity.ts` (NOT modified)
- `services/vexa-bot/core/src/services/production-replay.test.ts` (reference — format contract)

---

## 1. WAV Header — `readWavAsFloat32()` Compatibility

The reader (`production-replay.test.ts:123-148`) expects:

| Offset | Field | Expected | `createWavHeader()` writes | Result |
|--------|-------|----------|---------------------------|--------|
| 0 | ChunkID | `"RIFF"` | `"RIFF"` | PASS |
| 4 | ChunkSize | `36 + dataSize` | `36 + dataSize` | PASS |
| 8 | Format | `"WAVE"` | `"WAVE"` | PASS |
| 12 | Subchunk1ID | `"fmt "` | `"fmt "` | PASS |
| 16 | Subchunk1Size | 16 | 16 | PASS |
| 20 | AudioFormat | 1 (PCM) | 1 | PASS |
| 22 | NumChannels | any | 1 (mono) | PASS |
| 24 | SampleRate | `UInt32LE` — resamples if != 16000 | 16000 | PASS (no resample needed) |
| 28 | ByteRate | any | 32000 | PASS |
| 32 | BlockAlign | any | 2 | PASS |
| 34 | BitsPerSample | `UInt16LE` — supports 16 or 32 | 16 | PASS |
| 36 | Subchunk2ID | `"data"` | `"data"` | PASS |
| 40 | Subchunk2Size | `UInt32LE` | dataSize | PASS |

**Verdict: PASS** — WAV header is fully compatible with reader.

## 2. Float32-to-Int16 PCM Conversion

`float32ToInt16PCM()` (raw-capture.ts:198-206):
- Clamps input to `[-1, 1]`
- Maps: `negative * 0x8000`, `positive * 0x7FFF`
- Writes `Int16LE`

Reader does: `buf.readInt16LE(offset) / 32768` → recovers float.

Round-trip: `0.5 → 0.5*32767 = 16383 → 16383/32768 = 0.49997`. Acceptable precision loss.

**Verdict: PASS**

## 3. Events.txt Format — `parseRealEvents()` Compatibility

### 3a. Timestamp format

`new Date().toISOString()` produces: `2026-03-25T12:34:56.789Z`

Reader regex: `^(\d{4}-\d{2}-\d{2}T[\d:.]+)Z` — matches ISO with trailing `Z`.

**Verdict: PASS**

### 3b. Speaker change events

`logSpeakerEvent()` output (raw-capture.ts:90):
```
2026-03-25T12:34:56.789Z [SPEAKER] Speaker change: (none) -> Alice (Guest)
```

Reader regex: `Speaker change: (.+?) -> (.+?) \(Guest\)` (where `->` is the `U+2192` arrow)

**ISSUE:** The regex searches for `→` (Unicode RIGHT ARROW U+2192). The source code at raw-capture.ts:90 uses the same `→` character. Verified by reading the actual bytes — both use Unicode arrow. **PASS**

The `[SPEAKER]` tag between timestamp and "Speaker change:" is fine — regex is not position-anchored.

### 3c. Caption events (TEAMS CAPTION)

Reader regex: `TEAMS CAPTION.*"([^"]+)": (.+)`

`logSegmentConfirmed()` output: `[SEGMENT] "Alice": hello world` — does NOT match `TEAMS CAPTION`.

**This is acceptable for Zoom** — caption events are Teams-specific. Zoom datasets don't use caption-driven speaker changes. The replay test uses `speakerChangeTimes` (from speaker change events) as the primary mechanism. Caption events are only needed for Teams datasets.

**Verdict: PASS (for Zoom scope)**

## 4. File Naming — `loadGroundTruth()` Compatibility

### 4a. Directory structure

Reader checks (production-replay.test.ts:222):
```typescript
const audioDir = fs.existsSync(path.join(collectionDir, 'audio'))
  ? path.join(collectionDir, 'audio') : collectionDir;
```

Raw capture writes to `{outputDir}/audio/`. **PASS**

### 4b. WAV file naming

Raw capture: `{NN}-{sanitized-name}.wav` (e.g., `01-alice-smith.wav`)
Reader: sorts `.wav` files alphabetically. Zero-padded counter ensures correct order. **PASS**

### 4c. Matching .txt files

Reader (production-replay.test.ts:234): `wavFile.replace('.wav', '.txt')`
Raw capture writes `{NN}-{sanitized-name}.txt` alongside each `.wav`. **PASS**

### 4d. Speaker name extraction from filename

Reader fallback (production-replay.test.ts:242-243):
```typescript
const baseName = wavFile.replace(/^\d+-/, '').replace(/\.wav$/, '');
const baseWords = baseName.split('-');
// fallback: title-case first word
speaker = baseWords[0].charAt(0).toUpperCase() + baseWords[0].slice(1);
```

`sanitizeName("Alice Smith")` → `alice-smith` → filename `01-alice-smith.wav`
Reader: strips `01-` → `alice-smith`, splits → `["alice", "smith"]`, title-cases → `"Alice"`.

Primary path uses `speakerChangeTimes[i].speaker` from events.txt. Fallback is adequate.

**Verdict: PASS**

### 4e. WAV/event count alignment

**ISSUE (MODERATE):** `loadGroundTruth()` maps WAV files to speaker change events by index:
```typescript
if (i < speakerChangeTimes.length) {
  speaker = speakerChangeTimes[i].speaker;
}
```

Raw capture flushes a WAV file when:
1. A speaker changes on a track (`feedAudio` detects name change)
2. At `finalize()` (all remaining tracks)

Speaker change events are logged when DOM polling detects a new active speaker (`logSpeakerEvent` from recording.ts).

These are **independent triggers**. The number of WAV files may not match the number of speaker change events in `events.txt`. If there are 5 speaker changes but only 3 track flushes (e.g., continuous audio on one track), the replay test will misalign speakers.

**Impact:** Speaker name assignment in `loadGroundTruth()` will be wrong for files where `i >= speakerChangeTimes.length` (falls back to filename-derived name) or where `i < speakerChangeTimes.length` but the Nth speaker change doesn't correspond to the Nth WAV file.

**Mitigation:** This is a design mismatch between the Teams collection format (utterance-per-file, 1:1 with speaker changes) and the Zoom raw capture format (continuous-per-track, flushed on speaker change or finalize). The replay test was designed for Teams. A Zoom-specific ground truth loader or a metadata file mapping WAV→speaker would fix this.

**Recommendation:** Not a blocker for initial capture. The raw audio data is correct — only the ground truth alignment needs work for scoring. The captured data can still be replayed; scoring accuracy depends on correct speaker mapping.

## 5. TypeScript Compilation

```bash
cd services/vexa-bot/core && npx tsc -p tsconfig.json --noEmit
# EXIT: 0
```

**Verdict: PASS** — zero compilation errors.

## 6. Wiring Verification

### 6a. `feedAudio` — called from `handlePerSpeakerAudioData` (index.ts:1587-1589)

```typescript
if (rawCaptureService) {
  const resolvedName = speakerManager.getSpeakerName(speakerId) || '';
  rawCaptureService.feedAudio(speakerIndex, audioData, resolvedName);
}
```

Called BEFORE `speakerManager.feedAudio()` — captures raw audio before pipeline processing. **PASS**

### 6b. `logSpeakerEvent` — called from recording.ts:201-204

```typescript
const rawCapture = getRawCaptureService();
if (rawCapture) {
  rawCapture.logSpeakerEvent(lastActiveSpeaker, speakerName);
}
```

Called on DOM-polled speaker change in Zoom. **PASS**

### 6c. `logSegmentConfirmed` — called from index.ts:1395

```typescript
if (rawCaptureService) rawCaptureService.logSegmentConfirmed(speakerName, transcript);
```

Called inside `onSegmentConfirmed` callback. **PASS**

### 6d. `logTrackLock` — NOT wired

`speaker-identity.ts:78` logs `LOCKED PERMANENTLY` but does NOT call `rawCaptureService.logTrackLock()`.

**ISSUE (MINOR):** Track lock events won't appear in events.txt. This is informational only — the replay test doesn't parse lock events (no regex for `LOCKED PERMANENTLY` in `parseRealEvents`). Not a functional blocker.

### 6e. `finalize` — called from index.ts:1628-1631

```typescript
if (rawCaptureService) {
  const outputPath = rawCaptureService.finalize();
  log(`[PerSpeaker] Raw capture finalized -> ${outputPath}`);
  rawCaptureService = null;
}
```

Called in cleanup path. **PASS**

### 6f. Initialization — gated by `RAW_CAPTURE=true` (index.ts:1178-1181)

```typescript
if (process.env.RAW_CAPTURE === 'true') {
  rawCaptureService = new RawCaptureService(meetingId);
  log(`[PerSpeaker] Raw capture enabled -> ${rawCaptureService.outputPath}`);
}
```

**PASS**

## 7. `make play-replay DATASET=zoom-captured` Compatibility

**ISSUE (MINOR):** The Makefile `play-replay` target calls `replay-meeting.test.ts`, not `production-replay.test.ts`. There is no Makefile target for `production-replay.test.ts` with `DATASET` support.

Manual invocation works:
```bash
DATASET=zoom-captured npx ts-node core/src/services/production-replay.test.ts
```

**Recommendation:** Add a `play-production` Makefile target or update `play-replay` to use `production-replay.test.ts`.

## Summary

| Check | Result | Notes |
|-------|--------|-------|
| WAV header matches readWavAsFloat32() | PASS | 44-byte header, 16kHz mono 16-bit PCM |
| Float32->Int16 conversion correct | PASS | Proper clamping and scaling |
| events.txt timestamp format | PASS | ISO 8601 with Z suffix |
| Speaker change event regex match | PASS | Unicode arrow, (Guest) suffix |
| File naming matches loadGroundTruth() | PASS | NN-name.wav + .txt pairs, audio/ subdir |
| TypeScript compiles | PASS | `tsc --noEmit` exits 0 |
| feedAudio wired in index.ts | PASS | Before pipeline processing |
| logSpeakerEvent wired in recording.ts | PASS | On DOM speaker change |
| logSegmentConfirmed wired in index.ts | PASS | In onSegmentConfirmed callback |
| logTrackLock wired in speaker-identity.ts | NOT WIRED | Minor — replay test doesn't parse locks |
| finalize wired in cleanup | PASS | Nulls out service reference |
| RAW_CAPTURE env gate | PASS | Only activates when true |
| WAV/event count alignment | MODERATE ISSUE | See section 4e — design mismatch |
| Makefile target exists | MINOR ISSUE | No target for production-replay + DATASET |

**Overall: PASS with caveats.** The raw capture service correctly captures per-speaker audio in a format that `production-replay.test.ts` can read. The WAV files are valid, the events.txt format matches parser regexes, and TypeScript compiles clean. Two issues to address in follow-up:

1. **WAV/event count alignment** (moderate) — the 1:1 mapping between WAV files and speaker change events may not hold for Zoom's continuous-per-track capture model. Needs a Zoom-specific ground truth strategy.
2. **logTrackLock not wired** (minor) — informational only, doesn't affect replay functionality.
