import { log } from '../utils';

/**
 * Post-transcription speaker mapper for MS Teams.
 *
 * Takes Whisper word-level timestamps + caption speaker boundaries,
 * produces speaker-attributed text segments.
 *
 * Whisper transcribes the mixed audio stream (all speakers combined).
 * Captions tell us who spoke when. This engine maps each word to a
 * speaker by matching word timestamps against caption boundaries.
 *
 * Works on any single-channel mixed audio where external speaker
 * boundaries are available (Teams captions, diarization output, etc.)
 */

export interface TimestampedWord {
  word: string;
  start: number;  // seconds
  end: number;    // seconds
  probability?: number;
}

export interface SpeakerBoundary {
  speaker: string;
  start: number;  // seconds
  end: number;    // seconds
}

export interface AttributedSegment {
  speaker: string;
  text: string;
  start: number;  // seconds
  end: number;    // seconds
  words: TimestampedWord[];
  wordCount: number;
}

/**
 * Map words to speakers using timestamp alignment.
 *
 * For each word, finds the speaker boundary that overlaps most with
 * the word's time range. Consecutive words with the same speaker are
 * grouped into segments.
 *
 * Words that fall outside all speaker boundaries get attributed to
 * the nearest speaker (by time distance).
 */
export function mapWordsToSpeakers(
  words: TimestampedWord[],
  speakers: SpeakerBoundary[],
): AttributedSegment[] {
  if (words.length === 0 || speakers.length === 0) return [];

  // Sort both by start time
  const sortedWords = [...words].sort((a, b) => a.start - b.start);
  const sortedSpeakers = [...speakers].sort((a, b) => a.start - b.start);

  // Attribute each word to a speaker
  const attributed: { word: TimestampedWord; speaker: string }[] = [];

  for (const word of sortedWords) {
    const wordMid = (word.start + word.end) / 2;
    let bestSpeaker: string | null = null;
    let bestOverlap = 0;

    // Find speaker with most overlap
    for (const sp of sortedSpeakers) {
      const overlapStart = Math.max(word.start, sp.start);
      const overlapEnd = Math.min(word.end, sp.end);
      const overlap = Math.max(0, overlapEnd - overlapStart);

      if (overlap > bestOverlap) {
        bestOverlap = overlap;
        bestSpeaker = sp.speaker;
      }
    }

    // No overlap — find nearest speaker by midpoint distance
    if (!bestSpeaker) {
      let minDist = Infinity;
      for (const sp of sortedSpeakers) {
        const dist = Math.min(
          Math.abs(wordMid - sp.start),
          Math.abs(wordMid - sp.end),
        );
        if (dist < minDist) {
          minDist = dist;
          bestSpeaker = sp.speaker;
        }
      }
    }

    attributed.push({ word, speaker: bestSpeaker || 'Unknown' });
  }

  // Group consecutive same-speaker words into segments
  const segments: AttributedSegment[] = [];
  let currentSpeaker = attributed[0].speaker;
  let currentWords: TimestampedWord[] = [attributed[0].word];

  for (let i = 1; i < attributed.length; i++) {
    if (attributed[i].speaker === currentSpeaker) {
      currentWords.push(attributed[i].word);
    } else {
      // Emit segment
      segments.push(buildSegment(currentSpeaker, currentWords));
      currentSpeaker = attributed[i].speaker;
      currentWords = [attributed[i].word];
    }
  }
  // Emit last segment
  segments.push(buildSegment(currentSpeaker, currentWords));

  return segments;
}

function buildSegment(speaker: string, words: TimestampedWord[]): AttributedSegment {
  return {
    speaker,
    text: words.map(w => w.word.trim()).join(' ').trim(),
    start: words[0].start,
    end: words[words.length - 1].end,
    words,
    wordCount: words.length,
  };
}

/**
 * Build speaker boundaries from Teams caption events.
 *
 * Captions arrive as (speaker, text, timestamp) events. This converts
 * them into continuous speaker boundary intervals. Consecutive captions
 * from the same speaker are merged into one boundary.
 */
export function captionsToSpeakerBoundaries(
  captions: { speaker: string; timestamp: number }[],
): SpeakerBoundary[] {
  if (captions.length === 0) return [];

  const sorted = [...captions].sort((a, b) => a.timestamp - b.timestamp);
  const boundaries: SpeakerBoundary[] = [];

  let current = { speaker: sorted[0].speaker, start: sorted[0].timestamp };

  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i].speaker !== current.speaker) {
      // Speaker changed — close current boundary, start new
      boundaries.push({
        speaker: current.speaker,
        start: current.start,
        end: sorted[i].timestamp,
      });
      current = { speaker: sorted[i].speaker, start: sorted[i].timestamp };
    }
  }

  // Close last boundary — extend to last caption + 30s buffer
  boundaries.push({
    speaker: current.speaker,
    start: current.start,
    end: sorted[sorted.length - 1].timestamp + 30,
  });

  return boundaries;
}
