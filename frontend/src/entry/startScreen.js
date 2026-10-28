// Start screen: three ways in, one editor. Shown on load as a modal; choosing an option closes it.
import { el } from '../editor/fields.js';
import { icon } from '../ui/icons.js';
import { createLogo } from '../ui/logo.js';
import { ENTRY_POINTS, PRESET_ENTRIES } from './entryPoints.js';

export const START_FOOTNOTE = 'Designs are illustrative previews and are not manufacturing drawings.';

export function mountStartScreen({ onChoose }) {
  const choose = (entry) => {
    dialog.close();
    dialog.remove();
    onChoose(entry);
  };
  const cards = ENTRY_POINTS.map((entry) => {
    const action = el('button', { className: 'btn', attrs: { type: 'button' } }, [
      document.createTextNode(`${entry.action} `),
      icon('arrow', { size: 18 }),
    ]);
    action.dataset.testid = `entry-${entry.id}`;
    const card = el('article', { className: 'entry-card' }, [
      el('span', { className: 'entry-card__icon' }, [icon(entry.icon, { size: 24 })]),
      el('h2', { className: 'entry-card__title', text: entry.title }),
      el('p', { className: 'entry-card__text', text: entry.description }),
      action,
    ]);
    action.addEventListener('click', () => choose(entry));
    return card;
  });
  const presets = PRESET_ENTRIES.map((entry) => {
    const button = el('button', { className: 'preset', attrs: { type: 'button' } }, [
      el('span', { className: 'preset__title', text: entry.title }),
      el('span', { className: 'preset__size', text: entry.size }),
    ]);
    button.dataset.testid = entry.id;
    button.addEventListener('click', () => choose(entry));
    return el('li', {}, [button]);
  });

  const dialog = el('dialog', { className: 'start', attrs: { 'aria-labelledby': 'start-title' } }, [
    el('header', { className: 'start__bar' }, [createLogo({ size: 36 })]),
    el('main', { className: 'start__main' }, [
      el('h1', { className: 'start__title', text: 'Design your wardrobe', attrs: { id: 'start-title' } }),
      el('p', { className: 'start__subtitle', text: 'Choose how you would like to begin. You can switch between the AI designer and manual editing at any time.' }),
      el('div', { className: 'start__cards' }, cards),
      el('section', { className: 'start__presets', attrs: { 'aria-labelledby': 'start-presets-title' } }, [
        el('h2', { className: 'start__presets-title', text: 'Or start from a template', attrs: { id: 'start-presets-title' } }),
        el('ul', { className: 'start__preset-list' }, presets),
      ]),
      el('p', { className: 'start__footnote', text: START_FOOTNOTE }),
      el('a', { className: 'start__footnote', text: 'הצהרת נגישות', attrs: { href: '/accessibility.html', lang: 'he' } }),
    ]),
  ]);
  dialog.dataset.testid = 'start-screen';
  // A choice is required: Esc must not leave the user on a blank workspace.
  dialog.addEventListener('cancel', (event) => event.preventDefault());
  document.body.append(dialog);
  dialog.showModal();
  return dialog;
}
