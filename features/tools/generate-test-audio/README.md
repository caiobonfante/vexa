# Generate Test Audio
Confidence: 40 — script exists but TTS service not port-mapped. Untested since move.
Command: `cd features/realtime-transcription && bash scripts/generate-test-audio.sh`
Output: WAV files + .txt ground truth in data/raw/synthetic/audio/
  - short-sentence.wav, medium-paragraph.wav, long-monologue.wav, long-dialogue.wav
Needs:
  - TTS service running and accessible at localhost:8002
  - TTS container exists (vexa-restore-tts-service-1) but port 8002 is NOT mapped to host
  - Fix: either `docker port` the TTS container, or use gTTS (pip package, installed) as alternative
Alternative: `python3 -c "from gtts import gTTS; tts = gTTS('your text here'); tts.save('output.mp3')"` then convert to 16kHz WAV with `ffmpeg -i output.mp3 -ar 16000 -ac 1 -f wav output.wav`
Dead ends: piper TTS installed but broken (missing pathvalidate dependency).
