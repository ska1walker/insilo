/**
 * Audio-capture defaults tuned for ASR (Whisper), not VoIP.
 *
 * Chrome's `getUserMedia({ audio: true })` defaults enable a DSP chain
 * meant for Zoom/Teams calls:
 *   - Auto-Gain-Control compresses speech dynamics + amplifies pause noise
 *   - Noise Suppression cuts fricatives (s, sch, f, h) the model treats as
 *     noise — the main cause of "Wörter fehlen" in Whisper output
 *   - Echo Cancellation is harmless and useful in echoey rooms
 *
 * Whisper has its own VAD and is robust to background noise, so the right
 * posture for ASR is: keep EC, disable AGC + NS. Channel-count and sample
 * rate are pinned explicitly so a flaky browser default cannot surprise us.
 *
 * MediaRecorder's default Opus bitrate is often ~32 kbps for voice — fine
 * technically, but produces tiny files that "look broken" and leave no
 * headroom when DSP has already shaved phonemes. 128 kbps Opus is
 * transparent for speech (~1 MB/min, still small in absolute terms).
 */

export const ASR_AUDIO_CONSTRAINTS: MediaTrackConstraints = {
  channelCount: 1,
  sampleRate: 48000,
  echoCancellation: true,
  noiseSuppression: false,
  autoGainControl: false,
};

export const ASR_RECORDER_OPTIONS: Pick<MediaRecorderOptions, "audioBitsPerSecond"> = {
  audioBitsPerSecond: 128_000,
};
