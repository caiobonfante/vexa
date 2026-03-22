#!/usr/bin/env node
/**
 * Render a single tick to rendered.md — three-column comparison table.
 *
 * Usage: node tick.js <tick-number>
 *   DATASET=youtube-single-speaker node tick.js 1
 */

const fs = require('fs');
const path = require('path');

const DATASET = process.env.DATASET || 'youtube-single-speaker';
const DATA_DIR = path.resolve(__dirname, '..', '..', 'data');
const CORE_PATH = process.env.CORE_PATH || path.join(DATA_DIR, 'core', DATASET, 'transcript.jsonl');
const GT_PATH = process.env.GT_PATH || path.join(DATA_DIR, 'raw', DATASET, 'ground-truth.json');
const OUT_DIR = process.env.OUT_DIR || __dirname;
const OUT_PATH = path.join(OUT_DIR, 'rendered.md');

const tickNum = parseInt(process.argv[2] || '1');
const ticks = fs.readFileSync(CORE_PATH, 'utf8').trim().split('\n').map(l => JSON.parse(l));
const gt = fs.existsSync(GT_PATH) ? (JSON.parse(fs.readFileSync(GT_PATH, 'utf8')).segments || []) : [];

if (tickNum < 1 || tickNum > ticks.length) {
  console.error(`Tick ${tickNum} out of range (1-${ticks.length})`);
  process.exit(1);
}

const norm = s => (s || '').replace(/\s*\(Guest\)/i, '').trim();

// Accumulate state for current tick and previous tick
function accumulateState(upToTick) {
  const confirmed = new Map();
  const pendingBySpeaker = new Map();
  for (let i = 0; i < upToTick; i++) {
    const tick = ticks[i];
    for (const seg of (tick.confirmed || []).filter(s => s.text?.trim())) {
      confirmed.set(seg.segment_id || seg.absolute_start_time, seg);
    }
    const speaker = tick.speaker;
    const valid = (tick.pending || []).filter(s => s.text?.trim());
    if (valid.length > 0) pendingBySpeaker.set(speaker, valid);
    else pendingBySpeaker.delete(speaker);
  }
  return { confirmed, pendingBySpeaker };
}

function getRendered(state) {
  const { confirmed, pendingBySpeaker } = state;
  const confirmedBySpeaker = new Map();
  for (const seg of confirmed.values()) {
    const sp = seg.speaker || '';
    if (!confirmedBySpeaker.has(sp)) confirmedBySpeaker.set(sp, new Set());
    confirmedBySpeaker.get(sp).add((seg.text || '').trim());
  }
  const all = [...confirmed.values()];
  for (const [speaker, segs] of pendingBySpeaker) {
    const ct = confirmedBySpeaker.get(speaker);
    for (const seg of segs) {
      if (ct?.has((seg.text || '').trim())) continue;
      all.push(seg);
    }
  }
  return all.sort((a, b) => (a.absolute_start_time || '').localeCompare(b.absolute_start_time || ''));
}

function renderLine(seg) {
  const prefix = seg.completed ? '' : '*';
  const suffix = seg.completed ? '' : '*';
  return prefix + seg.text + suffix;
}

// Build states
const currentState = accumulateState(tickNum);
const prevState = tickNum > 1 ? accumulateState(tickNum - 1) : { confirmed: new Map(), pendingBySpeaker: new Map() };
const currentRendered = getRendered(currentState);
const prevRendered = getRendered(prevState);

// Max time for GT window
const maxTime = Math.max(0, ...currentRendered.map(s => s.end || 0));
const gtSegments = gt.filter(s => s.start <= maxTime + 2);

// Build time-aligned rows
// Collect all time points from GT, current rendered, and previous rendered
const allEvents = [];
for (const s of gtSegments) allEvents.push({ time: s.start, gt: (s.text || '').trim() });
for (const s of currentRendered) allEvents.push({ time: s.start || 0, cur: renderLine(s) });
for (const s of prevRendered) allEvents.push({ time: s.start || 0, prev: renderLine(s) });

// Merge events at similar times (within 2s) into rows
const rows = [];
allEvents.sort((a, b) => a.time - b.time);
for (const ev of allEvents) {
  // Find existing row within 2s
  let found = rows.find(r => Math.abs(r.time - ev.time) < 2 && !r[ev.gt ? 'gt' : ev.cur ? 'cur' : 'prev']);
  if (!found) {
    found = { time: ev.time, gt: '', cur: '', prev: '' };
    rows.push(found);
    rows.sort((a, b) => a.time - b.time);
  }
  if (ev.gt) found.gt = ev.gt;
  if (ev.cur) found.cur = ev.cur;
  if (ev.prev) found.prev = ev.prev;
}

const lines = [];
const thisTick = ticks[tickNum - 1];
const newC = (thisTick.confirmed || []).filter(s => s.text?.trim());

lines.push(`# Tick ${tickNum}/${ticks.length} | ${norm(thisTick.speaker)} | ${currentState.confirmed.size} confirmed`);
lines.push('');

if (newC.length > 0) {
  for (const c of newC) lines.push(`**+ "${c.text}"**`);
  lines.push('');
}

// Three columns, one segment per row, no gaps
const rl = (seg) => seg.completed ? seg.text : `[...] ${seg.text}`;

const maxRenderedTime = Math.max(0, ...currentRendered.map(s => s.end || s.start || 0));
const gtLines = gtSegments.filter(s => s.start <= maxRenderedTime + 2).map(s => (s.text || '').trim());
const curLines = currentRendered.map(rl);
const prevLines = prevRendered.map(rl);

fs.mkdirSync(OUT_DIR, { recursive: true });
fs.writeFileSync(path.join(OUT_DIR, 'gt.txt'), gtLines.join('\n') + '\n');
fs.writeFileSync(path.join(OUT_DIR, 'rendered.txt'), curLines.join('\n') + '\n');
fs.writeFileSync(path.join(OUT_DIR, 'last-rendered.txt'), prevLines.join('\n') + '\n');

lines.push(`GT: ${gtLines.length} segments → gt.txt`);
lines.push(`Rendered: ${curLines.length} segments → rendered.txt`);
lines.push(`Last: ${prevLines.length} segments → last-rendered.txt`);

fs.writeFileSync(OUT_PATH, lines.join('\n') + '\n');
console.log(`Tick ${tickNum}/${ticks.length} → gt.txt, rendered.txt, last-rendered.txt`);
