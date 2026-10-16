// Voice input/output for the chat (no DOM rendering here).
// - The recorder captures one utterance while the mic button is active and returns an audio Blob.
// - The player reads one reply at a time and stops when a new recording starts.
// Browser APIs are injected so this can be tested without a microphone.

export const MAX_RECORDING_MS = 30_000;

// Preferred recording formats, in order. Safari records audio/mp4; the server accepts both.
const MIME_CANDIDATES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];

export function voiceSupported(env = globalThis) {
  return Boolean(env.navigator?.mediaDevices?.getUserMedia && env.MediaRecorder);
}

/**
 * @param {object} [deps]
 * @param {MediaDevices} [deps.mediaDevices]
 * @param {typeof MediaRecorder} [deps.MediaRecorderImpl]
 * @param {number} [deps.maxMs] auto-stop after this long
 * @param {(state: 'idle'|'recording') => void} [deps.onState]
 */
export function createRecorder({
  mediaDevices = globalThis.navigator?.mediaDevices,
  MediaRecorderImpl = globalThis.MediaRecorder,
  maxMs = MAX_RECORDING_MS,
  onState = () => {},
} = {}) {
  let recorder = null;
  let stream = null;
  let timer = null;
  let finish = null;

  const release = () => {
    clearTimeout(timer);
    stream?.getTracks().forEach((track) => track.stop()); // the browser's mic indicator turns off
    recorder = null;
    stream = null;
    onState('idle');
  };

  return {
    isRecording: () => recorder !== null,

    /** Starts recording. Resolves to a Blob when stop() is called (or on auto-stop). */
    async start() {
      if (recorder) throw new Error('already recording');
      stream = await mediaDevices.getUserMedia({ audio: true }); // rejects when permission is denied
      const mimeType = MIME_CANDIDATES.find((type) => MediaRecorderImpl.isTypeSupported?.(type));
      recorder = new MediaRecorderImpl(stream, mimeType ? { mimeType } : undefined);
      const chunks = [];
      const done = new Promise((resolve) => { finish = resolve; });
      recorder.ondataavailable = (event) => { if (event.data?.size) chunks.push(event.data); };
      recorder.onstop = () => {
        const type = recorder?.mimeType || mimeType || 'audio/webm';
        release();
        finish(new Blob(chunks, { type }));
      };
      recorder.start();
      onState('recording');
      timer = setTimeout(() => recorder?.state === 'recording' && recorder.stop(), maxMs);
      return done;
    },

    stop() {
      if (recorder?.state === 'recording') recorder.stop();
    },
  };
}

/** Plays one audio Blob at a time; a new play() or stop() cuts the previous one. */
export function createPlayer({ AudioImpl = globalThis.Audio, urls = globalThis.URL } = {}) {
  let current = null;
  const stop = () => {
    if (!current) return;
    current.audio.pause();
    urls.revokeObjectURL(current.url);
    current = null;
  };
  return {
    stop,
    async play(blob) {
      stop();
      const url = urls.createObjectURL(blob);
      const audio = new AudioImpl(url);
      current = { audio, url };
      audio.onended = () => { if (current?.audio === audio) stop(); };
      try {
        await audio.play();
      } catch {
        stop(); // autoplay refused or decode error: the text reply is already on screen
      }
    },
  };
}
