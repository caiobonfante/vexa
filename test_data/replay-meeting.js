#!/usr/bin/env node
/**
 * Replay a saved meeting transcript with one bot per speaker + one listener.
 *
 * Each speaker gets its own user/API key so multiple bots can join the same meeting.
 * The listener bot transcribes. At the end, compares transcription to source.
 *
 * Usage:
 *   API_KEY=vxa_user_xxx node replay-meeting.js <meeting_url> <transcript_file> [--limit=N]
 *
 * Speaker API keys are auto-loaded from the DB via admin API.
 */

const fs = require('fs');
const http = require('http');
const https = require('https');

const API_URL = process.env.API_URL || 'http://localhost:8066';
const ADMIN_URL = process.env.ADMIN_URL || 'http://localhost:8067';
const ADMIN_TOKEN = process.env.ADMIN_TOKEN || 'changeme';
const LISTENER_API_KEY = process.env.API_KEY || '';
const MEETING_URL = process.argv[2];
const TRANSCRIPT_FILE = process.argv[3];
const LIMIT = parseInt(process.argv.find(a => a.startsWith('--limit='))?.split('=')[1] || '0') || 0;

if (!MEETING_URL || !TRANSCRIPT_FILE || !LISTENER_API_KEY) {
  console.error('Usage: API_KEY=xxx node replay-meeting.js <meeting_url> <transcript_file> [--limit=N]');
  process.exit(1);
}

const VOICES = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'];

function parseTranscript(file) {
  const text = fs.readFileSync(file, 'utf-8');
  const lines = text.split('\n');
  const entries = [];
  let speaker = null, time = null, txt = '';
  for (const line of lines) {
    const m = line.match(/^\[(.+?)\]\s+(\d{2}:\d{2}:\d{2})/);
    if (m) {
      if (speaker && txt.trim()) entries.push({ speaker, time, text: txt.trim() });
      speaker = m[1]; time = m[2]; txt = '';
    } else if (line.trim() && speaker) {
      txt += (txt ? ' ' : '') + line.trim();
    }
  }
  if (speaker && txt.trim()) entries.push({ speaker, time, text: txt.trim() });
  return entries;
}

function timeToMs(t) { const [h,m,s] = t.split(':').map(Number); return ((h*60+m)*60+s)*1000; }
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function req(method, baseUrl, path, body, apiKey) {
  return new Promise((resolve, reject) => {
    const url = new URL(`${baseUrl}${path}`);
    const headers = { 'Content-Type': 'application/json' };
    if (apiKey) headers['X-API-Key'] = apiKey;
    if (baseUrl === ADMIN_URL) headers['X-Admin-API-Key'] = ADMIN_TOKEN;
    const data = body ? JSON.stringify(body) : null;
    if (data) headers['Content-Length'] = Buffer.byteLength(data);
    const opts = { hostname: url.hostname, port: url.port, path: url.pathname + url.search, method, headers };
    const r = (url.protocol === 'https:' ? https : http).request(opts, (res) => {
      let b = ''; res.on('data', c => b += c);
      res.on('end', () => { try { resolve({s: res.statusCode, d: JSON.parse(b)}); } catch { resolve({s: res.statusCode, d: b}); } });
    });
    r.on('error', reject);
    if (data) r.write(data);
    r.end();
  });
}

function api(method, path, body, apiKey) { return req(method, API_URL, path, body, apiKey || LISTENER_API_KEY); }
function admin(method, path, body) { return req(method, ADMIN_URL, path, body); }

function parseMeetingUrl(url) {
  const u = new URL(url);
  if (u.hostname.includes('teams')) return { platform: 'teams', nativeId: u.pathname.split('/').pop(), passcode: u.searchParams.get('p') || '' };
  if (u.hostname.includes('meet.google')) return { platform: 'google_meet', nativeId: u.pathname.split('/').pop(), passcode: '' };
  return { platform: 'zoom', nativeId: u.pathname.split('/').pop(), passcode: '' };
}

async function getOrCreateSpeakerKey(speakerName) {
  const safeName = speakerName.replace(/[^a-zA-Z0-9]/g, '').substring(0, 20);
  const email = `${safeName}@replay.vexa.ai`;

  // Check if user exists
  const users = await admin('GET', `/admin/users/email/${email}`);
  let userId;
  if (users.s === 200 && users.d.id) {
    userId = users.d.id;
  } else {
    // Create user
    const create = await admin('POST', '/admin/users', { email, name: speakerName });
    if (create.s >= 400) { console.error(`Failed to create user for ${speakerName}:`, create.d); return null; }
    userId = create.d.id;
  }

  // Get existing token
  const tokens = await admin('GET', `/admin/users/${userId}/tokens`);
  if (tokens.s === 200 && Array.isArray(tokens.d) && tokens.d.length > 0) {
    return tokens.d[0].token;
  }

  // Create token
  const token = await admin('POST', `/admin/users/${userId}/tokens`);
  if (token.s >= 400) { console.error(`Failed to create token for ${speakerName}:`, token.d); return null; }
  return token.d.token;
}

async function waitForBotActive(apiKey, meetingId, label) {
  for (let i = 0; i < 60; i++) {
    await sleep(5000);
    const r = await api('GET', '/meetings', null, apiKey);
    if (r.s === 200) {
      const m = (r.d.meetings || []).find(x => x.id === meetingId);
      if (m) {
        if (i % 3 === 0) console.log(`  ${label}: ${m.status} (${i*5}s)`);
        if (m.status === 'active') return true;
        if (m.status === 'failed') return false;
      }
    }
  }
  return false;
}

async function main() {
  // Parse and consolidate transcript
  const rawEntries = parseTranscript(TRANSCRIPT_FILE);
  const entries = [];
  for (const e of rawEntries) {
    const last = entries[entries.length - 1];
    if (last && last.speaker === e.speaker) {
      last.text += ' ' + e.text;
    } else {
      entries.push({ ...e });
    }
  }

  const playEntries = LIMIT > 0 ? entries.slice(0, LIMIT) : entries;
  const speakers = [...new Set(entries.map(e => e.speaker))];
  const voiceMap = {};
  speakers.forEach((s, i) => { voiceMap[s] = VOICES[i % VOICES.length]; });

  console.log(`Consolidated ${rawEntries.length} → ${entries.length} utterances`);
  console.log(`Playing ${playEntries.length} utterances\n`);
  console.log(`Speakers (${speakers.length}):`);
  speakers.forEach(s => console.log(`  ${s} → ${voiceMap[s]}`));

  const { platform, nativeId, passcode } = parseMeetingUrl(MEETING_URL);
  console.log(`\nPlatform: ${platform}, ID: ${nativeId}\n`);

  // Get/create API keys for each speaker
  console.log('Setting up speaker API keys...');
  const speakerKeys = {};
  for (const s of speakers) {
    const key = await getOrCreateSpeakerKey(s);
    if (key) {
      speakerKeys[s] = key;
      console.log(`  ${s}: OK`);
    } else {
      console.log(`  ${s}: FAILED — will use listener bot`);
    }
  }

  // Create listener bot
  console.log('\nCreating listener bot...');
  const listenerReq = { platform, native_meeting_id: nativeId, bot_name: 'Listener', meeting_url: MEETING_URL };
  if (passcode) listenerReq.passcode = passcode;
  const lr = await api('POST', '/bots', listenerReq);
  if (lr.s >= 400) { console.error('Listener failed:', lr.d); process.exit(1); }
  console.log(`  Listener: meeting ${lr.d.id}`);

  // Create speaker bots (each with their own API key)
  console.log('\nCreating speaker bots...');
  const speakerMeetings = {}; // speaker → meetingId
  for (const s of speakers) {
    if (!speakerKeys[s]) continue;
    const botReq = { platform, native_meeting_id: nativeId, bot_name: s, meeting_url: MEETING_URL };
    if (passcode) botReq.passcode = passcode;
    const r = await api('POST', '/bots', botReq, speakerKeys[s]);
    if (r.s >= 400) {
      console.log(`  ${s}: FAILED — ${JSON.stringify(r.d).substring(0, 100)}`);
    } else {
      speakerMeetings[s] = r.d.id;
      console.log(`  ${s}: meeting ${r.d.id}`);
    }
    await sleep(1000);
  }

  console.log('\n>>> ADMIT ALL BOTS FROM THE MEETING LOBBY <<<\n');

  // Wait for listener
  console.log('Waiting for listener...');
  if (!await waitForBotActive(LISTENER_API_KEY, lr.d.id, 'Listener')) {
    console.error('Listener not active'); process.exit(1);
  }
  console.log('  Listener: ACTIVE');

  // Wait for speakers
  for (const [s, mid] of Object.entries(speakerMeetings)) {
    const active = await waitForBotActive(speakerKeys[s], mid, s);
    console.log(`  ${s}: ${active ? 'ACTIVE' : 'FAILED'}`);
    if (!active) delete speakerMeetings[s];
  }

  console.log('\n--- Starting playback ---\n');
  await sleep(3000);

  const t0 = timeToMs(playEntries[0].time);

  for (let i = 0; i < playEntries.length; i++) {
    const e = playEntries[i];
    const voice = voiceMap[e.speaker];

    // Timing delay
    if (i > 0) {
      const delay = Math.max(0, timeToMs(e.time) - timeToMs(playEntries[i-1].time));
      if (delay > 0 && delay < 30000) await sleep(delay);
    }

    const el = ((timeToMs(e.time) - t0) / 1000).toFixed(0);
    const short = e.text.length > 70 ? e.text.substring(0, 67) + '...' : e.text;
    console.log(`[${e.time}] +${el}s ${e.speaker}: "${short}"`);

    // Speak through speaker's bot (their API key) or listener
    const speakKey = speakerKeys[e.speaker] || LISTENER_API_KEY;
    const r = await api('POST', `/bots/${platform}/${nativeId}/speak`, { text: e.text, voice }, speakKey);
    if (r.s >= 400) console.log(`  SPEAK FAILED: ${JSON.stringify(r.d).substring(0, 80)}`);

    // Wait for playback
    await sleep(Math.max(2000, e.text.length * 60));
  }

  console.log('\n--- Playback complete ---');

  // Compare
  console.log('\nWaiting 20s for transcription...');
  await sleep(20000);

  const tx = await api('GET', `/meeting-transcript/${platform}/${nativeId}`);
  if (tx.s === 200 && tx.d.transcript) {
    const segs = tx.d.transcript;
    console.log(`\n=== RESULTS ===`);
    console.log(`Source: ${playEntries.length} utterances from ${speakers.length} speakers`);
    console.log(`Transcribed: ${segs.length} segments\n`);

    console.log('--- Transcribed (first 30) ---');
    segs.slice(0, 30).forEach((s, i) => console.log(`  ${i+1}. [${s.speaker || '?'}] ${(s.text || '').substring(0, 80)}`));
    if (segs.length > 30) console.log(`  ... +${segs.length - 30} more`);
  }

  console.log(`\nListener meeting: ${lr.d.id}`);
  console.log(`Dashboard: http://localhost:3011/meetings/${lr.d.id}`);
}

main().catch(err => { console.error(err); process.exit(1); });
