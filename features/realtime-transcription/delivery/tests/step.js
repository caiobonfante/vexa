#!/usr/bin/env node
/**
 * Interactive tick stepper for delivery testing.
 *
 * Reads core ticks (transcript.jsonl) and ground truth (ground-truth.json),
 * creates a meeting, publishes one tick at a time to WS via SegmentPublisher.
 * You watch the dashboard and compare to GT. Press Enter for the next tick.
 *
 * Usage:
 *   node step.js [dataset]
 *   DATASET=youtube-single-speaker node step.js
 *
 * Env vars:
 *   DATASET          - dataset name (default: youtube-single-speaker)
 *   API_TOKEN        - API key for WS auth
 *   REDIS_URL        - Redis URL (default: redis://172.25.0.2:6379)
 *   ADMIN_TOKEN      - JWT signing secret (default: changeme)
 *   API_GATEWAY_URL  - gateway URL (default: http://localhost:8066)
 */

const fs = require('fs');
const path = require('path');
const http = require('http');
const crypto = require('crypto');
const readline = require('readline');

const DATASET = process.env.DATASET || process.argv[2] || 'youtube-single-speaker';
const API_TOKEN = process.env.API_TOKEN;
const REDIS_URL = process.env.REDIS_URL || 'redis://172.25.0.2:6379';
const ADMIN_TOKEN_SECRET = process.env.ADMIN_TOKEN || 'changeme';
const API_GATEWAY_URL = process.env.API_GATEWAY_URL || 'http://localhost:8066';

const DATA_DIR = path.resolve(__dirname, '..', '..', 'data');
const CORE_PATH = path.join(DATA_DIR, 'core', DATASET, 'transcript.jsonl');
const GT_PATH = path.join(DATA_DIR, 'raw', DATASET, 'ground-truth.json');

if (!API_TOKEN) { console.error('ERROR: API_TOKEN required'); process.exit(1); }

// --- Load data ---

function loadTicks() {
  if (!fs.existsSync(CORE_PATH)) {
    console.error(`Core ticks not found: ${CORE_PATH}`);
    console.error('Run: DATASET=' + DATASET + ' make play-replay');
    process.exit(1);
  }
  return fs.readFileSync(CORE_PATH, 'utf8').trim().split('\n').map(l => JSON.parse(l));
}

function loadGT() {
  if (!fs.existsSync(GT_PATH)) {
    console.log('  (no ground-truth.json — GT comparison disabled)');
    return null;
  }
  const data = JSON.parse(fs.readFileSync(GT_PATH, 'utf8'));
  return data.segments || data;
}

// --- Meeting creation ---

function mintToken(meetingId, userId, platform, nativeId) {
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
  const now = Math.floor(Date.now() / 1000);
  const payload = Buffer.from(JSON.stringify({
    meeting_id: meetingId, user_id: userId, platform, native_meeting_id: nativeId,
    scope: 'transcribe:write', iss: 'bot-manager', aud: 'transcription-collector',
    iat: now, exp: now + 7200, jti: crypto.randomUUID(),
  })).toString('base64url');
  const sig = crypto.createHmac('sha256', ADMIN_TOKEN_SECRET)
    .update(`${header}.${payload}`).digest('base64url');
  return `${header}.${payload}.${sig}`;
}

async function createMeeting() {
  const nativeId = `${Date.now()}`.slice(0, 13);
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
  const insertResult = await new Promise((resolve, reject) => {
    const { exec } = require('child_process');
    exec(
      `docker exec vexa-restore-postgres-1 psql -U postgres -d vexa_restore -c "INSERT INTO meetings (user_id, platform, platform_specific_id, status, data, created_at, updated_at) VALUES (${userId}, 'teams', '${nativeId}', 'active', '{}'::jsonb, now(), now()) RETURNING id;"`,
      (err, stdout) => { if (err) reject(err); else resolve(stdout); }
    );
  });
  const match = insertResult.match(/(\d+)/);
  if (!match) throw new Error(`Failed to create meeting: ${insertResult}`);
  return { meetingId: parseInt(match[1]), nativeId, userId };
}

// --- SegmentPublisher (inline, minimal) ---

async function createPublisher(redisUrl, meetingId, token, sessionUid) {
  const { createClient } = require(path.resolve(__dirname, '..', '..', '..', '..', 'services', 'vexa-bot', 'node_modules', 'redis'));
  const client = createClient({ url: redisUrl });
  await client.connect();

  return {
    async publishTick(speaker, confirmed, pending) {
      // XADD confirmed for persistence
      for (const seg of confirmed) {
        const payload = JSON.stringify({
          type: 'transcription', token, uid: sessionUid,
          platform: 'teams', meeting_id: String(meetingId),
          segments: [seg],
        });
        await client.xAdd('transcription_segments', '*', { payload });
      }

      // Store pending in Redis
      const pendingKey = `meeting:${meetingId}:pending:${speaker}`;
      if (pending.length > 0) {
        await client.set(pendingKey, JSON.stringify(pending), { EX: 60 });
      } else {
        await client.del(pendingKey);
      }

      // PUBLISH to WS channel
      const wsChannel = `tc:meeting:${meetingId}:mutable`;
      await client.publish(wsChannel, JSON.stringify({
        type: 'transcript',
        meeting: { id: meetingId },
        speaker,
        confirmed,
        pending,
        ts: new Date().toISOString(),
      }));
    },

    async close() {
      await client.disconnect();
    },
  };
}

// --- Display helpers ---

function norm(speaker) {
  return (speaker || '').replace(/\s*\(Guest\)/i, '').trim();
}

function printRendered(confirmed, pendingBySpeaker) {
  const all = [...confirmed.values()];
  const confirmedBySpeaker = new Map();
  for (const seg of confirmed.values()) {
    const sp = seg.speaker || '';
    if (!confirmedBySpeaker.has(sp)) confirmedBySpeaker.set(sp, new Set());
    confirmedBySpeaker.get(sp).add((seg.text || '').trim());
  }
  for (const [speaker, segs] of pendingBySpeaker) {
    const ct = confirmedBySpeaker.get(speaker);
    for (const seg of segs) {
      if (ct?.has((seg.text || '').trim())) continue;
      all.push(seg);
    }
  }
  all.sort((a, b) => (a.absolute_start_time || '').localeCompare(b.absolute_start_time || ''));

  console.log('');
  for (const seg of all) {
    const mark = seg.completed ? 'C' : 'P';
    const sp = norm(seg.speaker).padEnd(10);
    console.log(`    [${mark}] ${sp} "${seg.text.substring(0, 75)}"`);
  }
}

function printGT(gt, maxTimeSec) {
  if (!gt) return;
  const relevant = gt.filter(s => s.start <= maxTimeSec + 5);
  if (relevant.length === 0) return;
  console.log('\n  GT (up to ~' + Math.round(maxTimeSec) + 's):');
  for (const s of relevant.slice(-5)) {
    console.log(`    [${s.start.toFixed(1)}-${s.end.toFixed(1)}] "${(s.text || '').trim().substring(0, 75)}"`);
  }
}

// --- Main ---

async function main() {
  const ticks = loadTicks();
  const gt = loadGT();

  console.log(`\n  Dataset: ${DATASET}`);
  console.log(`  Ticks: ${ticks.length}`);
  if (gt) console.log(`  GT segments: ${gt.length}`);

  // Create meeting + publisher
  const meeting = await createMeeting();
  const token = mintToken(meeting.meetingId, meeting.userId, 'teams', meeting.nativeId);
  const sessionUid = `step-${DATASET}-${Date.now()}`;
  const pub = await createPublisher(REDIS_URL, meeting.meetingId, token, sessionUid);

  console.log(`\n  Meeting: ${meeting.meetingId}`);
  console.log(`  Dashboard: http://localhost:3011/meetings/${meeting.meetingId}`);
  console.log(`\n  Open the dashboard, then press Enter to start.\n`);

  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  const waitForEnter = () => new Promise(resolve => rl.question('  [Enter] ', resolve));

  // State model
  const confirmed = new Map();
  const pendingBySpeaker = new Map();
  const t0 = new Date(ticks[0].ts).getTime();

  await waitForEnter();

  for (let i = 0; i < ticks.length; i++) {
    const tick = ticks[i];
    const elapsed = ((new Date(tick.ts).getTime() - t0) / 1000).toFixed(1);
    const speaker = tick.speaker;
    const newConfirmed = (tick.confirmed || []).filter(s => s.text?.trim());
    const newPending = (tick.pending || []).filter(s => s.text?.trim());

    // Update local state
    for (const seg of newConfirmed) {
      const key = seg.segment_id || seg.absolute_start_time;
      confirmed.set(key, seg);
    }
    if (newPending.length > 0) {
      pendingBySpeaker.set(speaker, newPending);
    } else {
      pendingBySpeaker.delete(speaker);
    }

    // Publish to WS
    await pub.publishTick(speaker, newConfirmed, newPending);

    // Display
    console.log(`\n  TICK ${String(i + 1).padStart(3)} | ${elapsed}s | ${norm(speaker)} | ${confirmed.size}C`);

    if (newConfirmed.length > 0) {
      for (const c of newConfirmed) {
        console.log(`    + CONFIRMED: "${c.text.substring(0, 70)}"`);
      }
    }
    if (newPending.length > 0) {
      console.log(`    ~ PENDING:   "${newPending[0].text.substring(0, 70)}"`);
    }

    // Show current max time for GT reference
    const maxTime = Math.max(
      ...[...confirmed.values()].map(s => s.end || 0),
      ...newPending.map(s => s.end || 0),
    );

    console.log('\n  RENDERED:');
    printRendered(confirmed, pendingBySpeaker);
    printGT(gt, maxTime);

    if (i < ticks.length - 1) {
      await waitForEnter();
    }
  }

  console.log(`\n  Done. ${ticks.length} ticks, ${confirmed.size} confirmed segments.`);
  console.log(`  Dashboard: http://localhost:3011/meetings/${meeting.meetingId}\n`);

  rl.close();
  await pub.close();
}

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
