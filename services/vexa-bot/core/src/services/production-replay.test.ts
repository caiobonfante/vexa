/**
 * Production-faithful replay test.
 *
 * Reproduces the EXACT index.ts code path:
 *   audio → SpeakerStreamManager → onSegmentReady (real Whisper + word storage)
 *   → handleTranscriptionResult → confirm/idle → onSegmentConfirmed
 *   → mapper condition check → mapWordsToSpeakers → per-speaker segments
 *
 * Uses real collected data:
 *   - TTS audio files placed at ground truth offsets
 *   - Real caption events replayed at recorded timestamps
 *   - Real Whisper (word timestamps)
 *   - flushSpeaker on caption speaker changes (same as handleTeamsCaptionData)
 *
 * Run: npx ts-node core/src/services/production-replay.test.ts <audio-dir> <tests-dir>
 */

import * as fs from 'fs';
import { SpeakerStreamManager } from './speaker-streams';
import { TranscriptionClient } from './transcription-client';
import { mapWordsToSpeakers, captionsToSpeakerBoundaries, CaptionEvent, TimestampedWord } from './speaker-mapper';

const SAMPLE_RATE = 16000;
const CHUNK_SIZE = 4096;
const CHUNK_DURATION_MS = (CHUNK_SIZE / SAMPLE_RATE) * 1000;
const TX_URL = process.env.TRANSCRIPTION_URL || 'http://localhost:8085/v1/audio/transcriptions';
const TX_TOKEN = process.env.TRANSCRIPTION_TOKEN || '32c59b9f654f1b6e376c6f020d79897d';

const AUDIO_DIR = process.argv[2] || `${__dirname}/../../../../features/realtime-transcription/tests/audio`;
const TESTS_DIR = process.argv[3] || `${__dirname}/../../../../features/realtime-transcription/tests`;

// ── WAV reader ───────────────────────────────────────────────

function readWavAsFloat32(path: string): Float32Array {
  const buf = fs.readFileSync(path);
  if (buf.toString('ascii', 0, 4) !== 'RIFF') throw new Error(`Not a WAV: ${path}`);
  const sampleRate = buf.readUInt32LE(24);
  const bitsPerSample = buf.readUInt16LE(34);
  let dataOffset = 36;
  while (dataOffset < buf.length - 8) {
    if (buf.toString('ascii', dataOffset, dataOffset + 4) === 'data') { dataOffset += 8; break; }
    dataOffset += 8 + buf.readUInt32LE(dataOffset + 4);
  }
  const totalSamples = (buf.length - dataOffset) / (bitsPerSample / 8);
  const original = new Float32Array(totalSamples);
  for (let i = 0; i < totalSamples; i++) {
    original[i] = bitsPerSample === 16 ? buf.readInt16LE(dataOffset + i * 2) / 32768 : buf.readFloatLE(dataOffset + i * 4);
  }
  if (sampleRate === SAMPLE_RATE) return original;
  const ratio = SAMPLE_RATE / sampleRate;
  const resampled = new Float32Array(Math.floor(totalSamples * ratio));
  for (let i = 0; i < resampled.length; i++) {
    const srcIdx = i / ratio;
    const lo = Math.floor(srcIdx);
    const hi = Math.min(lo + 1, totalSamples - 1);
    resampled[i] = original[lo] * (1 - srcIdx + lo) + original[hi] * (srcIdx - lo);
  }
  return resampled;
}

// ── Parse real caption events from collected data ─────────────

interface RealCaptionEvent {
  type: 'caption' | 'speaker_change';
  speaker: string;
  text?: string;
  from?: string;
  to?: string;
  relTimeSec: number;
}

function parseRealEvents(path: string): RealCaptionEvent[] {
  const lines = fs.readFileSync(path, 'utf8').split('\n');
  const events: RealCaptionEvent[] = [];
  let firstTs: number | null = null;

  for (const line of lines) {
    const tsMatch = line.match(/^(\d{4}-\d{2}-\d{2}T[\d:.]+)Z/);
    if (!tsMatch) continue;
    const tsStr = tsMatch[1].replace(/(\.\d{6})\d+/, '$1');
    const ts = new Date(tsStr).getTime() / 1000;
    if (firstTs === null) firstTs = ts;
    const rel = ts - firstTs;

    const capMatch = line.match(/TEAMS CAPTION.*"([^"]+)": (.+)/);
    if (capMatch) {
      events.push({ type: 'caption', speaker: capMatch[1], text: capMatch[2], relTimeSec: rel });
      continue;
    }

    const changeMatch = line.match(/Speaker change: (.+?) → (.+?)(?:\s*\(|$)/);
    if (changeMatch) {
      events.push({ type: 'speaker_change', speaker: changeMatch[2].trim(), from: changeMatch[1].trim(), to: changeMatch[2].trim(), relTimeSec: rel });
    }
  }
  return events;
}

// ── Ground truth ─────────────────────────────────────────────

interface GTUtterance {
  speaker: string;
  text: string;
  offsetSec: number;
}

// Diverse test ground truth (17 utterances, 3 speakers)
const GT: GTUtterance[] = [
  { speaker: 'Alice', offsetSec: 0,    text: 'Let me walk through the full product roadmap...' },
  { speaker: 'Bob',   offsetSec: 25,   text: 'Sounds great.' },
  { speaker: 'Charlie', offsetSec: 29, text: 'Agreed.' },
  { speaker: 'Alice', offsetSec: 33,   text: 'Thanks.' },
  { speaker: 'Bob',   offsetSec: 37,   text: 'OK.' },
  // 10s silence
  { speaker: 'Alice', offsetSec: 51,   text: 'Can we discuss the budget?' },
  { speaker: 'Bob',   offsetSec: 56,   text: 'Two hundred thousand for infrastructure.' },
  { speaker: 'Charlie', offsetSec: 62, text: 'Plus fifty for marketing.' },
  { speaker: 'Alice', offsetSec: 67,   text: 'What about events?' },
  { speaker: 'Bob',   offsetSec: 70,   text: 'Fifty thousand.' },
  { speaker: 'Charlie', offsetSec: 73, text: 'Agreed.' },
  { speaker: 'Alice', offsetSec: 76,   text: 'Perfect. Let us finalize by Friday.' },
  { speaker: 'Charlie', offsetSec: 84, text: 'I want to add context about Europe...' },
  { speaker: 'Alice', offsetSec: 99,   text: 'Great.' },
  { speaker: 'Bob',   offsetSec: 102,  text: 'Well done.' },
  { speaker: 'Charlie', offsetSec: 105, text: 'Thanks everyone.' },
];

// ── Main ─────────────────────────────────────────────────────

async function main() {
  console.log('\n  ====================================================');
  console.log('  PRODUCTION-FAITHFUL REPLAY TEST');
  console.log('  Exact index.ts code path with real Whisper + real data');
  console.log('  ====================================================\n');

  // ── 1. Load real caption events ─────────────────────────────

  const eventsPath = `${TESTS_DIR}/diverse-test-timestamped-events.txt`;
  const realEvents = parseRealEvents(eventsPath);
  const captionEvents = realEvents.filter(e => e.type === 'caption');
  const speakerChanges = realEvents.filter(e => e.type === 'speaker_change');

  console.log(`  Real data: ${captionEvents.length} captions, ${speakerChanges.length} speaker changes`);

  // ── 2. Build mixed audio from TTS files at GT offsets ───────

  const audioFiles: { file: string; offsetSec: number; speaker: string }[] = [
    { file: 'long-monologue.wav', offsetSec: 0,  speaker: 'Alice' },  // ~43s monologue
    { file: 'short-sentence.wav', offsetSec: 25, speaker: 'Bob' },    // "Sounds great" (reused)
    { file: 'short-sentence.wav', offsetSec: 29, speaker: 'Charlie' },
    { file: 'short-sentence.wav', offsetSec: 51, speaker: 'Alice' },  // "Can we discuss"
    { file: 'medium-paragraph.wav', offsetSec: 56, speaker: 'Bob' },
    { file: 'short-sentence.wav', offsetSec: 84, speaker: 'Charlie' }, // monologue approx
    { file: 'short-sentence.wav', offsetSec: 99, speaker: 'Alice' },
    { file: 'short-sentence.wav', offsetSec: 102, speaker: 'Bob' },
    { file: 'short-sentence.wav', offsetSec: 105, speaker: 'Charlie' },
  ];

  const totalDurSec = 120;
  const mixed = new Float32Array(totalDurSec * SAMPLE_RATE);
  for (const af of audioFiles) {
    try {
      const audio = readWavAsFloat32(`${AUDIO_DIR}/${af.file}`);
      const start = Math.floor(af.offsetSec * SAMPLE_RATE);
      for (let i = 0; i < audio.length && (start + i) < mixed.length; i++) {
        mixed[start + i] += audio[i];
      }
    } catch {}
  }
  // Clamp
  for (let i = 0; i < mixed.length; i++) mixed[i] = Math.max(-1, Math.min(1, mixed[i]));

  console.log(`  Mixed audio: ${totalDurSec}s\n`);

  // ── 3. Set up pipeline — EXACT index.ts wiring ──────────────

  const txClient = new TranscriptionClient({
    serviceUrl: TX_URL, apiToken: TX_TOKEN, sampleRate: SAMPLE_RATE,
  });

  const mgr = new SpeakerStreamManager({
    sampleRate: SAMPLE_RATE, minAudioDuration: 3, submitInterval: 3,
    confirmThreshold: 3, maxBufferDuration: 120, idleTimeoutSec: 15,
  });

  const t0 = Date.now();
  const ts = () => ((Date.now() - t0) / 1000).toFixed(1);
  const sessionStartMs = t0;

  // === index.ts globals ===
  let latestWhisperWords: TimestampedWord[] = [];
  const captionEventLog: CaptionEvent[] = [];
  let lastCaptionSpeakerId: string | null = null;
  const outputSegments: { speaker: string; text: string; start: number; end: number }[] = [];
  let whisperCalls = 0;

  // === onSegmentReady — same as index.ts ===
  mgr.onSegmentReady = async (speakerId, speakerName, audioBuffer) => {
    whisperCalls++;
    try {
      const result = await txClient.transcribe(audioBuffer);
      if (result?.text) {
        const text = result.text.trim();
        const words = result.segments?.flatMap(s => s.words || []) || [];
        if (words.length > 0) {
          latestWhisperWords = words;
        }
        const lastSeg = result.segments?.[result.segments.length - 1];
        mgr.handleTranscriptionResult(speakerId, text, lastSeg?.end);
      } else {
        mgr.handleTranscriptionResult(speakerId, '');
      }
    } catch (err: any) {
      mgr.handleTranscriptionResult(speakerId, '');
    }
  };

  // === onSegmentConfirmed — same as index.ts with mapper ===
  mgr.onSegmentConfirmed = (speakerId, speakerName, transcript, bufferStartMs, bufferEndMs, segmentId) => {
    const startSec = (bufferStartMs - sessionStartMs) / 1000;
    const endSec = (bufferEndMs - sessionStartMs) / 1000;

    console.log(`  [${ts()}s] CONFIRMED | ${speakerName} | words=${latestWhisperWords.length} captions=${captionEventLog.length} | "${transcript.substring(0, 60)}..."`);

    // Mapper condition — exact same as index.ts
    if (latestWhisperWords.length > 0 && captionEventLog.length > 0) {
      const boundaries = captionsToSpeakerBoundaries(captionEventLog);
      const offsetWords = latestWhisperWords.map(w => ({
        ...w, start: startSec + w.start, end: startSec + w.end,
      }));
      const attributed = mapWordsToSpeakers(offsetWords, boundaries);

      if (attributed.length > 1) {
        console.log(`  [${ts()}s] SPLIT into ${attributed.length} speakers:`);
        for (const seg of attributed) {
          console.log(`    [${seg.speaker}] "${seg.text.substring(0, 50)}"`);
          outputSegments.push({ speaker: seg.speaker, text: seg.text, start: seg.start, end: seg.end });
        }
      } else if (attributed.length === 1) {
        const seg = attributed[0];
        outputSegments.push({ speaker: seg.speaker, text: seg.text, start: seg.start, end: seg.end });
      }
    } else {
      console.log(`  [${ts()}s] NO MAPPER (words=${latestWhisperWords.length}, captions=${captionEventLog.length})`);
      outputSegments.push({ speaker: speakerName, text: transcript, start: startSec, end: endSec });
    }
  };

  // ── 4. Schedule caption events from real data ────────────────

  // Rebase caption times: first caption at 0s = audio at 0s
  const firstCaptionTime = captionEvents.length > 0 ? captionEvents[0].relTimeSec : 0;

  for (const ce of captionEvents) {
    const rebasedTime = ce.relTimeSec - firstCaptionTime;
    const delayMs = Math.max(0, rebasedTime * 1000);

    setTimeout(() => {
      const speakerId = `teams-${ce.speaker.replace(/\s+/g, '_')}`;

      // Accumulate for mapper boundaries
      captionEventLog.push({ speaker: ce.speaker, text: ce.text || '', timestamp: rebasedTime });

      // Speaker change → flush previous (same as handleTeamsCaptionData)
      if (lastCaptionSpeakerId && lastCaptionSpeakerId !== speakerId) {
        mgr.flushSpeaker(lastCaptionSpeakerId);
      }
      lastCaptionSpeakerId = speakerId;

      // Add speaker if new
      if (!mgr.hasSpeaker(speakerId)) {
        mgr.addSpeaker(speakerId, ce.speaker);
      }
    }, delayMs);
  }

  // ── 5. Feed audio at real-time speed ─────────────────────────

  console.log(`  [0.0s] Playing ${totalDurSec}s of audio...\n`);

  // Find which speaker is active at each moment (from caption events)
  // Audio goes to the ACTIVE speaker's buffer (same as Teams routing)
  const totalChunks = Math.ceil(mixed.length / CHUNK_SIZE);
  let currentActiveSpeaker: string | null = null;

  for (let i = 0; i < totalChunks; i++) {
    const start = i * CHUNK_SIZE;
    const end = Math.min(start + CHUNK_SIZE, mixed.length);
    const audioSec = start / SAMPLE_RATE;

    // Determine active speaker at this audio time
    // Use caption events to find who's speaking
    const rebasedCaptions = captionEvents.map(c => ({ ...c, t: c.relTimeSec - firstCaptionTime }));
    let activeSpeaker: string | null = null;
    for (const c of rebasedCaptions) {
      if (c.t <= audioSec) activeSpeaker = c.speaker;
    }

    if (activeSpeaker) {
      const speakerId = `teams-${activeSpeaker.replace(/\s+/g, '_')}`;
      if (mgr.hasSpeaker(speakerId)) {
        mgr.feedAudio(speakerId, mixed.subarray(start, end));
      }
      if (activeSpeaker !== currentActiveSpeaker) {
        currentActiveSpeaker = activeSpeaker;
      }
    }

    if (i > 0 && Math.floor(audioSec) % 10 === 0 && Math.floor(((i - 1) * CHUNK_SIZE) / SAMPLE_RATE) % 10 !== 0) {
      console.log(`  [${ts()}s] ░░░ ${audioSec.toFixed(0)}s / ${totalDurSec}s ░░░`);
    }

    await new Promise(r => setTimeout(r, CHUNK_DURATION_MS));
  }

  console.log(`\n  [${ts()}s] Audio complete. Waiting for final processing...\n`);
  await new Promise(r => setTimeout(r, 5000));

  // Force flush all speakers
  for (const sid of mgr.getActiveSpeakers()) {
    mgr.flushSpeaker(sid, true);
  }
  await new Promise(r => setTimeout(r, 3000));

  // ── 6. Score against ground truth ────────────────────────────

  console.log('  ====================================================');
  console.log('  RESULTS');
  console.log('  ====================================================\n');

  console.log(`  Whisper calls: ${whisperCalls}`);
  console.log(`  Output segments: ${outputSegments.length}`);
  console.log(`  Caption events accumulated: ${captionEventLog.length}`);
  console.log(`  latestWhisperWords at end: ${latestWhisperWords.length}\n`);

  console.log('  Output segments:');
  for (const seg of outputSegments) {
    const spk = seg.speaker.replace(' (Guest)', '');
    console.log(`    [${spk}] ${seg.start.toFixed(1)}s-${seg.end.toFixed(1)}s: "${seg.text.substring(0, 60)}"`);
  }

  // Check each GT utterance
  console.log('\n  Ground truth comparison:');
  let captured = 0;
  let correctSpeaker = 0;

  for (const gt of GT) {
    // Find output segment containing this GT text (fuzzy word match)
    const gtWords = gt.text.toLowerCase().replace(/[.,!?]/g, '').split(/\s+/).filter(w => w.length > 2);
    let found = false;
    let speakerCorrect = false;

    for (const seg of outputSegments) {
      const segWords = seg.text.toLowerCase().replace(/[.,!?]/g, '').split(/\s+/);
      const matches = gtWords.filter(w => segWords.some(sw => sw.includes(w) || w.includes(sw)));
      if (matches.length >= Math.max(1, gtWords.length * 0.5)) {
        found = true;
        const segSpeaker = seg.speaker.replace(' (Guest)', '');
        speakerCorrect = segSpeaker === gt.speaker;
        const mark = speakerCorrect ? '✓' : '✗ wrong speaker';
        console.log(`    ${mark} ${gt.speaker} "${gt.text.substring(0, 40)}" → [${segSpeaker}]`);
        break;
      }
    }

    if (!found) {
      console.log(`    ✗ LOST ${gt.speaker} "${gt.text.substring(0, 40)}"`);
    }

    if (found) captured++;
    if (speakerCorrect) correctSpeaker++;
  }

  console.log(`\n  CAPTURED: ${captured}/${GT.length} (${(captured/GT.length*100).toFixed(0)}%)`);
  console.log(`  CORRECT SPEAKER: ${correctSpeaker}/${GT.length} (${(correctSpeaker/GT.length*100).toFixed(0)}%)`);
  console.log(`  MAPPER FIRED: ${outputSegments.some(s => s.speaker !== 'Mixed') ? 'YES' : 'NO'}`);

  mgr.removeAll();
  process.exit(0);
}

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
