import { describe, expect, it, vi } from 'vitest';
import {
  ApiError, applyProposal, getCatalog, getDefaultDesign, getHealth, sendChat,
} from '../../src/api/client.js';

const okResponse = (body) => vi.fn().mockResolvedValue({ ok: true, json: async () => body });

describe('api client', () => {
  it('returns the health payload', async () => {
    const fetchImpl = okResponse({ success: true, data: { status: 'ok' } });
    await expect(getHealth(fetchImpl)).resolves.toEqual({ success: true, data: { status: 'ok' } });
    expect(fetchImpl).toHaveBeenCalledWith('http://localhost:8000/api/health');
  });

  it('unwraps the envelope for catalog and default design', async () => {
    await expect(getCatalog(okResponse({ success: true, data: { colors: [] } }))).resolves.toEqual({ colors: [] });
    await expect(getDefaultDesign(okResponse({ success: true, data: { design: {}, revision: 1 } })))
      .resolves.toEqual({ design: {}, revision: 1 });
  });

  it('posts chat and apply requests as JSON and unwraps the envelope', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ success: true, data: { reply: 'hi', proposal: null } }) });
    const payload = { messages: [{ role: 'user', content: 'x' }], design: { a: 1 }, revision: 2 };
    await expect(sendChat(payload, fetchImpl)).resolves.toEqual({ reply: 'hi', proposal: null });
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/chat');
    expect(init.method).toBe('POST');
    expect(init.headers['Content-Type']).toBe('application/json');
    expect(JSON.parse(init.body)).toEqual(payload);

    await applyProposal({ design: {}, revision: 1, proposal: { proposalId: 'p' } }, fetchImpl);
    expect(fetchImpl.mock.calls[1][0]).toBe('http://localhost:8000/api/proposals/apply');
  });

  it('keeps the server error code and message, e.g. 409 STALE', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: false, status: 409, json: async () => ({ success: false, error: { code: 'STALE', message: 'Changed.' } }),
    });
    const error = await applyProposal({}, fetchImpl).catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 409, code: 'STALE', message: 'Changed.' });
  });

  it('turns network failures and non-JSON errors into a generic ApiError', async () => {
    const offline = await sendChat({}, vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))).catch((e) => e);
    expect(offline).toMatchObject({ code: 'NETWORK_ERROR' });
    const html = vi.fn().mockResolvedValue({ ok: false, status: 502, json: async () => { throw new SyntaxError('<html>'); } });
    const proxy = await sendChat({}, html).catch((e) => e);
    expect(proxy).toMatchObject({ status: 502, code: 'HTTP_ERROR' });
    expect(proxy.message).not.toContain('html');
  });

  it('throws on HTTP errors and unsuccessful envelopes', async () => {
    await expect(getCatalog(vi.fn().mockResolvedValue({ ok: false, status: 503 }))).rejects.toThrow('503');
    await expect(getCatalog(okResponse({ success: false, error: 'x' }))).rejects.toThrow('unsuccessful');
  });
});
