// The three ways to start (spec section 6). All of them land in the same editor and data model.
export const ENTRY_POINTS = Object.freeze([
  Object.freeze({
    id: 'guided',
    icon: 'chat',
    title: 'Guide me',
    description: 'Answer a few questions and the AI designer will propose a wardrobe for you to confirm.',
    action: 'Start guided flow',
    focusesChat: true, // placeholder text per language: chat/i18n.js composerHints.guided
  }),
  Object.freeze({
    id: 'freeText',
    icon: 'edit',
    title: 'Describe it',
    description: 'Type your wardrobe in your own words. The AI designer turns it into a proposal you approve.',
    action: 'Enter description',
    focusesChat: true, // composerHints.freeText
  }),
  Object.freeze({
    id: 'basic',
    icon: 'wardrobe',
    title: 'Start from a basic wardrobe',
    description: 'Begin with a standard 200 × 240 × 60 cm wardrobe, then edit it by hand or with the AI.',
    action: 'Open basic wardrobe',
    focusesChat: false,
  }),
]);

// Ready-made starting templates (src/domain/presets.js). They open the editor like the basic wardrobe.
export const PRESET_ENTRIES = Object.freeze([
  Object.freeze({ id: 'preset-kids', presetId: 'kids', title: "Kids' wardrobe", size: '150 × 180 × 55 cm', focusesChat: false }),
  Object.freeze({ id: 'preset-sliding', presetId: 'sliding', title: 'Double wardrobe, sliding doors', size: '240 × 240 × 65 cm', focusesChat: false }),
  Object.freeze({ id: 'preset-minimal', presetId: 'minimal', title: 'Minimalist wardrobe', size: '120 × 220 × 60 cm', focusesChat: false }),
]);

export const getEntryPoint = (id) => ENTRY_POINTS.find((entry) => entry.id === id) ?? null;
