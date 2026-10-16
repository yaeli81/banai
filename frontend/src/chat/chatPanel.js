// Left column: header, a welcome with starter prompts, the conversation, the proposal card and
// the composer. This panel never changes the design by itself: a proposal is only applied by the
// host's onConfirm, after the customer presses Confirm.
import { el } from '../editor/fields.js';
import { icon } from '../ui/icons.js';
import { MAX_MESSAGE_LENGTH, SUGGESTIONS } from './chatModel.js';
import { renderProposalCard } from './proposalCard.js';

const HINT = 'Enter to send · Shift+Enter for a new line';
const VOICE_HINTS = Object.freeze({
  idle: 'Enter to send · or tap the mic to speak',
  recording: 'Listening… tap the mic again to stop',
  transcribing: 'Turning your voice into text…',
});
export const VOICE_NOTES = Object.freeze({
  denied: 'Microphone access was blocked. You can allow it in the browser, or type your request.',
  empty: "I didn't catch that. Please try again or type your request.",
  failed: 'Your recording could not be processed. Please try again or type your request.',
});

/**
 * @param {object} [options.voice] { recorder, transcribe(blob) -> text, stopPlayback() }; omit when unsupported.
 */
export function mountChat(container, { model, onConfirm, voice = null }) {
  container.classList.add('panel--chat');

  const header = el('header', { className: 'chat__header' }, [
    el('span', { className: 'chat__avatar' }, [icon('sparkle', { size: 22 })]),
    el('div', { className: 'chat__heading' }, [
      el('h2', { className: 'chat__title', text: 'AI Designer' }),
      el('p', { className: 'chat__subtitle', text: 'Design assistant' }),
    ]),
    model.isConnected()
      ? el('span', { className: 'chat__status chat__status--online', text: 'Online', attrs: { title: 'Proposals are applied only after you confirm them.' } })
      : el('span', { className: 'chat__status', text: 'Offline', attrs: { title: 'The AI agent is not connected.' } }),
  ]);

  const input = el('textarea', { className: 'chat__input', attrs: { rows: '2', maxlength: String(MAX_MESSAGE_LENGTH), placeholder: 'Describe your wardrobe…', 'aria-label': 'Message to the AI designer', dir: 'auto' } });
  input.dataset.testid = 'chat-input';
  const sendButton = el('button', { className: 'icon-btn icon-btn--filled chat__send', attrs: { type: 'submit', 'aria-label': 'Send message' } }, [icon('send')]);
  sendButton.dataset.testid = 'chat-send';
  const micButton = el('button', { className: 'icon-btn chat__mic', attrs: { type: 'button', 'aria-label': 'Speak your request' } }, [icon('mic')]);
  micButton.dataset.testid = 'chat-mic';
  const composer = el('form', { className: 'chat__composer' }, voice ? [input, micButton, sendButton] : [input, sendButton]);
  const hint = el('p', { className: 'chat__hint', text: voice ? VOICE_HINTS.idle : HINT });

  // Voice: record one utterance, transcribe it, then send the text like a typed message.
  let micState = 'idle';
  const setMic = (state) => {
    micState = state;
    micButton.replaceChildren(icon(state === 'recording' ? 'stop' : 'mic'));
    micButton.classList.toggle('chat__mic--recording', state === 'recording');
    micButton.setAttribute('aria-label', state === 'recording' ? 'Stop recording' : 'Speak your request');
    micButton.setAttribute('aria-pressed', String(state === 'recording'));
    micButton.disabled = state === 'transcribing' || (state === 'idle' && model.isBusy());
    hint.textContent = VOICE_HINTS[state];
  };
  async function recordAndSend() {
    voice.stopPlayback();
    let blob;
    try {
      const recording = voice.recorder.start();
      setMic('recording');
      blob = await recording;
    } catch {
      setMic('idle');
      model.note(VOICE_NOTES.denied);
      return;
    }
    setMic('transcribing');
    try {
      const text = (await voice.transcribe(blob)).trim();
      setMic('idle');
      if (!text) model.note(VOICE_NOTES.empty);
      else if (!model.send(text, { spoken: true }).ok) model.note(VOICE_NOTES.failed);
    } catch {
      setMic('idle');
      model.note(VOICE_NOTES.failed);
    }
  }
  micButton.addEventListener('click', () => {
    if (micState === 'recording') voice.recorder.stop();
    else if (micState === 'idle' && !model.isBusy()) recordAndSend();
  });

  const chips = SUGGESTIONS.map((text) => {
    const chip = el('button', { className: 'suggestion', attrs: { type: 'button' } }, [icon('sparkle', { size: 16 }), el('span', { text })]);
    chip.dataset.testid = 'suggestion';
    chip.addEventListener('click', () => {
      input.value = text; // only fills the composer: nothing is sent until the customer presses send
      input.focus();
    });
    return chip;
  });
  const welcome = el('section', { className: 'welcome', attrs: { 'aria-label': 'Get started' } }, [
    el('h3', { className: 'welcome__title', text: 'What shall we design today?' }),
    el('p', { className: 'welcome__text', text: "Describe your wardrobe in your own words. I'll turn it into a proposal that you confirm before anything changes." }),
    el('div', { className: 'welcome__chips' }, chips),
  ]);
  welcome.dataset.testid = 'chat-welcome';

  const list = el('div', { className: 'chat__messages', attrs: { role: 'log', 'aria-live': 'polite', 'aria-label': 'Conversation' } });
  list.dataset.testid = 'chat-messages';
  const thinking = el('div', { className: 'chat__thinking', attrs: { role: 'status', 'aria-label': 'The designer is thinking' } },
    [el('span', { className: 'chat__dot' }), el('span', { className: 'chat__dot' }), el('span', { className: 'chat__dot' })]);
  thinking.dataset.testid = 'chat-thinking';
  const proposalSlot = el('div', { className: 'chat__proposal' });

  const submit = () => {
    if (model.send(input.value).ok) input.value = '';
  };
  composer.addEventListener('submit', (event) => {
    event.preventDefault();
    submit();
  });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  });

  let renderedCount = 0;
  let renderedProposalKey = '';
  function render() {
    const messages = model.getMessages();
    welcome.hidden = messages.length > 0 || model.getProposal() !== null;
    list.hidden = messages.length === 0;
    // Only newly added bubbles are created (and animate in); existing ones stay untouched.
    if (messages.length < renderedCount) {
      list.replaceChildren();
      renderedCount = 0;
    }
    messages.slice(renderedCount).forEach((message) => {
      const bubble = el('div', { className: `chat__bubble chat__bubble--${message.role}` });
      if (message.role === 'system') bubble.append(icon('info', { size: 16 }));
      bubble.append(el('span', { text: message.text, attrs: { dir: 'auto' } }));
      list.append(bubble);
    });
    renderedCount = messages.length;
    const busy = model.isBusy();
    thinking.hidden = !busy || model.getProposal() !== null; // a confirm in progress shows on the card
    sendButton.disabled = busy;
    if (voice && micState === 'idle') micButton.disabled = busy;
    list.scrollTop = list.scrollHeight;

    // Re-render the card only when the proposal, its status or the busy flag changed (keeps its entrance animation calm).
    const proposal = model.getProposal();
    const status = model.getProposalStatus();
    const key = proposal ? `${proposal.id}:${status}:${busy}` : '';
    if (key === renderedProposalKey) return;
    renderedProposalKey = key;
    proposalSlot.replaceChildren();
    if (proposal) {
      proposalSlot.append(renderProposalCard(proposal, status, {
        busy,
        onConfirm,
        onCancel: () => model.cancelProposal(),
      }));
    }
  }

  container.replaceChildren(header, el('div', { className: 'chat__body' }, [welcome, list, thinking, proposalSlot]), el('div', { className: 'chat__footer' }, [composer, hint]));
  model.subscribe(render);
  render();

  return {
    focus: (placeholder) => {
      if (placeholder) input.placeholder = placeholder;
      input.focus();
    },
    /** Re-render, e.g. after the design revision changed (a pending proposal may now be stale). */
    refresh: render,
  };
}
