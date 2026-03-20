/**
 * Real-time pipeline test: feeds a WAV file at actual playback speed
 * through SpeakerStreamManager → TranscriptionClient → Whisper.
 *
 * Audio is fed chunk-by-chunk at the real sample rate (~256ms per chunk).
 * The SpeakerStreamManager's internal timer drives submissions — no manual
 * trySubmit calls. You see transcription appear as if listening live.
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
  console.log(`  Whisper:  ${TX_URL}`);
  console.log(`  Mode:     REAL-TIME playback\n`);

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
    // Don't log submissions — too noisy. Log results only.

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

  // Start playback
  console.log(`  [0.0s] ▶ Playing ${totalDuration.toFixed(1)}s of audio in real-time...\n`);
  mgr.addSpeaker('s1', 'Speaker');

  // Feed chunks at real-time speed
  for (let i = 0; i < totalChunks; i++) {
    const start = i * CHUNK_SIZE;
    const end = Math.min(start + CHUNK_SIZE, audio.length);
    mgr.feedAudio('s1', audio.subarray(start, end));

    // Progress indicator every 5s of audio
    const audioSec = (i * CHUNK_SIZE) / SAMPLE_RATE;
    if (i > 0 && Math.floor(audioSec) % 5 === 0 && Math.floor(((i - 1) * CHUNK_SIZE) / SAMPLE_RATE) % 5 !== 0) {
      console.log(`  [${ts()}s] ░░░ ${audioSec.toFixed(0)}s / ${totalDuration.toFixed(0)}s audio played ░░░`);
    }

    // Real-time pacing
    await new Promise(r => setTimeout(r, CHUNK_DURATION_MS));
  }

  console.log(`  [${ts()}s] ■ Playback complete. Waiting for final transcription...\n`);

  // Wait for in-flight Whisper calls
  await new Promise(r => setTimeout(r, 3000));

  // Flush remaining
  mgr.flushSpeaker('s1');
  await new Promise(r => setTimeout(r, 2000));

  // Summary
  console.log(`  ┌─────────────────────────────────────────────────`);
  console.log(`  │ Audio:     ${totalDuration.toFixed(1)}s`);
  console.log(`  │ Wall time: ${ts()}s`);
  console.log(`  │ Whisper:   ${whisperCalls} calls, avg ${whisperCalls > 0 ? (totalWhisperMs / whisperCalls).toFixed(0) : 0}ms`);
  console.log(`  │ Segments:  ${confirmed.length}`);
  console.log(`  │`);
  console.log(`  │ TRANSCRIPT:`);
  confirmed.forEach((t, i) => console.log(`  │  ${i + 1}. "${t}"`));
  console.log(`  └─────────────────────────────────────────────────\n`);

  mgr.removeAll();
  process.exit(0);
}

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
