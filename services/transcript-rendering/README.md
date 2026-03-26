# Transcript Rendering

TypeScript library for processing real-time transcript streams. Handles segment deduplication, speaker-based grouping, and timestamp parsing. Used by frontend components that consume WebSocket transcript data.

## Exports

```typescript
// Types
TranscriptSegment    // Segment with text, speaker, timestamps, segment_id
SegmentGroup         // Group of consecutive segments merged by speaker
GroupingOptions      // Configuration for grouping behavior

// Functions
deduplicateSegments  // Remove duplicate segments by segment_id
upsertSegments       // Insert or update segments in an existing array
sortSegments         // Sort segments by absolute_start_time
groupSegments        // Group consecutive segments by speaker (configurable)
parseUTCTimestamp    // Parse ISO timestamp strings
```

## TranscriptSegment Fields

| Field | Type | Description |
|-------|------|-------------|
| `text` | `string` | Segment text content |
| `speaker` | `string?` | Speaker name or identifier |
| `absolute_start_time` | `string` | ISO timestamp of segment start |
| `absolute_end_time` | `string` | ISO timestamp of segment end |
| `completed` | `boolean?` | Whether the segment is finalized |
| `segment_id` | `string?` | Stable identity (e.g., `speakerA:3`) |
| `start_time` | `number?` | Relative start time in seconds |
| `end_time` | `number?` | Relative end time in seconds |

## Grouping Options

- `getGroupKey` — Function returning the grouping key for a segment (default: groups by `speaker`).
- `maxCharsPerGroup` — Maximum characters per group before splitting (default: `512`).

## Development

```bash
cd services/transcript-rendering
npm install
npm run build      # Build with tsup (ESM + CJS)
npm test           # Run tests with vitest
npm run typecheck  # Type-check without emitting
```

## Package

Published as `@vexaai/transcript-rendering`. Dual ESM/CJS output via tsup.
