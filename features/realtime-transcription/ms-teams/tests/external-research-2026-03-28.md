# External Research: MS Teams Realtime Transcription Re-evaluation

Date: 2026-03-28
Researcher: researcher agent (external)
Context: Re-evaluation of Teams realtime transcription architecture. Current results (2026-03-23): 9/9 E2E, 18/20 stress, 100% speaker accuracy, 14-15% WER.

---

## Teams Platform Changes

### Bot Detection (MC1251206) — No Changes Since Last Research

The bot detection feature announced March 13 remains on track:
- **Mid-May 2026**: Targeted release
- **Mid-June 2026**: GA worldwide + GCC
- Detected bots labeled "Unverified" in "Suspected threats" lobby section
- Organizer must explicitly and individually admit each bot (no batch-admit)
- Admin policy in Teams admin center, enabled by default
- **PowerShell cmdlet not yet published** as of March 2026 (Teams PS module v7.6 has no setting)

No new technical details about detection signals since the existing `bot-detection-research.md`. Microsoft's stance remains: "detection is not perfect and might not pick up every third-party recording bot."

**New finding**: UC Today framed the feature as security against "malicious actors masquerading as legitimate tools" — suggesting Microsoft is positioning this as a security feature, not just an anti-bot feature. This makes it less likely to be softened under industry pressure.

Sources:
- [Office365 IT Pros](https://office365itpros.com/2026/03/16/third-party-recording-bots/)
- [UC Today](https://www.uctoday.com/security-compliance-risk/microsoft-teams-rolling-out-update-to-boost-it-scrutiny-of-meeting-bots/)
- [TechCommunity discussion](https://techcommunity.microsoft.com/discussions/microsoftteams/teams-meetings-to-block-third-party-recording-bots/4502502) — no replies yet (zero community feedback)

### Explicit Consent for Recording (MC1163766) — NEW

A **separate** policy requiring explicit participant consent for recording/transcription in 1:1 calls:
- **PowerShell**: `Set-CsTeamsCallingPolicy -Identity Global -ExplicitRecordingConsent "Enabled"`
- **Default**: Disabled (must be explicitly activated by admins)
- **Rollout**: Jan–April 2026 (GA)
- **Scope**: 1:1 VoIP calls ONLY — does NOT apply to group meetings
- **Platforms**: Desktop (Windows, macOS) only

**Impact on Vexa**: Minimal for now — this only affects 1:1 calls, not meetings. But it signals Microsoft's direction toward requiring consent for all recording. Expect a meeting equivalent in 2026-2027.

Source: [MWPro blog on MC1163766](https://mwpro.co.uk/blog/2026/03/20/updated-new-policy-setting-to-require-explicit-consent-for-recording-and-transcription-in-teams-11-calls-mc1163766-4/)

### WebRTC / RTCPeerConnection — No Breaking Changes

WebRTC deprecation announced only for **VDI environments** (Citrix/AVD/Windows 365), transitioning to SlimCore architecture. This does NOT affect:
- Browser-based Teams web client
- RTCPeerConnection hooks in Playwright/Puppeteer
- Audio capture via the existing approach

The browser client continues to use standard WebRTC. Our RTCPeerConnection hook remains valid.

Source: [Microsoft TechCommunity: Next Chapter of Teams in Virtualized Environments](https://techcommunity.microsoft.com/blog/microsoftteamsblog/the-next-chapter-of-microsoft-teams-in-virtualized-environments/4498259)

### DOM Structure / Caption Selectors — No Evidence of Changes

No public documentation of changes to `data-tid` selectors for captions. The selectors verified in our March 25 research remain:
- `[data-tid="closed-caption-renderer-wrapper"]`
- `[data-tid="author"]`
- `[data-tid="closed-caption-text"]`

Classic Teams client ended availability July 2025; all users on new Teams v2. DOM should be stable since single codebase.

**Risk**: Microsoft does not document or guarantee DOM stability for `data-tid` attributes. These are internal implementation details that can change without notice in any Teams update.

---

## Communication Compliance

### Compliance Recording Bots — Exemption Status UNCLEAR

Microsoft has a [compliance recording certification program](https://learn.microsoft.com/en-us/microsoftteams/teams-recording-compliance) for partners (Verint, Luware, NICE, etc.). These bots use the Graph Communications API and are registered Azure AD applications.

**Key question**: Are certified compliance recording bots exempt from the new bot detection?

**Finding**: No source explicitly confirms or denies an exemption. The language in MC1251206 says "external third-party bots" — compliance recording bots are also third-party, but they are Azure AD-registered and use official APIs. Likely they are treated differently, but this is unconfirmed.

**Important distinction**:
- **Compliance recording bots**: Use Graph API, Azure AD-registered, tenant-configured via policy
- **Browser-based bots (us)**: Join as anonymous/guest participants via web client

The detection feature appears to target the latter category specifically, based on "meeting join metadata" analysis. Compliance recording bots joining via Graph API would have different metadata (valid Azure AD tokens, registered app ID).

### Recording Consent Banners

Teams already shows consent banners when recording/transcription starts. The ExplicitRecordingConsent policy (MC1163766) adds opt-in/opt-out for 1:1 calls. For meetings, consent is still implied by remaining in the meeting after the banner appears.

### GDPR / Regional Considerations

No new region-specific compliance requirements found for meeting recording bots in 2025-2026 beyond existing GDPR, CCPA, and BIPA frameworks. Fireflies.ai is facing a BIPA class-action lawsuit (Illinois biometric privacy) — relevant for any service capturing voice data from Illinois participants.

---

## Native Transcription APIs

### Graph API — Still Post-Meeting Only

The Graph API `callTranscript` resource provides transcript retrieval **after** a meeting ends. No real-time transcript streaming API exists.

Recent additions:
- **`meetingSpokenLanguageTag`** property on `onlineMeeting` — specify spoken language for transcription
- **Change notifications** (webhooks) for transcripts and recordings — get notified when transcript is ready (replaces polling)
- **Ad hoc call support** for transcript/recording change notifications

**Verdict**: Graph API remains a post-meeting-only path. Not useful for real-time transcription.

Source: [Microsoft Learn: Meeting Transcripts Overview](https://learn.microsoft.com/en-us/microsoftteams/platform/graph-api/meeting-transcripts/overview-transcripts)

### Application-Hosted Media Bots — Unchanged

Still requires C#/.NET, Windows Server on Azure, per-VM public IP. SDK auto-deprecates after 3 months. Provides unmixed per-speaker audio. Not viable for our architecture.

### Google Meet Media API (Contrast Point)

Google's Meet Media API (Developer Preview) provides native WebRTC access to real-time media streams — **without a bot joining as a participant**. This is what Microsoft does NOT offer:
- Real-time audio/video via WebRTC
- First-class API, not browser automation
- Currently preview-only (all participants must be in developer preview)
- Active development (last updated Dec 2025)

**Strategic note**: Google is moving toward enabling third-party real-time access. Microsoft is moving toward restricting it. This divergence increases the strategic value of Google Meet support.

Source: [Google Meet Media API Overview](https://developers.google.com/workspace/meet/media-api/guides/overview)

---

## Streaming ASR Alternatives

### Commercial Streaming APIs (2026 Benchmarks)

| Provider | Model | WER | Streaming Latency | Pricing | Key Advantage |
|----------|-------|-----|-------------------|---------|---------------|
| **Deepgram** | Nova-3 | 5.26% (batch) | Native streaming, sub-300ms | $0.0077/min ($0.46/hr) | Built-in end-of-turn, 10+ languages |
| **AssemblyAI** | Universal-3 Pro | 8.14% | ~150ms P50 | $0.45/hr | Best entity recognition (16.7% missed) |
| **OpenAI** | GPT-4o Transcribe | ~5.4% | ~500ms (via Realtime API) | $0.06/min input | Integrated with GPT ecosystem |
| **Microsoft Azure** | Azure Speech | 13-23% | WebSocket streaming | $1.00/hr real-time | Deepest Teams integration |
| **Google** | Chirp 3 | Not published | 1-3s | $0.72-0.96/hr | Multi-modal, US only |

**vs. Our current approach** (faster-whisper HTTP POST):
- Our WER: 14-15%. Deepgram Nova-3 achieves 5.26% — a **~3x improvement**.
- Our approach: batch POST every N seconds. Commercial APIs: native WebSocket streaming with sub-300ms latency.
- Cost: Deepgram at $0.46/hr would cost ~$0.15 per 20-minute meeting.

### Open-Source Models (2026 Benchmarks)

| Model | WER | Speed (RTF) | Streaming | Notes |
|-------|-----|-------------|-----------|-------|
| **Canary Qwen 2.5B** | 5.63% | 418x | No (batch) | Best open-source accuracy |
| **IBM Granite Speech 8B** | 5.85% | N/A | N/A | New entrant, English + multilingual |
| **Whisper Large V3** | 7.4% | ~100x+ | No | Our current model |
| **Whisper Large V3 Turbo** | 7.75% | 216x | No | 2x faster, similar accuracy |
| **Parakeet TDT 1.1B** | ~8.0% | >2000x | **Yes** (RNN-T) | Native streaming, extremely fast |
| **Distil-Whisper Large V3** | ~7.5% | 5-6x Whisper | No | English-only distilled |

**Key finding — Parakeet TDT 1.1B**: NVIDIA's RNN-Transducer architecture enables **native streaming** with minimal latency. At >2000x real-time factor, it could replace faster-whisper for real-time use cases while being self-hosted. WER is comparable to Whisper V3.

### SimulStreaming (Replaces WhisperStreaming)

SimulStreaming by Dominik Machacek (same author as WhisperStreaming) is **SOTA 2025** for simultaneous speech-to-text:
- **5x faster** than WhisperStreaming
- Uses AlignAtt policy for encoder-decoder attention alignment
- Won IWSLT 2025 Simultaneous Speech Translation Shared Task
- Integrated into WhisperLiveKit

Source: [GitHub: ufal/SimulStreaming](https://github.com/ufal/SimulStreaming)

### WhisperLiveKit (Full Pipeline)

WhisperLiveKit now integrates:
- **SimulStreaming** (SOTA 2025) for ultra-low latency transcription
- **Streaming Sortformer** (SOTA 2025) + **pyannote** for diarization
- WebSocket streaming with FFmpeg audio decoding
- Multi-user support with VAD
- Browser-based frontend

**This is the closest open-source equivalent to our full pipeline** (streaming Whisper + speaker diarization). However, it uses a different diarization approach (pyannote on raw audio) vs. our caption-based attribution.

Source: [GitHub: QuentinFuxa/WhisperLiveKit](https://github.com/QuentinFuxa/WhisperLiveKit)

### Recommendation for Our Architecture

Our current faster-whisper HTTP POST approach works but leaves significant WER improvement on the table:

1. **Quick win**: Upgrade to Whisper Large V3 Turbo (7.75% WER vs our 14-15%, 2x faster)
2. **Better win**: Switch to Deepgram Nova-3 API ($0.46/hr, 5.26% WER, native streaming)
3. **Self-hosted win**: Evaluate Parakeet TDT 1.1B for native streaming (8% WER, >2000x RTF)
4. **Long-term**: Integrate SimulStreaming via WhisperLiveKit for SOTA streaming quality

Note: Our 14-15% WER may be partially due to the chunked HTTP POST approach (losing context at chunk boundaries), not just the model. Switching to true streaming could improve WER even with the same model.

---

## Caption-Based Speaker Attribution

### Competitor Validation

**Recall.ai confirmed** using caption scraping for Teams speaker attribution:
- `span[data-tid="author"]` for speaker name
- MutationObserver + finalization detection
- Same approach as ours

No other competitor publicly documents caption-based attribution. Most (Otter, Fireflies, tl;dv) use proprietary post-hoc diarization on mixed audio, which is less accurate for real-time use.

**Our 100% speaker accuracy validates this approach** — caption-based attribution is fundamentally more reliable than audio-only diarization for Teams meetings because it leverages Teams' own server-side ASR.

### Audio-Only Diarization Alternatives

If caption-based attribution were to become unavailable (e.g., DOM structure change, caption policy restriction):

| Approach | Accuracy | Latency | Effort |
|----------|----------|---------|--------|
| **pyannote 4.0** (community-1) | Good for clear audio, degrades with overlap | Near-real-time (~2.5% RTF) | High — pure PyTorch, needs GPU |
| **AssemblyAI streaming diarization** | 30% improved in noisy environments (2025) | ~150ms | Low — API call, $0.45/hr |
| **WhisperLiveKit + Sortformer** | SOTA streaming diarization | Low | Medium — self-hosted |
| **SpeakerLM (LLM-based)** | Refines cascaded systems | Post-processing | Research-only |

**Assessment**: Audio-only diarization on mixed Teams audio would be significantly worse than our current caption-based approach. Mixed audio with overlapping speech is one of the hardest diarization scenarios. Caption-based attribution bypasses this entirely by using Teams' server-side ASR which has access to per-participant audio.

### pyannote 4.0 Update

pyannote.audio released version 4.0 with `community-1` model:
- Removed onnxruntime dependency (pure PyTorch)
- Commercial offering (pyannoteAI) has real-time diarization as premium feature
- Open-source 4.0 is primarily batch-oriented
- Real-time factor: ~2.5% on V100 GPU (1.5 min to process 1 hour)

Source: [pyannote.ai](https://www.pyannote.ai/)

---

## Risks & Recommendations

### Risk Matrix (Updated)

| Risk | Severity | Timeline | Mitigation |
|------|----------|----------|------------|
| **Bot detection** (MC1251206) | HIGH | May-June 2026 | Accept labeling, educate organizers; long-term: signed-in bots or Desktop SDK |
| **DOM selector change** | MEDIUM | Any time | Monitor Teams updates; caption selectors are internal, ungauranteed |
| **Caption policy restriction** | LOW | Unknown | Per-participant captions unaffected by org policy in current implementation |
| **Explicit recording consent** (MC1163766) | LOW (now) | Already rolling out | Only 1:1 calls; watch for meeting extension in 2026-2027 |
| **WER gap vs competitors** | MEDIUM | Ongoing | Our 14-15% vs Deepgram 5.26% is a competitive disadvantage |
| **Microsoft strategic hostility** | HIGH | Ongoing | Microsoft is actively discouraging third-party meeting bots |

### Top Recommendations

1. **Investigate WER improvement** — Our 14-15% WER is roughly 3x worse than Deepgram Nova-3 (5.26%). Either:
   - Switch to Deepgram Nova-3 streaming API ($0.46/hr), OR
   - Upgrade to Whisper V3 Turbo (self-hosted, should improve to ~8%), OR
   - Try SimulStreaming for context-aware streaming (should improve WER by preserving context across chunks)

2. **Bot detection preparation** — The May 2026 rollout is < 2 months away:
   - **Phase 1**: Accept detection, ensure organizer education UX
   - **Phase 2**: Support signed-in bots (trusted domain accounts)
   - **Phase 3**: Evaluate Desktop SDK approach (like Recall.ai)

3. **No need to change caption-based attribution** — Our approach is validated by Recall.ai doing the same thing. 100% speaker accuracy with server-side ASR attribution is superior to any audio-only diarization approach on mixed audio.

4. **Monitor Google Meet Media API** — Google's approach (real-time WebRTC API, no bot participant) is the future. If it exits preview, it would be a significant improvement over browser automation for GMeet.

5. **Do NOT pivot to Graph API** — Still requires C#/.NET/Windows/Azure. The effort is enormous and the SDK auto-deprecates every 3 months. Not worth it.

### What's Changed Since Last Research (2026-03-25)

| Topic | Change |
|-------|--------|
| Bot detection | No updates — still on track for May 2026 |
| Explicit consent | NEW: MC1163766 for 1:1 calls (not meetings) |
| Graph API | Minor additions (webhooks, language tag) — still post-meeting only |
| Streaming ASR | Deepgram Nova-3 benchmarks now public: 5.26% WER. AssemblyAI U3 Pro: 8.14% WER, 150ms P50 |
| Open-source ASR | Canary Qwen 2.5B (5.63% WER), Parakeet TDT (streaming, >2000x RTF) now top choices |
| SimulStreaming | Confirmed SOTA 2025, 5x faster than WhisperStreaming, integrated in WhisperLiveKit |
| Caption attribution | Approach validated — Recall.ai uses identical technique |
| pyannote | 4.0 released with community-1 model; commercial offering has real-time as premium |
| DOM selectors | No evidence of changes |
| WebRTC | VDI deprecation only — browser client unaffected |

---

## Sources

### Teams Platform
- [Office365 IT Pros: Third-Party Recording Bots](https://office365itpros.com/2026/03/16/third-party-recording-bots/)
- [UC Today: Teams Bot Scrutiny Update](https://www.uctoday.com/security-compliance-risk/microsoft-teams-rolling-out-update-to-boost-it-scrutiny-of-meeting-bots/)
- [MWPro: Explicit Consent MC1163766](https://mwpro.co.uk/blog/2026/03/20/updated-new-policy-setting-to-require-explicit-consent-for-recording-and-transcription-in-teams-11-calls-mc1163766-4/)
- [Microsoft TechCommunity: Teams Virtualization](https://techcommunity.microsoft.com/blog/microsoftteamsblog/the-next-chapter-of-microsoft-teams-in-virtualized-environments/4498259)
- [Microsoft Learn: Compliance Recording](https://learn.microsoft.com/en-us/microsoftteams/teams-recording-compliance)
- [Microsoft Learn: Meeting Transcripts](https://learn.microsoft.com/en-us/microsoftteams/platform/graph-api/meeting-transcripts/overview-transcripts)

### ASR & Diarization
- [AssemblyAI: Best APIs for Real-Time ASR 2026](https://www.assemblyai.com/blog/best-api-models-for-real-time-speech-recognition-and-transcription)
- [Deepgram: Best STT APIs 2026](https://deepgram.com/learn/best-speech-to-text-apis-2026)
- [Northflank: Best Open-Source STT 2026](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks)
- [GitHub: SimulStreaming](https://github.com/ufal/SimulStreaming)
- [GitHub: WhisperLiveKit](https://github.com/QuentinFuxa/WhisperLiveKit)
- [pyannote.ai](https://www.pyannote.ai/)

### Competitors
- [Skribby: Meeting Bot API Comparison 2026](https://skribby.io/blog/meeting-bot-api-comparison-2026)
- [Recall.ai: Desktop Recording SDK](https://www.recall.ai/product/desktop-recording-sdk)
- [Google Meet Media API](https://developers.google.com/workspace/meet/media-api/guides/overview)
