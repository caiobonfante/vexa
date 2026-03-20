/**
 * Pipeline test: feeds a WAV file at real-time speed through
 * SpeakerStreamManager → TranscriptionClient → Whisper.
 *
 * Audio is fed chunk-by-chunk at the actual sample rate (~256ms per chunk).
 * The SpeakerStreamManager's internal 2s timer drives submissions — same
 * as production. Play audio alongside with `make play`.
 *
 * Usage: npx ts-node core/src/services/speaker-streams.wav-test.ts [wav-file]
 */

import * as fs from 'fs';
import { SpeakerStreamManager } from './speaker-streams';
import { TranscriptionClient } from './transcription-client';

const SAMPLE_RATE = 16000;
const CHUNK_SIZE = 4096;
const CHUNK_DURATION_MS = (CHUNK_SIZE / SAMPLE_RATE) * 1000; // ~256ms
const WAV_PATH = process.argv[2] || '/tmp/test-speech.wav';
const TX_URL = process.env.TRANSCRIPTION_URL || 'http://localhost:8085/v1/audio/transcriptions';
const TX_TOKEN = process.env.TRANSCRIPTION_TOKEN || '32c59b9f654f1b6e376c6f020d79897d';

function readWavAsFloat32(path: string): Float32Array {
  const buf = fs.readFileSync(path);
  if (buf.toString('ascii', 0, 4) !== 'RIFF') throw new Error('Not a WAV file');

  const sampleRate = buf.readUInt32LE(24);
  const bitsPerSample = buf.readUInt16LE(34);
  const numChannels = buf.readUInt16LE(22);

  let dataOffset = 36;
  while (dataOffset < buf.length - 8) {
    if (buf.toString('ascii', dataOffset, dataOffset + 4) === 'data') {
      dataOffset += 8;
      break;
    }
    dataOffset += 8 + buf.readUInt32LE(dataOffset + 4);
  }

  const bytesPerSample = bitsPerSample / 8;
  const totalSamples = (buf.length - dataOffset) / (bytesPerSample * numChannels);

  const original = new Float32Array(totalSamples);
  for (let i = 0; i < totalSamples; i++) {
    const pos = dataOffset + i * bytesPerSample * numChannels;
    original[i] = bitsPerSample === 16 ? buf.readInt16LE(pos) / 32768 : buf.readFloatLE(pos);
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

async function main() {
  const audio = readWavAsFloat32(WAV_PATH);
  const totalDuration = audio.length / SAMPLE_RATE;
  const totalChunks = Math.ceil(audio.length / CHUNK_SIZE);

  console.log(`\n  File:     ${WAV_PATH}`);
  console.log(`  Duration: ${totalDuration.toFixed(1)}s (${totalChunks} chunks at ${CHUNK_DURATION_MS.toFixed(0)}ms each)`);
  console.log(`  Whisper:  ${TX_URL}\n`);

  const txClient = new TranscriptionClient({
    serviceUrl: TX_URL,
    apiToken: TX_TOKEN,
    sampleRate: SAMPLE_RATE,
  });

  const mgr = new SpeakerStreamManager({
    sampleRate: SAMPLE_RATE,
    minAudioDuration: 2,
    submitInterval: 2,
    confirmThreshold: 2,
    maxBufferDuration: 120,
    idleTimeoutSec: 15,
  });

  const t0 = Date.now();
  const ts = () => ((Date.now() - t0) / 1000).toFixed(1);
  const audioTs = (chunkIdx: number) => ((chunkIdx * CHUNK_SIZE) / SAMPLE_RATE).toFixed(1);

  let whisperCalls = 0;
  let totalWhisperMs = 0;
  const confirmed: string[] = [];
  let lastDraft = '';
  mgr.onSegmentReady = async (speakerId, speakerName, audioBuffer) => {
    whisperCalls++;
    const durSec = (audioBuffer.length / SAMPLE_RATE).toFixed(1);

    const start = Date.now();
    try {
      const result = await txClient.transcribe(audioBuffer);
      const elapsed = Date.now() - start;
      totalWhisperMs += elapsed;

      if (result?.text) {
        const text = result.text.trim();
        if (text !== lastDraft) {
          console.log(`  [${ts()}s] DRAFT  | ${elapsed}ms | "${text}"`);
          lastDraft = text;
        }
        mgr.handleTranscriptionResult(speakerId, text);
      } else {
        mgr.handleTranscriptionResult(speakerId, '');
      }
    } catch (err: any) {
      console.log(`  [${ts()}s] ERROR  | ${err.message}`);
      mgr.handleTranscriptionResult(speakerId, '');
    }

  };

  mgr.onSegmentConfirmed = (speakerId, speakerName, text) => {
    confirmed.push(text);
    console.log(`\n  ✓ [${ts()}s] CONFIRMED | "${text}"\n`);
  };

  // Feed audio at real-time speed. Timer drives submissions.
  console.log(`  [0.0s] ▶ Playing ${totalDuration.toFixed(1)}s of audio...\n`);
  mgr.addSpeaker('s1', 'Speaker');

  for (let i = 0; i < totalChunks; i++) {
    const start = i * CHUNK_SIZE;
    const end = Math.min(start + CHUNK_SIZE, audio.length);
    mgr.feedAudio('s1', audio.subarray(start, end));

    const audioSec = (i * CHUNK_SIZE) / SAMPLE_RATE;
    if (i > 0 && Math.floor(audioSec) % 5 === 0 && Math.floor(((i - 1) * CHUNK_SIZE) / SAMPLE_RATE) % 5 !== 0) {
      console.log(`  [${ts()}s] ░░░ ${audioSec.toFixed(0)}s / ${totalDuration.toFixed(0)}s audio played ░░░`);
    }

    await new Promise(r => setTimeout(r, CHUNK_DURATION_MS));
  }

  // Wait for in-flight Whisper calls
  await new Promise(r => setTimeout(r, 3000));

  console.log(`  [${ts()}s] ■ Complete. Flushing remaining buffer...\n`);
  mgr.flushSpeaker('s1');
  await new Promise(r => setTimeout(r, 2000));

  // Deduplicate and join confirmed segments into clean output.
  // Segments may overlap at boundaries — Whisper sometimes repeats the
  // last few words of the previous segment at the start of the next.
  function deduplicateSegments(segments: string[]): string {
    if (segments.length === 0) return '';
    let result = segments[0];
    for (let i = 1; i < segments.length; i++) {
      const prev = result;
      const next = segments[i];
      // Find overlap: check if the end of prev matches the start of next
      const prevWords = prev.split(/\s+/);
      const nextWords = next.split(/\s+/);
      let bestOverlap = 0;
      // Try matching last N words of prev with first N words of next
      for (let n = Math.min(8, prevWords.length, nextWords.length); n >= 2; n--) {
        const prevTail = prevWords.slice(-n).join(' ').toLowerCase();
        const nextHead = nextWords.slice(0, n).join(' ').toLowerCase();
        if (prevTail === nextHead) {
          bestOverlap = n;
          break;
        }
      }
      if (bestOverlap > 0) {
        // Skip overlapping words from next
        result = result + ' ' + nextWords.slice(bestOverlap).join(' ');
      } else {
        result = result + ' ' + next;
      }
    }
    return result.replace(/\s+/g, ' ').trim();
  }

  const fullTranscript = deduplicateSegments(confirmed);

  // Summary
  console.log(`  ┌─────────────────────────────────────────────────`);
  console.log(`  │ Audio:     ${totalDuration.toFixed(1)}s`);
  console.log(`  │ Wall time: ${ts()}s`);
  console.log(`  │ Whisper:   ${whisperCalls} calls, avg ${whisperCalls > 0 ? (totalWhisperMs / whisperCalls).toFixed(0) : 0}ms`);
  console.log(`  │ Segments:  ${confirmed.length}`);
  console.log(`  │`);
  console.log(`  │ SEGMENTS:`);
  confirmed.forEach((t, i) => console.log(`  │  ${i + 1}. "${t}"`));
  console.log(`  │`);
  console.log(`  │ COMBINED OUTPUT:`);
  // Word-wrap at 70 chars
  const words = fullTranscript.split(' ');
  let line = '  │  ';
  for (const w of words) {
    if (line.length + w.length + 1 > 75) {
      console.log(line);
      line = '  │  ' + w;
    } else {
      line += (line.length > 5 ? ' ' : '') + w;
    }
  }
  if (line.length > 5) console.log(line);
  console.log(`  └─────────────────────────────────────────────────\n`);

  mgr.removeAll();
  process.exit(0);
}

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
