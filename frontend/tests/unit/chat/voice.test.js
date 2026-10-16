import { describe, expect, it, vi } from 'vitest';
import { createPlayer, createRecorder, voiceSupported } from '../../../src/chat/voice.js';
import { ApiError, downloadCarpenterPdf, speakText, transcribeAudio } from '../../../src/api/client.js';
import { createChatModel } from '../../../src/chat/chatModel.js';

function fakeMedia({ deny = false, supported = ['audio/webm;codecs=opus'] } = {}) {
  const tracks = [{ stop: vi.fn() }];
  const mediaDevices = {
    getUserMedia: vi.fn(async () => {
      if (deny) throw new DOMException('denied', 'NotAllowedError');
      return { getTracks: () => tracks };
    }),
  };
  class FakeRecorder {
    static isTypeSupported = (type) => supported.includes(type);
    constructor(stream, options) { this.stream = stream; this.mimeType = options?.mimeType ?? ''; this.state = 'inactive'; FakeRecorder.last = this; }
    start() { this.state = 'recording'; }
    stop() {
      this.state = 'inactive';
      this.ondataavailable({ data: new Blob(['abc'], { type: this.mimeType }) });
      this.onstop();
    }
  }
  return { mediaDevices, FakeRecorder, tracks };
}

describe('recorder', () => {
  it('records until stop, returns a typed Blob and releases the microphone', async () => {
    const { mediaDevices, FakeRecorder, tracks } = fakeMedia();
    const states = [];
    const recorder = createRecorder({ mediaDevices, MediaRecorderImpl: FakeRecorder, onState: (s) => states.push(s) });
    const done = recorder.start();
    await vi.waitFor(() => expect(recorder.isRecording()).toBe(true));
    recorder.stop();
    const blob = await done;
    expect(blob.type).toBe('audio/webm;codecs=opus');
    expect(blob.size).toBe(3);
    expect(tracks[0].stop).toHaveBeenCalled();
    expect(states).toEqual(['recording', 'idle']);
    expect(recorder.isRecording()).toBe(false);
  });

  it('stops by itself after the time limit', async () => {
    vi.useFakeTimers();
    const { mediaDevices, FakeRecorder } = fakeMedia();
    const recorder = createRecorder({ mediaDevices, MediaRecorderImpl: FakeRecorder, maxMs: 1000 });
    const done = recorder.start();
    await vi.waitFor(() => expect(recorder.isRecording()).toBe(true));
    vi.advanceTimersByTime(1000);
    await expect(done).resolves.toBeInstanceOf(Blob);
    vi.useRealTimers();
  });

  it('falls back to audio/mp4 (Safari) and rejects when permission is denied', async () => {
    const safari = fakeMedia({ supported: ['audio/mp4'] });
    const recorder = createRecorder({ mediaDevices: safari.mediaDevices, MediaRecorderImpl: safari.FakeRecorder });
    const done = recorder.start();
    await vi.waitFor(() => expect(recorder.isRecording()).toBe(true));
    expect(safari.FakeRecorder.last.mimeType).toBe('audio/mp4');
    recorder.stop();
    await done;

    const denied = fakeMedia({ deny: true });
    const blocked = createRecorder({ mediaDevices: denied.mediaDevices, MediaRecorderImpl: denied.FakeRecorder });
    await expect(blocked.start()).rejects.toThrow('denied');
    expect(blocked.isRecording()).toBe(false);
  });

  it('detects support', () => {
    expect(voiceSupported({})).toBe(false);
    expect(voiceSupported({ navigator: { mediaDevices: { getUserMedia() {} } } })).toBe(false);
    expect(voiceSupported({ navigator: { mediaDevices: { getUserMedia() {} } }, MediaRecorder: class {} })).toBe(true);
  });
});

describe('player', () => {
  const setup = () => {
    const played = [];
    class FakeAudio {
      constructor(url) { this.url = url; this.pause = vi.fn(); played.push(this); }
      play() { return Promise.resolve(); }
    }
    const urls = { createObjectURL: vi.fn((b) => `blob:${b.size}`), revokeObjectURL: vi.fn() };
    return { player: createPlayer({ AudioImpl: FakeAudio, urls }), played, urls };
  };

  it('plays one reply at a time and cleans up the object URL', async () => {
    const { player, played, urls } = setup();
    await player.play(new Blob(['a']));
    await player.play(new Blob(['bb']));
    expect(played[0].pause).toHaveBeenCalled();
    expect(urls.revokeObjectURL).toHaveBeenCalledWith('blob:1');
    player.stop();
    expect(urls.revokeObjectURL).toHaveBeenCalledWith('blob:2');
  });

  it('swallows a refused autoplay', async () => {
    const urls = { createObjectURL: () => 'blob:x', revokeObjectURL: vi.fn() };
    class Refused { pause() {} play() { return Promise.reject(new Error('NotAllowedError')); } }
    await expect(createPlayer({ AudioImpl: Refused, urls }).play(new Blob(['a']))).resolves.toBeUndefined();
    expect(urls.revokeObjectURL).toHaveBeenCalled();
  });
});

describe('voice api client', () => {
  it('posts the raw recording with its base content type and returns the text', async () => {
    const fetchImpl = vi.fn(async () => ({ ok: true, json: async () => ({ success: true, data: { text: 'wider' } }) }));
    const blob = new Blob(['x'], { type: 'audio/webm;codecs=opus' });
    await expect(transcribeAudio(blob, fetchImpl)).resolves.toBe('wider');
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/voice/transcribe');
    expect(init.headers['Content-Type']).toBe('audio/webm');
    expect(init.body).toBe(blob);
  });

  it('returns speech audio as a Blob and surfaces server errors', async () => {
    const audio = new Blob(['mp3'], { type: 'audio/mpeg' });
    const ok = vi.fn(async () => ({ ok: true, blob: async () => audio }));
    await expect(speakText('Hello', ok)).resolves.toBe(audio);
    expect(JSON.parse(ok.mock.calls[0][1].body)).toEqual({ text: 'Hello' });

    const limited = vi.fn(async () => ({ ok: false, status: 429, json: async () => ({ success: false, error: { code: 'RATE_LIMITED', message: 'Too many requests.' } }) }));
    const error = await transcribeAudio(new Blob(['x']), limited).catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 429, code: 'RATE_LIMITED' });
  });
});

describe('chat model with voice', () => {
  it('speaks the reply only for a spoken turn, and a speech failure never breaks the chat', async () => {
    const speak = vi.fn(async () => { throw new Error('tts down'); });
    const model = createChatModel({ getRevision: () => 1, agent: async () => ({ reply: 'I suggest 240 cm.', proposal: null }), speak });
    await model.send('typed message').done;
    expect(speak).not.toHaveBeenCalled();
    await model.send('spoken message', { spoken: true }).done;
    await vi.waitFor(() => expect(speak).toHaveBeenCalledWith('I suggest 240 cm.'));
    expect(model.getMessages().map((m) => m.role)).toEqual(['user', 'assistant', 'user', 'assistant']);
  });

  it('adds local notes that are never sent to the agent', async () => {
    const agent = vi.fn(async () => ({ reply: 'ok', proposal: null }));
    const model = createChatModel({ getRevision: () => 1, agent });
    model.note("I didn't catch that.");
    await model.send('hello').done;
    expect(agent.mock.calls[0][0]).toEqual([{ role: 'user', content: 'hello' }]);
  });
});

describe('carpenter pdf client', () => {
  it('posts the design with both images and returns the PDF blob', async () => {
    const pdf = new Blob(['%PDF-1.4'], { type: 'application/pdf' });
    const fetchImpl = vi.fn(async () => ({ ok: true, blob: async () => pdf }));
    const payload = { design: { a: 1 }, images: { closed: 'data:image/png;base64,AA', interior: 'data:image/png;base64,BB' } };
    await expect(downloadCarpenterPdf(payload, fetchImpl)).resolves.toBe(pdf);
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/carpenter/pdf');
    expect(JSON.parse(init.body)).toEqual(payload);
  });

  it('surfaces the server error code', async () => {
    const fetchImpl = vi.fn(async () => ({ ok: false, status: 422, json: async () => ({ success: false, error: { code: 'INVALID_IMAGE', message: 'The 3D images could not be read.' } }) }));
    await expect(downloadCarpenterPdf({ design: {}, images: {} }, fetchImpl)).rejects.toMatchObject({ code: 'INVALID_IMAGE', status: 422 });
  });
});
