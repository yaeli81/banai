// Pure chat view-model (no DOM). With an `agent`, a sent message goes to the backend agent and the
// reply (plus an optional signed proposal) comes back; without one, the customer gets an honest
// "not connected" reply. The model never applies anything to the design itself.
//
// A proposal is { id, baseRevision, summary, changes: [{ title, detail }], ... } (the server's signed
// fields travel along untouched). It is kept apart from the committed design and is only ever
// "pending" or "stale" (the design changed after it was made).

export const NOT_CONNECTED_MESSAGE =
  "The AI agent isn't connected yet. You can design manually in the Properties panel.";
export const STALE_MESSAGE = 'Design changed. Ask the agent to re-propose.';
export const AGENT_ERROR_MESSAGE = 'The AI designer is unavailable right now. Please try again.';
export const MAX_MESSAGE_LENGTH = 2000;
// The backend accepts at most 20 messages; older turns are dropped from the context first.
export const MAX_HISTORY = 20;

// Starter prompts shown before the first message. Picking one only fills the composer.
export const SUGGESTIONS = Object.freeze([
  '240 cm wide, 260 cm tall, white, three compartments',
  'Tall wardrobe with sliding doors and a hanging rail',
  'Four shelves on the left, hanging in the middle, three drawers on the right',
]);

export function proposalStatus(proposal, currentRevision) {
  if (!proposal) return null;
  return proposal.baseRevision === currentRevision ? 'pending' : 'stale';
}

/** Customer/assistant turns for the agent (local system notes are never sent). */
export function agentHistory(messages) {
  return messages
    .filter((m) => m.role === 'user' || m.role === 'assistant')
    .slice(-MAX_HISTORY)
    .map((m) => ({ role: m.role, content: m.text }));
}

/**
 * @param {object} options
 * @param {() => number} options.getRevision current committed revision
 * @param {((history: {role, content}[]) => Promise<{reply: string, proposal: object|null}>) | null} [options.agent]
 */
export function createChatModel({ getRevision, agent = null }) {
  let nextId = 1;
  let proposal = null;
  let busy = false;
  const messages = [];
  const listeners = new Set();
  const notify = () => listeners.forEach((listener) => listener());
  const push = (role, text) => {
    messages.push(Object.freeze({ id: nextId, role, text }));
    nextId += 1;
  };

  async function askAgent() {
    busy = true;
    proposal = null; // a new turn replaces any earlier proposal
    notify();
    try {
      const result = await agent(agentHistory(messages));
      if (typeof result?.reply === 'string' && result.reply) push('assistant', result.reply);
      // The reply bubble already carries the summary, so the card shows only the change list.
      if (result?.proposal) proposal = { ...result.proposal, id: result.proposal.proposalId, summary: '' };
    } catch (error) {
      push('system', typeof error?.message === 'string' && error.code ? error.message : AGENT_ERROR_MESSAGE);
    } finally {
      busy = false;
      notify();
    }
  }

  return {
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    getMessages: () => [...messages],
    getProposal: () => proposal,
    getProposalStatus: () => proposalStatus(proposal, getRevision()),
    /** True while the agent is thinking or a proposal is being applied. */
    isBusy: () => busy,
    isConnected: () => agent !== null,

    /**
     * A customer message. Returns { ok, done } and never touches the design.
     * `done` resolves when the agent's answer (if any) has arrived.
     */
    send(rawText) {
      if (busy) return { ok: false, reason: 'busy' };
      const text = String(rawText ?? '').trim();
      if (!text) return { ok: false, reason: 'empty' };
      if (text.length > MAX_MESSAGE_LENGTH) return { ok: false, reason: 'too-long' };
      push('user', text);
      if (!agent) {
        push('system', NOT_CONNECTED_MESSAGE);
        notify();
        return { ok: true, done: Promise.resolve() };
      }
      return { ok: true, done: askAgent() };
    },

    /** Set by the agent turn, or by the dev-only demo. */
    setProposal(next) {
      proposal = next;
      notify();
    },

    /** Marks a confirm in progress (the composer and card are disabled meanwhile). */
    setBusy(value) {
      busy = Boolean(value);
      notify();
    },

    /** Cancel never changes the design; it only drops the pending proposal. */
    cancelProposal() {
      if (!proposal || busy) return false;
      proposal = null;
      push('system', 'Proposal cancelled. No changes were made.');
      notify();
      return true;
    },

    /** Called after the host applied (or refused) the proposal. */
    resolveProposal(message) {
      proposal = null;
      if (message) push('system', message);
      notify();
    },
  };
}
