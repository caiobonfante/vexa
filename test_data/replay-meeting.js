#!/usr/bin/env node
/**
 * Replay a saved meeting transcript using TTS bots.
 *
 * Parses closed caption format, assigns Piper voices to speakers,
 * sends bots to a meeting, plays back lines with correct timing.
 *
 * Usage:
 *   node replay-meeting.js <meeting_url> <transcript_file> [--api-url URL] [--api-key KEY]
 *
 * Example:
 *   node replay-meeting.js "https://teams.live.com/meet/123?p=abc" test_data/meeting_saved_closed_caption.txt
 */

const fs = require('fs');
const http = require('http');
const https = require('https');

// --- Config ---
const API_URL = process.env.API_URL || process.argv.find(a => a.startsWith('--api-url='))?.split('=')[1] || 'http://localhost:8066';
const API_KEY = process.env.API_KEY || process.argv.find(a => a.startsWith('--api-key='))?.split('=')[1] || '';
const MEETING_URL = process.argv[2];
const TRANSCRIPT_FILE = process.argv[3];

if (!MEETING_URL || !TRANSCRIPT_FILE) {
  console.error('Usage: node replay-meeting.js <meeting_url> <transcript_file>');
  console.error('  Set API_KEY env var or --api-key=...');
  process.exit(1);
}

// Piper voices — assign one per speaker for variety
const VOICES = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'];

// --- Parse transcript ---
function parseTranscript(file) {
  const text = fs.readFileSync(file, 'utf-8');
  const lines = text.split('\n');
  const entries = [];
  let currentSpeaker = null;
  let currentTime = null;
  let currentText = '';

  for (const line of lines) {
    const headerMatch = line.match(/^\[(.+?)\]\s+(\d{2}:\d{2}:\d{2})/);
    if (headerMatch) {
      // Save previous entry
      if (currentSpeaker && currentText.trim()) {
        entries.push({ speaker: currentSpeaker, time: currentTime, text: currentText.trim() });
      }
      currentSpeaker = headerMatch[1];
      currentTime = headerMatch[2];
      currentText = '';
    } else if (line.trim() && currentSpeaker) {
      currentText += (currentText ? ' ' : '') + line.trim();
    }
  }
  // Save last entry
  if (currentSpeaker && currentText.trim()) {
    entries.push({ speaker: currentSpeaker, time: currentTime, text: currentText.trim() });
  }

  return entries;
}

function timeToMs(timeStr) {
  const [h, m, s] = timeStr.split(':').map(Number);
  return ((h * 60 + m) * 60 + s) * 1000;
}

// --- API helpers ---
function apiRequest(method, path, body) {
  return new Promise((resolve, reject) => {
    const url = new URL(`${API_URL}${path}`);
    const opts = {
      hostname: url.hostname,
      port: url.port,
      path: url.pathname + url.search,
      method,
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
      },
    };

    const data = body ? JSON.stringify(body) : null;
    if (data) opts.headers['Content-Length'] = Buffer.byteLength(data);

    const req = (url.protocol === 'https:' ? https : http).request(opts, (res) => {
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => {
        try { resolve({ status: res.statusCode, data: JSON.parse(body) }); }
        catch { resolve({ status: res.statusCode, data: body }); }
      });
    });

    req.on('error', reject);
    if (data) req.write(data);
    req.end();
  });
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// --- Main ---
async function main() {
  console.log('Parsing transcript...');
  const entries = parseTranscript(TRANSCRIPT_FILE);

  // Get unique speakers and assign voices
  const speakers = [...new Set(entries.map(e => e.speaker))];
  const voiceMap = {};
  speakers.forEach((s, i) => { voiceMap[s] = VOICES[i % VOICES.length]; });

  console.log(`\nSpeakers (${speakers.length}):`);
  speakers.forEach(s => {
    const count = entries.filter(e => e.speaker === s).length;
    console.log(`  ${s} → voice: ${voiceMap[s]} (${count} lines)`);
  });

  console.log(`\nTotal lines: ${entries.length}`);
  console.log(`Duration: ${entries[0].time} → ${entries[entries.length - 1].time}`);

  // Parse meeting URL
  const meetingUrl = new URL(MEETING_URL);
  let platform, nativeId, passcode;

  if (meetingUrl.hostname.includes('teams')) {
    platform = 'teams';
    nativeId = meetingUrl.pathname.split('/').pop();
    passcode = meetingUrl.searchParams.get('p') || '';
  } else if (meetingUrl.hostname.includes('meet.google')) {
    platform = 'google_meet';
    nativeId = meetingUrl.pathname.split('/').pop();
  } else {
    platform = 'zoom';
    nativeId = meetingUrl.pathname.split('/').pop();
  }

  console.log(`\nPlatform: ${platform}, ID: ${nativeId}`);

  // Create the listener bot (transcribes the meeting)
  console.log('\nCreating listener bot...');
  const listenerReq = {
    platform,
    native_meeting_id: nativeId,
    bot_name: 'Vexa Listener',
    meeting_url: MEETING_URL,
  };
  if (passcode) listenerReq.passcode = passcode;

  const listener = await apiRequest('POST', '/bots', listenerReq);
  if (listener.status !== 201 && listener.status !== 200) {
    console.error('Failed to create listener bot:', listener.data);
    process.exit(1);
  }
  console.log(`Listener bot created: meeting ${listener.data.id}`);

  // Wait for bot to join
  console.log('Waiting 30s for bot to join...');
  await sleep(30000);

  // Play back the transcript
  const startTimeMs = timeToMs(entries[0].time);
  console.log(`\n--- Starting playback ---\n`);

  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i];
    const voice = voiceMap[entry.speaker];

    // Calculate delay from previous entry
    if (i > 0) {
      const prevMs = timeToMs(entries[i - 1].time);
      const currMs = timeToMs(entry.time);
      const delayMs = Math.max(0, currMs - prevMs);
      if (delayMs > 0 && delayMs < 30000) {
        await sleep(delayMs);
      }
    }

    const elapsed = ((timeToMs(entry.time) - startTimeMs) / 1000).toFixed(0);
    console.log(`[${entry.time}] (+${elapsed}s) ${entry.speaker}: "${entry.text.substring(0, 60)}${entry.text.length > 60 ? '...' : ''}"`);

    // Send speak command
    const speakResult = await apiRequest('POST', `/bots/${platform}/${nativeId}/speak`, {
      text: entry.text,
      voice,
    });

    if (speakResult.status !== 200 && speakResult.status !== 202) {
      console.error(`  SPEAK FAILED:`, speakResult.data);
    }

    // Wait for approximate TTS playback duration (100ms per char, min 2s)
    const playbackMs = Math.max(2000, entry.text.length * 80);
    await sleep(playbackMs);
  }

  console.log('\n--- Playback complete ---');
  console.log(`\nListener bot meeting ID: ${listener.data.id}`);
  console.log('Check transcription at the dashboard or via API.');

  // Optionally fetch and compare transcription
  console.log('\nWaiting 10s for transcription to settle...');
  await sleep(10000);

  const transcript = await apiRequest('GET', `/meeting-transcript/${platform}/${nativeId}`);
  if (transcript.status === 200 && transcript.data.transcript) {
    console.log('\n--- Transcription result ---');
    const segments = transcript.data.transcript;
    console.log(`Got ${segments.length} segments`);
    segments.forEach(s => {
      console.log(`  [${s.speaker || 'unknown'}] ${(s.text || '').substring(0, 80)}`);
    });
  }
}

main().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
