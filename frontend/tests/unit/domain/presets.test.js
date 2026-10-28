import { describe, expect, it } from 'vitest';
import { PRESETS, basicWardrobe, presetDesign } from '../../../src/domain/presets.js';
import { validateDesign } from '../../../src/domain/validation.js';
import { loadCatalog, loadDesign } from './helpers.js';

const catalog = loadCatalog();
const TEMPLATES = ['kids', 'sliding', 'minimal'];

describe('starting templates', () => {
  it.each(TEMPLATES)('%s passes validateDesign and matches the shared fixture', (id) => {
    const design = presetDesign(id, catalog);
    expect(validateDesign(design, catalog)).toEqual([]);
    expect(design).toEqual(loadDesign(`preset_${id}`));
  });

  it.each(TEMPLATES)('%s ops are frozen', (id) => {
    expect(Object.isFrozen(PRESETS[id])).toBe(true);
    expect(Object.isFrozen(PRESETS[id][0])).toBe(true);
  });

  it('basic is the basic wardrobe', () => {
    expect(presetDesign('basic', catalog)).toEqual(basicWardrobe(catalog));
  });

  it('keeps the advertised sizes and doors', () => {
    const kids = presetDesign('kids', catalog);
    expect(kids.dimensions.width).toBe(1500);
    expect(kids.doors.type).toBe('hinged');
    const sliding = presetDesign('sliding', catalog);
    expect([sliding.doors.type, sliding.doors.items.length]).toEqual(['sliding', 2]);
    expect(presetDesign('minimal', catalog).compartments).toHaveLength(2);
  });

  it('throws on an unknown template, including inherited keys', () => {
    expect(() => presetDesign('castle', catalog)).toThrow('unknown template');
    expect(() => presetDesign('toString', catalog)).toThrow('unknown template');
  });
});
