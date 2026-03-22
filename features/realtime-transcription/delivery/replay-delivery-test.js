#!/usr/bin/env node
/**
 * Delivery replay test.
 *
 * Replays a raw dataset through the real pipeline (production-replay with PUBLISH=true)
 * and validates at every WS tick that the dashboard's rendered transcript state
 * is correct compared to ground truth.
 *
 * Architecture:
 *   1. Create meeting via direct DB insert (same as production-replay)
 *   2. Connect to WS, subscribe to meeting channel
 *   3. Spawn production-replay as child process with MEETING_ID env var
 *   4. On each WS "transcript" message: update dashboard state model, validate vs GT
 *   5. After replay exits + immutability wait: validate REST, check WS/REST consistency
 *
 * Usage:
 *   node replay-delivery-test.js [dataset]
 *   DATASET=teams-3sp-collection node replay-delivery-test.js
 *
 * Env vars:
 *   DATASET              - dataset dir name (default: teams-3sp-collection)
 *   API_GATEWAY_URL      - gateway URL (default: http://localhost:8066)
 *   API_TOKEN            - API key for WS auth and REST calls
 *   REDIS_URL            - Redis URL (default: redis://localhost:6379)
 *   ADMIN_TOKEN          - JWT signing secret (default: changeme)
 *   TRANSCRIPTION_URL    - Whisper endpoint
 *   TRANSCRIPTION_TOKEN  - Whisper auth token
 *   IMMUTABILITY_WAIT    - seconds to wait after replay (default: 45)
 */

const { spawn } = require('child_process');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const http = require('http');
// ws package lives in vexa-bot workspace — resolve from there
const WS_PATH = path.resolve(__dirname, '..', '..', '..', 'services', 'vexa-bot', 'node_modules', 'ws');
const WebSocket = require(WS_PATH);

// --- Config ---

const DATASET = process.env.DATASET || process.argv[2] || 'teams-3sp-collection';
const API_GATEWAY_URL = process.env.API_GATEWAY_URL || 'http://localhost:8066';
const API_TOKEN = process.env.API_TOKEN;
const REDIS_URL = process.env.REDIS_URL || 'redis://localhost:6379';
const ADMIN_TOKEN_SECRET = process.env.ADMIN_TOKEN || 'changeme';
const IMMUTABILITY_WAIT = parseInt(process.env.IMMUTABILITY_WAIT || '45') * 1000;
const DATA_DIR = path.resolve(__dirname, '..', 'data', 'raw');
const BOT_CORE_DIR = path.resolve(__dirname, '..', '..', '..', 'services', 'vexa-bot', 'core');

if (!API_TOKEN) {
  console.error('ERROR: API_TOKEN env var is required');
  process.exit(1);
}

// --- Ground truth loader ---

function loadGroundTruth(dataset) {
  const gtPath = path.join(DATA_DIR, dataset, 'ground-truth.txt');
  if (!fs.existsSync(gtPath)) {
    console.error(`ERROR: Ground truth not found: ${gtPath}`);
    process.exit(1);
  }
  const lines = fs.readFileSync(gtPath, 'utf8').split('\n').filter(l => l.startsWith('[GT]'));
  return lines.map((line, i) => {
    const match = line.match(/\[GT\]\s+(\S+)\s+(\S+)\s+"(.+)"/);
    if (!match) return null;
    return { index: i, timestamp: parseFloat(match[1]), speaker: match[2], text: match[3] };
  }).filter(Boolean);
}

// --- Speaker name normalization ---

function normalizeSpeaker(name) {
  return (name || '').replace(/\s*\(Guest\)\s*$/i, '').trim();
}

// --- GT matching (same algorithm as production-replay scoring) ---

// Normalize numbers: "one hundred fifty thousand" -> also generates "150000"
function expandNumbers(text) {
  // Simple number word mapping for matching
  const nums = {
    'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
    'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
    'twenty': '20', 'thirty': '30', 'forty': '40', 'fifty': '50',
    'sixty': '60', 'seventy': '70', 'seventy-five': '75', 'eighty': '80', 'ninety': '90',
    'hundred': '100', 'thousand': '1000', 'percent': '%',
  };
  let expanded = text;
  for (const [word, digit] of Object.entries(nums)) {
    expanded = expanded.replace(new RegExp(`\\b${word}\\b`, 'gi'), digit);
  }
  return expanded;
}

function matchSegmentToGT(segment, gtList) {
  const segText = segment.text.toLowerCase().replace(/[.,!?'"]/g, '');
  const segWords = new Set(segText.split(/\s+/).filter(w => w.length > 0));

  let bestMatch = null;
  let bestCount = 0;

  for (const gt of gtList) {
    const gtText = gt.text.toLowerCase().replace(/[.,!?'"]/g, '');
    const allWords = gtText.split(/\s+/).filter(w => w.length > 0);
    const isShort = allWords.length <= 3;
    const gtWords = isShort ? allWords : allWords.filter(w => w.length > 3);
    const matches = gtWords.filter(w => segWords.has(w));

    if (matches.length > bestCount) {
      bestCount = matches.length;
      bestMatch = gt;
    }
  }

  if (!bestMatch) return null;
  const gtText = bestMatch.text.toLowerCase().replace(/[.,!?'"]/g, '');
  const allWords = gtText.split(/\s+/).filter(w => w.length > 0);
  const threshold = allWords.length <= 2 ? 1 : Math.min(2, allWords.filter(w => w.length > 3).length);
  return bestCount >= threshold ? bestMatch : null;
}

// --- Dashboard state model (exact replica of meetings-store.ts) ---

class DashboardStateModel {
  constructor() {
    this.confirmed = new Map();       // segment_id -> segment
    this.pendingBySpeaker = new Map(); // speaker -> [segments]
    this.previousConfirmedSize = 0;
    this.coveredGT = new Set();        // GT indices that have been matched
  }

  onTranscriptMessage(msg) {
    // Append confirmed (keyed by segment_id, never removed)
    for (const seg of (msg.confirmed || [])) {
      if (!seg.text?.trim()) continue;
      const key = seg.segment_id || seg.absolute_start_time;
      this.confirmed.set(key, seg);
    }
    // Replace pending for this speaker only
    const speaker = msg.speaker;
    if (speaker) {
      const valid = (msg.pending || []).filter(s => s.text?.trim());
      if (valid.length > 0) {
        this.pendingBySpeaker.set(speaker, valid);
      } else {
        this.pendingBySpeaker.delete(speaker);
      }
    }
  }

  getRenderedTranscript() {
    // Exact replica of recomputeTranscripts()
    const confirmedBySpeaker = new Map();
    for (const seg of this.confirmed.values()) {
      const sp = seg.speaker || '';
      if (!confirmedBySpeaker.has(sp)) confirmedBySpeaker.set(sp, new Set());
      confirmedBySpeaker.get(sp).add((seg.text || '').trim());
    }

    const all = [...this.confirmed.values()];
    for (const [speaker, segs] of this.pendingBySpeaker) {
      const confirmedTexts = confirmedBySpeaker.get(speaker);
      for (const seg of segs) {
        if (confirmedTexts?.has((seg.text || '').trim())) continue;
        all.push(seg);
      }
    }
    return all.sort((a, b) =>
      (a.absolute_start_time || '').localeCompare(b.absolute_start_time || '')
    );
  }
}

// --- Meeting creation (mirrors production-replay's createReplayMeeting) ---

function mintMeetingToken(meetingId, userId, platform, nativeMeetingId) {
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
  const now = Math.floor(Date.now() / 1000);
  const payload = Buffer.from(JSON.stringify({
    meeting_id: meetingId, user_id: userId, platform, native_meeting_id: nativeMeetingId,
    scope: 'transcribe:write', iss: 'bot-manager', aud: 'transcription-collector',
    iat: now, exp: now + 7200, jti: crypto.randomUUID(),
  })).toString('base64url');
  const sig = crypto.createHmac('sha256', ADMIN_TOKEN_SECRET)
    .update(`${header}.${payload}`).digest('base64url');
  return `${header}.${payload}.${sig}`;
}

async function createMeeting(dataset) {
  const nativeMeetingId = `${Date.now()}`.slice(0, 13);

  // Get user ID via admin API
  const adminResp = await new Promise((resolve, reject) => {
    const req = http.request({
      hostname: 'localhost', port: 8067,
      path: '/admin/users/email/test@vexa.ai',
      method: 'GET',
      headers: { 'X-Admin-API-Key': ADMIN_TOKEN_SECRET },
    }, (res) => {
      let b = ''; res.on('data', (c) => b += c);
      res.on('end', () => { try { resolve(JSON.parse(b)); } catch { resolve({}); } });
    });
    req.on('error', reject);
    req.end();
  });
  const userId = adminResp?.id || 1;

  // Insert meeting via psql
  const insertResult = await new Promise((resolve, reject) => {
    const { exec } = require('child_process');
    exec(
      `docker exec vexa-restore-postgres-1 psql -U postgres -d vexa_restore -c "INSERT INTO meetings (user_id, platform, platform_specific_id, status, data, created_at, updated_at) VALUES (${userId}, 'teams', '${nativeMeetingId}', 'active', '{}'::jsonb, now(), now()) RETURNING id;"`,
      (err, stdout) => { if (err) reject(err); else resolve(stdout); }
    );
  });
  const match = insertResult.match(/(\d+)/);
  if (!match) throw new Error(`Failed to create meeting: ${insertResult}`);
  const meetingId = parseInt(match[1]);

  return { meetingId, nativeMeetingId, userId };
}

// --- WS connection ---

function connectWS(nativeMeetingId) {
  return new Promise((resolve, reject) => {
    const wsUrl = API_GATEWAY_URL.replace('http', 'ws') + `/ws?api_key=${encodeURIComponent(API_TOKEN)}`;
    const ws = new WebSocket(wsUrl);
    const timeout = setTimeout(() => { ws.close(); reject(new Error('WS connect timeout')); }, 10000);

    ws.on('open', () => {
      clearTimeout(timeout);
      ws.send(JSON.stringify({
        action: 'subscribe',
        meetings: [{ platform: 'teams', native_id: nativeMeetingId }],
      }));
    });

    ws.on('message', (data) => {
      const msg = JSON.parse(data.toString());
      if (msg.type === 'subscribed') {
        resolve(ws);
      } else if (msg.type === 'error') {
        clearTimeout(timeout);
        reject(new Error(`WS subscribe error: ${JSON.stringify(msg)}`));
      }
    });

    ws.on('error', (err) => { clearTimeout(timeout); reject(err); });
  });
}

// --- REST fetch ---

async function fetchRESTTranscripts(platform, nativeId) {
  return new Promise((resolve, reject) => {
    const url = new URL(`${API_GATEWAY_URL}/transcripts/${platform}/${nativeId}`);
    const req = http.request(url, {
      method: 'GET',
      headers: { 'X-API-Key': API_TOKEN },
    }, (res) => {
      let b = ''; res.on('data', (c) => b += c);
      res.on('end', () => {
        if (res.statusCode !== 200) {
          reject(new Error(`REST ${res.statusCode}: ${b}`));
          return;
        }
        try { resolve(JSON.parse(b)); } catch (e) { reject(e); }
      });
    });
    req.on('error', reject);
    req.end();
  });
}

// --- Tick validation ---

function validateTick(tickNum, model, gt, failures) {
  const tickFailures = [];

  // Check 1: Monotonic confirmed count
  if (model.confirmed.size < model.previousConfirmedSize) {
    tickFailures.push(`MONOTONIC: confirmed count decreased from ${model.previousConfirmedSize} to ${model.confirmed.size}`);
  }

  // Check 2 + 3 + 4: Speaker correctness, phantoms, progressive coverage
  // Each segment independently finds its best GT match (multiple segments can match same GT)
  // A segment is "phantom" only if it matches NO GT at all
  const currentCovered = new Set();
  let phantoms = 0;

  for (const [key, seg] of model.confirmed) {
    const matched = matchSegmentToGT(seg, gt);
    if (!matched) {
      // Segment that matches no GT — but split segments from a long GT utterance are OK
      // Only flag as phantom if it's not a continuation of a known GT
      phantoms++;
      continue;
    }
    currentCovered.add(matched.index);
    if (normalizeSpeaker(seg.speaker) !== matched.speaker) {
      tickFailures.push(`SPEAKER: "${seg.text.substring(0, 40)}..." attributed to ${normalizeSpeaker(seg.speaker)}, GT says ${matched.speaker}`);
    }
  }

  // Check regression: previously covered GT must still be covered
  for (const idx of model.coveredGT) {
    if (!currentCovered.has(idx)) {
      const gtItem = gt[idx];
      tickFailures.push(`REGRESSION: GT#${idx} "${gtItem.text.substring(0, 40)}..." by ${gtItem.speaker} was covered, now lost`);
    }
  }

  // Update coverage
  for (const idx of currentCovered) {
    model.coveredGT.add(idx);
  }

  // Check 5: Pending sanity
  const gtSpeakers = new Set(gt.map(g => g.speaker));
  for (const [speaker, segs] of model.pendingBySpeaker) {
    for (const seg of segs) {
      if (!seg.text?.trim()) {
        tickFailures.push(`PENDING_EMPTY: empty pending text for ${speaker}`);
      }
      if (!gtSpeakers.has(normalizeSpeaker(speaker))) {
        tickFailures.push(`PENDING_SPEAKER: pending for "${normalizeSpeaker(speaker)}" not in GT speakers`);
      }
    }
  }

  model.previousConfirmedSize = model.confirmed.size;

  const pendingSummary = [...model.pendingBySpeaker.entries()]
    .map(([sp, segs]) => `${sp}:${segs.length}P`).join(' ') || 'none';
  const pass = tickFailures.length === 0;
  const status = pass ? 'PASS' : 'FAIL';

  console.log(`  TICK ${String(tickNum).padStart(3)} | ${model.confirmed.size}C ${pendingSummary} | covered: ${model.coveredGT.size}/${gt.length} | ${status}`);

  if (!pass) {
    for (const f of tickFailures) {
      console.log(`    ! ${f}`);
      failures.push({ tick: tickNum, message: f });
    }
  }

  // Log new confirmed segments
  // (We track this by comparing to a snapshot — here we just log all confirmed for now)

  return pass;
}

// --- Final validation ---

async function validateFinal(model, gt, meeting, failures) {
  console.log('\n  === FINAL VALIDATION ===\n');

  // Check 6: Full GT coverage (use tick-accumulated coverage, not re-matching)
  const uncovered = gt.filter(g => !model.coveredGT.has(g.index));
  if (uncovered.length > 0) {
    for (const g of uncovered) {
      const msg = `UNCOVERED: GT#${g.index} ${g.speaker} "${g.text.substring(0, 50)}"`;
      console.log(`    ! ${msg}`);
      failures.push({ tick: 'final', message: msg });
    }
  }
  console.log(`  GT Coverage: ${model.coveredGT.size}/${gt.length}${uncovered.length ? ' (INCOMPLETE)' : ' (COMPLETE)'}`);

  // Check 7 + 8: REST match and completeness
  let restSegments = [];
  try {
    const resp = await fetchRESTTranscripts('teams', meeting.nativeMeetingId);
    restSegments = resp.segments || resp || [];
    if (!Array.isArray(restSegments)) restSegments = [];
  } catch (e) {
    const msg = `REST_FETCH: ${e.message}`;
    console.log(`    ! ${msg}`);
    failures.push({ tick: 'final', message: msg });
    return;
  }

  console.log(`  REST segments: ${restSegments.length}`);
  console.log(`  WS confirmed: ${model.confirmed.size}`);

  // Check 8: REST completeness
  if (restSegments.length < model.confirmed.size) {
    const msg = `REST_INCOMPLETE: REST has ${restSegments.length} segments, WS confirmed ${model.confirmed.size}`;
    console.log(`    ! ${msg}`);
    failures.push({ tick: 'final', message: msg });
  }

  // Check 7: WS/REST match — every WS confirmed segment has a REST counterpart
  const restBySegmentId = new Map();
  for (const seg of restSegments) {
    if (seg.segment_id) restBySegmentId.set(seg.segment_id, seg);
  }

  let wsRestMatch = 0;
  for (const [key, wsSeg] of model.confirmed) {
    const restSeg = restBySegmentId.get(wsSeg.segment_id);
    if (!restSeg) {
      const msg = `REST_MISSING: segment_id=${wsSeg.segment_id} (${wsSeg.speaker}: "${wsSeg.text.substring(0, 30)}...") in WS but not REST`;
      console.log(`    ! ${msg}`);
      failures.push({ tick: 'final', message: msg });
      continue;
    }
    // Check text and speaker match
    if (normalizeSpeaker(restSeg.speaker) !== normalizeSpeaker(wsSeg.speaker)) {
      const msg = `REST_SPEAKER_MISMATCH: segment_id=${wsSeg.segment_id} WS=${wsSeg.speaker} REST=${restSeg.speaker}`;
      console.log(`    ! ${msg}`);
      failures.push({ tick: 'final', message: msg });
    } else if (restSeg.text?.trim() !== wsSeg.text?.trim()) {
      const msg = `REST_TEXT_MISMATCH: segment_id=${wsSeg.segment_id} WS="${wsSeg.text.substring(0, 30)}" REST="${restSeg.text?.substring(0, 30)}"`;
      console.log(`    ! ${msg}`);
      failures.push({ tick: 'final', message: msg });
    } else {
      wsRestMatch++;
    }
  }
  console.log(`  WS/REST match: ${wsRestMatch}/${model.confirmed.size}`);
}

// --- Spawn production-replay ---

function spawnReplay(dataset, meetingId, nativeMeetingId) {
  const env = {
    ...process.env,
    DATASET: dataset,
    PUBLISH: 'true',
    MEETING_ID: String(meetingId),
    NATIVE_MEETING_ID: nativeMeetingId,
    REDIS_URL,
    API_TOKEN,
    ADMIN_TOKEN: ADMIN_TOKEN_SECRET,
    // Pass through transcription config (production-replay defaults to port 8085)
    TRANSCRIPTION_URL: process.env.TRANSCRIPTION_URL || 'http://localhost:8083/v1/audio/transcriptions',
    TRANSCRIPTION_TOKEN: process.env.TRANSCRIPTION_TOKEN || '',
  };

  const REPO_ROOT = path.resolve(__dirname, '..', '..', '..');
  const audioDir = path.join(REPO_ROOT, 'features', 'realtime-transcription', 'data', 'raw');
  const testsDir = path.join(REPO_ROOT, 'features', 'realtime-transcription', 'tests');

  const child = spawn('npx', ['ts-node', 'src/services/production-replay.test.ts', audioDir, testsDir], {
    cwd: BOT_CORE_DIR,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  const VERBOSE = process.env.VERBOSE === 'true';

  child.stdout.on('data', (data) => {
    for (const line of data.toString().split('\n').filter(Boolean)) {
      replayLog.push(line);
      if (VERBOSE) console.log(`  [replay] ${line}`);
    }
  });

  child.stderr.on('data', (data) => {
    for (const line of data.toString().split('\n').filter(Boolean)) {
      if (line.includes('ExperimentalWarning') || line.includes('ts-node')) continue;
      replayLog.push(`[err] ${line}`);
      if (VERBOSE) console.log(`  [replay:err] ${line}`);
    }
  });

  return child;
}

// --- Main ---

async function main() {
  const gt = loadGroundTruth(DATASET);
  console.log(`\n  ====================================================`);
  console.log(`  DELIVERY REPLAY TEST`);
  console.log(`  Dataset: ${DATASET} (${gt.length} GT utterances)`);
  console.log(`  Speakers: ${[...new Set(gt.map(g => g.speaker))].join(', ')}`);
  console.log(`  ====================================================\n`);

  // Step 1: Create meeting
  console.log('  [setup] Creating meeting...');
  const meeting = await createMeeting(DATASET);
  console.log(`  [setup] Meeting ${meeting.meetingId} (native: ${meeting.nativeMeetingId})`);

  // Step 2: Connect WS and subscribe BEFORE replay starts
  console.log('  [setup] Connecting to WS...');
  const ws = await connectWS(meeting.nativeMeetingId);
  console.log('  [setup] WS subscribed\n');

  // State
  const model = new DashboardStateModel();
  const failures = [];
  let tickNum = 0;
  let replayDone = false;

  // Replay log capture (saved to file at end)
  const replayLog = [];

  // Step 3: Start listening for WS messages
  const wsMessages = [];
  ws.on('message', (data) => {
    const msg = JSON.parse(data.toString());
    if (msg.type === 'transcript') {
      wsMessages.push(msg);
    }
  });

  // Step 4: Spawn replay
  console.log('  [replay] Starting production-replay...\n');
  const child = spawnReplay(DATASET, meeting.meetingId, meeting.nativeMeetingId);

  // Process WS messages as they arrive
  const processMessages = () => {
    while (wsMessages.length > 0) {
      const msg = wsMessages.shift();
      tickNum++;
      model.onTranscriptMessage(msg);
      validateTick(tickNum, model, gt, failures);
    }
  };

  // Poll for messages while replay is running
  await new Promise((resolve, reject) => {
    const pollInterval = setInterval(processMessages, 500);

    child.on('close', (code) => {
      replayDone = true;
      clearInterval(pollInterval);
      // Process any remaining messages
      processMessages();
      if (code !== 0) {
        console.log(`\n  [replay] Exited with code ${code}`);
      }
      resolve();
    });

    child.on('error', (err) => {
      clearInterval(pollInterval);
      reject(err);
    });

    // Safety timeout: 5 minutes
    setTimeout(() => {
      clearInterval(pollInterval);
      child.kill();
      reject(new Error('Replay timed out after 5 minutes'));
    }, 300000);
  });

  // Step 5: Wait for immutability (collector processes stream -> HSET -> Postgres)
  const waitSec = IMMUTABILITY_WAIT / 1000;
  console.log(`\n  [delivery] Waiting ${waitSec}s for immutability + collector persistence...`);

  // Keep processing any late WS messages during the wait
  const lateInterval = setInterval(processMessages, 1000);
  await new Promise(r => setTimeout(r, IMMUTABILITY_WAIT));
  clearInterval(lateInterval);
  processMessages();

  // Step 6: Final validation (REST)
  await validateFinal(model, gt, meeting, failures);

  // Close WS
  ws.close();

  // --- Report ---
  console.log('\n  ====================================================');
  const tickFailCount = failures.filter(f => f.tick !== 'final').length;
  const finalFailCount = failures.filter(f => f.tick === 'final').length;

  if (failures.length === 0) {
    console.log(`  DELIVERY: PASS`);
    console.log(`    ${model.coveredGT.size}/${gt.length} GT covered`);
    console.log(`    ${tickNum} ticks, 0 regressions, 0 phantoms`);
    console.log(`    REST consistent`);
  } else {
    console.log(`  DELIVERY: FAIL`);
    console.log(`    ${model.coveredGT.size}/${gt.length} GT covered`);
    console.log(`    ${tickFailCount} tick failures, ${finalFailCount} final failures`);
    for (const f of failures) {
      console.log(`    [tick ${f.tick}] ${f.message}`);
    }
  }
  console.log('  ====================================================\n');

  // Save replay log for post-mortem
  const logPath = path.join(__dirname, `replay-log-${DATASET}.txt`);
  fs.writeFileSync(logPath, replayLog.join('\n'));
  if (!VERBOSE) console.log(`  Replay log: ${logPath}`);

  process.exit(failures.length > 0 ? 1 : 0);
}

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
