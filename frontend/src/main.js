import '@fontsource/bricolage-grotesque/600.css';
import '@fontsource/bricolage-grotesque/700.css';
import '@fontsource/bricolage-grotesque/800.css';
import '@fontsource/dm-sans/400.css';
import '@fontsource/dm-sans/500.css';
import '@fontsource/dm-sans/600.css';
import '@fontsource/dm-sans/700.css';
import { applyProposal, getCatalog, getDefaultDesign, sendChat } from './api/client.js';
import { createStore } from './state/store.js';
import { mountPanel } from './editor/panel.js';
import { createViewer } from './viewer/viewer.js';
import { createChatModel } from './chat/chatModel.js';
import { mountChat } from './chat/chatPanel.js';
import { mountStartScreen } from './entry/startScreen.js';
import { createSaveDialog } from './share/saveDialog.js';
import { createRenderDialog } from './render/renderDialog.js';
import { createLogo } from './ui/logo.js';
import { installRipple } from './ui/ripple.js';

function showError(message) {
  const banner = document.getElementById('error-banner');
  banner.textContent = message;
  banner.hidden = false;
}

function bindInteriorToggle(store) {
  const toggle = document.getElementById('toggle-interior');
  toggle.addEventListener('change', () => store.setDoorsVisible(!toggle.checked));
  store.subscribe((state) => { toggle.checked = !state.ui.doorsVisible; });
}

function bindDialogs() {
  const save = createSaveDialog();
  const render = createRenderDialog();
  document.getElementById('open-save').addEventListener('click', save.open);
  document.getElementById('open-render').addEventListener('click', render.open);
}

/**
 * Confirm: the server verifies the signature and that the design is unchanged, then applies the ops.
 * The committed design changes only here, and only with the server's validated result.
 */
async function confirmProposal(store, chatModel, proposal) {
  const { design, revision } = store.getState();
  if (proposal.baseRevision !== revision) return; // stale: the card already disables Confirm
  chatModel.setBusy(true);
  try {
    const result = await applyProposal({ design, revision, proposal });
    const committed = store.commitDesign(result.design, result.revision);
    chatModel.resolveProposal(committed.ok
      ? 'Changes applied to your design.'
      : 'The design changed while applying. Nothing was changed; please ask again.');
  } catch (error) {
    chatModel.resolveProposal(error?.code === 'STALE'
      ? 'The design changed after this proposal was made. Nothing was applied; please ask again.'
      : 'The changes could not be applied. Your design was not changed.');
  } finally {
    chatModel.setBusy(false);
  }
}

async function boot() {
  document.getElementById('topbar-logo').append(createLogo({ size: 34, tagline: 'Wardrobe Designer' }));
  installRipple();
  let catalog;
  let initial;
  try {
    [catalog, initial] = await Promise.all([getCatalog(), getDefaultDesign()]);
  } catch {
    showError('Could not reach the design service. Please check your connection and reload.');
    return;
  }
  // Validates the server data before anything is rendered (throws on invalid data).
  const store = createStore({ design: initial.design, revision: initial.revision, catalog });
  const viewer = createViewer(document.getElementById('viewer'), store);
  bindInteriorToggle(store);
  mountPanel(document.getElementById('properties-content'), store);
  bindDialogs();

  // The agent always sees the latest committed design and revision.
  const agent = (messages) => {
    const { design, revision } = store.getState();
    return sendChat({ messages, design, revision });
  };
  const chatModel = createChatModel({ getRevision: () => store.getState().revision, agent });
  const chat = mountChat(document.getElementById('chat-panel'), {
    model: chatModel,
    onConfirm: (proposal) => confirmProposal(store, chatModel, proposal),
  });
  // A manual edit changes the revision, which may turn a pending proposal stale.
  store.subscribe(() => chat.refresh());

  if (import.meta.env.DEV) {
    window.__banai = Object.freeze({ store, viewer, chat: chatModel });
  }

  mountStartScreen({
    onChoose: (entry) => {
      // All three entry points open the same editor; the chat ones also focus the composer.
      if (entry.id !== 'basic') chat.focus(entry.composerHint);
    },
  });
}

boot().catch(() => {
  showError('The designer could not start. Please reload the page.');
});
