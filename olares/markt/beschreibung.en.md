# Kurz
On-premise meeting intelligence — record, transcribe and summarize meetings without sending audio to any cloud

# Beschreibung
Insilo records business meetings, transcribes them locally and turns them into structured minutes — on your own Olares box.

**The promise**
No audio, no transcript and no search index ever leaves the box. Unlike PLAUD, Otter or Fireflies there is no cloud upload, no third-party AI API and no telemetry.

**What it does**
- Record from the browser (PWA), or upload existing audio
- Transcribe locally with faster-whisper (large-v3), speaker diarization via voiceprint matching
- Structured summaries from a template system, produced by the language model you point it at
- Ask questions across the whole meeting archive (RAG over pgvector)
- Outbound integration: webhooks with HMAC signatures, REST API, Markdown export — manual dispatch by default

**Privacy proof, measured**
The navigation carries a live statement of what actually leaves the box, derived from the configured endpoints and the delivered bytes in the audit log — not a promise. Three destinations are possible and each is named: an external language model endpoint, configured webhooks, and the one-time model download on first boot.

**Language model**
Insilo ships with no endpoint configured. Point it at any OpenAI-compatible address under Settings — for example the LiteLLM app on the same box. Until then recording and transcription work and summaries are skipped, and the app says so.

**Designed for**
Law firms, tax consultancies, management consultants and German Mittelstand companies under GDPR, BSI Grundschutz or attorney-client privilege.

**Interface**
German, English, French, Spanish and Italian; formal address in every language. Light and dark mode.

**Resource Usage**
CPU: 4 cores requested, up to 13
RAM: 12 GB requested, up to 24
Disk: 30 GB (audio, Whisper and BGE-M3 models ~3 GB, database share)
GPU: none — Whisper runs on CPU, the language model is external
