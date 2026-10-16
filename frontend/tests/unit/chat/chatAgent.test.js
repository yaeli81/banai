import { describe, expect, it, vi } from 'vitest';
import {
  agentHistory, AGENT_ERROR_MESSAGE, createChatModel, MAX_HISTORY,
} from '../../../src/chat/chatModel.js';
import { ApiError } from '../../../src/api/client.js';

const serverProposal = (baseRevision = 1) => ({
  proposalId: 'prop_1',
  baseRevision,
  baseHash: 'h',
  ops: [{ op: 'update_dimensions', width: 2400 }],
  summary: 'Wider',
  changes: [{ title: 'Dimensions', detail: 'Width 200 cm → 240 cm' }],
  signature: 's',
});

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

describe('chat model with an agent', () => {
  it('is busy while the agent thinks, then shows the reply and the proposal', async () => {
    const pending = deferred();
    const agent = vi.fn(() => pending.promise);
    const model = createChatModel({ getRevision: () => 1, agent });
    const { ok, done } = model.send('make it 240 cm wide');
    expect(ok).toBe(true);
    expect(model.isBusy()).toBe(true);
    expect(agent).toHaveBeenCalledWith([{ role: 'user', content: 'make it 240 cm wide' }]);

    pending.resolve({ reply: 'Wider', proposal: serverProposal() });
    await done;
    expect(model.isBusy()).toBe(false);
    expect(model.getMessages().map((m) => [m.role, m.text])).toEqual([['user', 'make it 240 cm wide'], ['assistant', 'Wider']]);
    expect(model.getProposal()).toMatchObject({ id: 'prop_1', signature: 's', ops: serverProposal().ops });
    expect(model.getProposalStatus()).toBe('pending');
  });

  it('rejects a second message while busy', async () => {
    const pending = deferred();
    const model = createChatModel({ getRevision: () => 1, agent: () => pending.promise });
    const first = model.send('one');
    expect(model.send('two')).toEqual({ ok: false, reason: 'busy' });
    pending.resolve({ reply: 'ok', proposal: null });
    await first.done;
    expect(model.getMessages()).toHaveLength(2);
  });

  it('a new message replaces an earlier proposal', async () => {
    const replies = [{ reply: 'a', proposal: serverProposal() }, { reply: 'Which side?', proposal: null }];
    const model = createChatModel({ getRevision: () => 1, agent: async () => replies.shift() });
    await model.send('wider').done;
    expect(model.getProposal()).not.toBeNull();
    await model.send('and a shelf').done;
    expect(model.getProposal()).toBeNull();
  });

  it('sends only customer and assistant turns as history, never local notes', async () => {
    const agent = vi.fn(async () => ({ reply: 'Sure', proposal: serverProposal() }));
    const model = createChatModel({ getRevision: () => 1, agent });
    await model.send('wider').done;
    model.cancelProposal();
    await model.send('again').done;
    expect(agent.mock.calls[1][0]).toEqual([
      { role: 'user', content: 'wider' }, { role: 'assistant', content: 'Sure' }, { role: 'user', content: 'again' },
    ]);
  });

  it('keeps the history within the backend limit', () => {
    const messages = Array.from({ length: 30 }, (_, i) => ({ role: i % 2 ? 'assistant' : 'user', text: `m${i}` }));
    const history = agentHistory(messages);
    expect(history).toHaveLength(MAX_HISTORY);
    expect(history.at(-1)).toEqual({ role: 'assistant', content: 'm29' });
  });

  it('shows the server message for API errors and a generic one otherwise', async () => {
    const failing = [new ApiError('Too many messages.', { status: 429, code: 'RATE_LIMITED' }), new Error('boom: internals')];
    const model = createChatModel({ getRevision: () => 1, agent: async () => { throw failing.shift(); } });
    await model.send('one').done;
    await model.send('two').done;
    const notes = model.getMessages().filter((m) => m.role === 'system').map((m) => m.text);
    expect(notes).toEqual(['Too many messages.', AGENT_ERROR_MESSAGE]);
    expect(model.isBusy()).toBe(false);
    expect(model.getProposal()).toBeNull();
  });

  it('cannot cancel while a confirm is in progress', async () => {
    const model = createChatModel({ getRevision: () => 1, agent: async () => ({ reply: 'x', proposal: serverProposal() }) });
    await model.send('wider').done;
    model.setBusy(true);
    expect(model.cancelProposal()).toBe(false);
    model.setBusy(false);
    expect(model.cancelProposal()).toBe(true);
  });

  it('reports whether an agent is connected', () => {
    expect(createChatModel({ getRevision: () => 1 }).isConnected()).toBe(false);
    expect(createChatModel({ getRevision: () => 1, agent: async () => ({}) }).isConnected()).toBe(true);
  });
});
