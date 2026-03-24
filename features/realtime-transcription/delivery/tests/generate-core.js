#!/usr/bin/env node
/**
 * Generate core ticks from a single audio file.
 *
 * Feeds a WAV file through SpeakerStreamManager as a single speaker (Google Meet path),
 * outputs transcript.jsonl — one tick per line with { confirmed[], pending[] }.
 *
 * Usage:
 *   node generate-core.js <audio.wav> [output-dir]
 *   DATASET=youtube-single-speaker node generate-core.js
 *
 * Env vars:
 *   DATASET              - dataset name (reads audio from data/raw/{dataset}/audio/01-speaker.wav)
 *   TRANSCRIPTION_URL    - Whisper endpoint
 *   TRANSCRIPTION_TOKEN  - Whisper auth token
 */

const fs = require('fs');
const path = require('path');

const DATASET = process.env.DATASET || 'youtube-single-speaker';
const DATA_DIR = path.resolve(__dirname, '..', '..', 'data');
const AUDIO_PATH = process.argv[2] || path.join(DATA_DIR, 'raw', DATASET, 'audio', '01-speaker.wav');
const OUTPUT_DIR = process.argv[3] || path.join(DATA_DIR, 'core', DATASET);

const TX_URL = process.env.TRANSCRIPTION_URL || 'http://localhost:8083/v1/audio/transcriptions';
const TX_TOKEN = process.env.TRANSCRIPTION_TOKEN || '';

const SAMPLE_RATE = 16000;
const CHUNK_SIZE = 4096;
const CHUNK_DURATION_MS = (CHUNK_SIZE / SAMPLE_RATE) * 1000;

// Import compiled JS from vexa-bot
const BOT_DIST = path.resolve(__dirname, '..', '..', '..', '..', 'services', 'vexa-bot', 'core', 'dist', 'services');

async function main() {
  const { SpeakerStreamManager } = require(path.join(BOT_DIST, 'speaker-streams'));
  const { TranscriptionClient } = require(path.join(BOT_DIST, 'transcription-client'));

  // Read WAV
  if (!fs.existsSync(AUDIO_PATH)) {
    console.error(`Audio not found: ${AUDIO_PATH}`);
    process.exit(1);
  }
  const samples = readWav(AUDIO_PATH);
  const durationSec = samples.length / SAMPLE_RATE;
  console.log(`Audio: ${AUDIO_PATH}`);
  console.log(`Duration: ${durationSec.toFixed(1)}s, ${samples.length} samples`);

  // Setup pipeline
  const txClient = new TranscriptionClient({
    serviceUrl: TX_URL, apiToken: TX_TOKEN, sampleRate: SAMPLE_RATE,
  });

  const mgr = new SpeakerStreamManager({
    sampleRate: SAMPLE_RATE,
    minAudioDuration: 3,
    submitInterval: 2,
    confirmThreshold: 2,
    maxBufferDuration: 30,
    idleTimeoutSec: 15,
  });

  const speakerId = 'speaker-0';
  const speakerName = 'Speaker';
  const t0 = Date.now();
  const sessionStartMs = t0;

  // Collect ticks
  const ticks = [];
  const confirmedBatches = [];

  mgr.onSegmentReady = async (_sid, _name, audioBuffer) => {
    try {
      const prompt = mgr.getLastConfirmedText(speakerId);
      const result = await txClient.transcribe(audioBuffer, undefined, prompt || undefined);
      if (result?.text) {
        const text = result.text.trim();
        const lastSeg = result.segments?.[result.segments.length - 1];
        const whisperSegs = result.segments?.map(s => ({ text: s.text, start: s.start, end: s.end }));
        mgr.handleTranscriptionResult(speakerId, text, lastSeg?.end, whisperSegs);

        const bufStart = mgr.getBufferStartMs(speakerId);
        const nowMs = Date.now();
        const startSec = (bufStart - sessionStartMs) / 1000;
        const endSec = (nowMs - sessionStartMs) / 1000;
        const segId = mgr.getSegmentId(speakerId);
        const absStart = new Date(bufStart).toISOString();
        const absEnd = new Date(nowMs).toISOString();

        // Build one pending entry per Whisper segment (preserves sentence boundaries)
        const whisperSegments = result.segments || [{ text, start: 0, end: 0 }];
        const pendingSegs = whisperSegments.map(ws => ({
          speaker: speakerName,
          text: (ws.text || '').trim(),
          start: startSec + (ws.start || 0),
          end: startSec + (ws.end || 0),
          language: result.language || 'en',
          completed: false,
          segment_id: segId,
          absolute_start_time: new Date(bufStart + (ws.start || 0) * 1000).toISOString(),
          absolute_end_time: new Date(bufStart + (ws.end || 0) * 1000).toISOString(),
        })).filter(s => s.text);

        // Drain confirmed batch
        const newConfirmed = confirmedBatches.splice(0);

        // Filter out pending segments that overlap with just-confirmed text
        const confirmedTextList = newConfirmed.map(c => c.text.trim());
        const pending = pendingSegs.filter(p => {
          const pt = p.text.trim();
          return !confirmedTextList.some(ct => pt === ct || pt.startsWith(ct) || ct.startsWith(pt));
        });

        ticks.push({
          ts: new Date().toISOString(),
          speaker: speakerName,
          confirmed: newConfirmed,
          pending,
        });

        const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
        const cText = newConfirmed.map(c => `"${c.text.substring(0, 50)}"`).join(', ');
        const pText = pending.length > 0 ? `"${pending[0].text.substring(0, 50)}"` : '(skipped)';
        console.log(`  [${elapsed}s] C=[${cText || 'none'}] P=${pText}`);
      } else {
        mgr.handleTranscriptionResult(speakerId, '');
      }
    } catch (err) {
      console.error(`  Whisper error: ${err.message}`);
      mgr.handleTranscriptionResult(speakerId, '');
    }
  };

  mgr.onSegmentConfirmed = (_sid, _name, transcript, bufferStartMs, bufferEndMs, segmentId) => {
    const startSec = (bufferStartMs - sessionStartMs) / 1000;
    const endSec = (bufferEndMs - sessionStartMs) / 1000;
    confirmedBatches.push({
      speaker: speakerName, text: transcript, start: startSec, end: endSec,
      language: 'en', completed: true,
      segment_id: `session:${segmentId}`,
      absolute_start_time: new Date(bufferStartMs).toISOString(),
      absolute_end_time: new Date(bufferEndMs).toISOString(),
    });
    const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
    console.log(`  [${elapsed}s] CONFIRMED: "${transcript.substring(0, 60)}"`);
  };

  // Feed audio in real-time chunks
  console.log(`\nFeeding ${durationSec.toFixed(0)}s of audio...\n`);
  mgr.addSpeaker(speakerId, speakerName);

  for (let i = 0; i < samples.length; i += CHUNK_SIZE) {
    const chunk = samples.subarray(i, i + CHUNK_SIZE);
    mgr.feedAudio(speakerId, chunk);
    await new Promise(r => setTimeout(r, CHUNK_DURATION_MS));

    // Progress every 10s
    const elapsed = (i / SAMPLE_RATE);
    if (i > 0 && i % (SAMPLE_RATE * 10) < CHUNK_SIZE) {
      process.stdout.write(`  --- ${Math.round(elapsed)}s / ${Math.round(durationSec)}s ---\n`);
    }
  }

  console.log('\nAudio complete. Waiting for final processing...');
  await new Promise(r => setTimeout(r, 20000));

  // Flush any remaining confirmed
  const remaining = confirmedBatches.splice(0);
  if (remaining.length > 0) {
    ticks.push({
      ts: new Date().toISOString(),
      speaker: speakerName,
      confirmed: remaining,
      pending: [],
    });
    console.log(`Flushed ${remaining.length} remaining confirmed`);
  }

  mgr.removeAll();

  // Save
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const outPath = path.join(OUTPUT_DIR, 'transcript.jsonl');
  fs.writeFileSync(outPath, ticks.map(t => JSON.stringify(t)).join('\n') + '\n');
  console.log(`\nSaved ${ticks.length} ticks to ${outPath}`);

  const confirmedCount = ticks.reduce((n, t) => n + t.confirmed.length, 0);
  console.log(`Confirmed segments: ${confirmedCount}`);

  process.exit(0);
}

// --- WAV reader ---

function readWav(wavPath) {
  const buf = fs.readFileSync(wavPath);
  if (buf.toString('ascii', 0, 4) !== 'RIFF') throw new Error(`Not a WAV: ${wavPath}`);
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

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
