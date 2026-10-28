// Predefined starting designs. Mirrors BASIC_WARDROBE_OPS / PRESET_OPS / preset_design in
// backend/app/domain/defaults.py (configurable prototype values).

import { applyOps } from './apply.js';
import { deepFreeze } from './util.js';

export const BASIC_WARDROBE_OPS = deepFreeze([
  { op: 'create_wardrobe', width: 2000, height: 2400, depth: 600, compartmentCount: 3,
    compartmentIds: ['cmp_left', 'cmp_middle', 'cmp_right'], partitionIds: ['prt_1', 'prt_2'] },
  { op: 'add_shelf', compartmentId: 'cmp_left', y: 400, id: 'shf_l1' },
  { op: 'add_shelf', compartmentId: 'cmp_left', y: 800, id: 'shf_l2' },
  { op: 'add_shelf', compartmentId: 'cmp_left', y: 1200, id: 'shf_l3' },
  { op: 'add_shelf', compartmentId: 'cmp_left', y: 1600, id: 'shf_l4' },
  { op: 'add_shelf', compartmentId: 'cmp_middle', y: 2000, id: 'shf_m1' },
  { op: 'add_rail', compartmentId: 'cmp_middle', y: 1900, id: 'rail_m1' },
  { op: 'add_shelf', compartmentId: 'cmp_right', y: 800, id: 'shf_r1' },
  { op: 'add_shelf', compartmentId: 'cmp_right', y: 1400, id: 'shf_r2' },
  { op: 'add_drawer', compartmentId: 'cmp_right', y: 0, height: 200, id: 'drw_r1' },
  { op: 'add_drawer', compartmentId: 'cmp_right', y: 200, height: 200, id: 'drw_r2' },
  { op: 'configure_doors', type: 'hinged', ids: ['dr_left', 'dr_middle', 'dr_right'] },
]);

// ASSUMPTION: the templates below are configurable starting points (sizes, layout, colours),
// not business or manufacturing rules.
export const KIDS_WARDROBE_OPS = deepFreeze([
  { op: 'create_wardrobe', width: 1500, height: 1800, depth: 550, compartmentCount: 2,
    compartmentIds: ['cmp_kids_hang', 'cmp_kids_store'], partitionIds: ['prt_kids'] },
  { op: 'add_rail', compartmentId: 'cmp_kids_hang', y: 1100, id: 'rail_kids' }, // within a child's reach
  { op: 'add_shelf', compartmentId: 'cmp_kids_hang', y: 1300, id: 'shf_kids_top' },
  { op: 'add_drawer', compartmentId: 'cmp_kids_store', y: 0, height: 180, id: 'drw_kids1' },
  { op: 'add_drawer', compartmentId: 'cmp_kids_store', y: 180, height: 180, id: 'drw_kids2' },
  { op: 'add_drawer', compartmentId: 'cmp_kids_store', y: 360, height: 180, id: 'drw_kids3' },
  { op: 'add_shelf', compartmentId: 'cmp_kids_store', y: 900, id: 'shf_kids1' },
  { op: 'add_shelf', compartmentId: 'cmp_kids_store', y: 1300, id: 'shf_kids2' },
  { op: 'configure_doors', type: 'hinged', ids: ['dr_kids_left', 'dr_kids_right'] },
  { op: 'set_material', target: 'doors', color: { catalogId: 'sage_green' } },
]);

export const SLIDING_WARDROBE_OPS = deepFreeze([
  { op: 'create_wardrobe', width: 2400, height: 2400, depth: 650, compartmentCount: 2,
    compartmentIds: ['cmp_his', 'cmp_hers'], partitionIds: ['prt_couple'] },
  { op: 'add_rail', compartmentId: 'cmp_his', y: 1900, id: 'rail_his' },
  { op: 'add_shelf', compartmentId: 'cmp_his', y: 2050, id: 'shf_his' },
  { op: 'add_drawer', compartmentId: 'cmp_hers', y: 0, height: 200, id: 'drw_hers1' },
  { op: 'add_drawer', compartmentId: 'cmp_hers', y: 200, height: 200, id: 'drw_hers2' },
  { op: 'add_rail', compartmentId: 'cmp_hers', y: 1900, id: 'rail_hers' },
  { op: 'add_shelf', compartmentId: 'cmp_hers', y: 2050, id: 'shf_hers' },
  { op: 'configure_doors', type: 'sliding', ids: ['dr_slide1', 'dr_slide2'] },
]);

export const MINIMAL_WARDROBE_OPS = deepFreeze([
  { op: 'create_wardrobe', width: 1200, height: 2200, depth: 600, compartmentCount: 2,
    compartmentIds: ['cmp_min_hang', 'cmp_min_shelves'], partitionIds: ['prt_min'] },
  { op: 'add_rail', compartmentId: 'cmp_min_hang', y: 1750, id: 'rail_min' },
  { op: 'add_shelf', compartmentId: 'cmp_min_shelves', y: 500, id: 'shf_min1' },
  { op: 'add_shelf', compartmentId: 'cmp_min_shelves', y: 1000, id: 'shf_min2' },
  { op: 'add_shelf', compartmentId: 'cmp_min_shelves', y: 1500, id: 'shf_min3' },
  { op: 'configure_doors', type: 'hinged', ids: ['dr_min_left', 'dr_min_right'] },
  { op: 'set_material', target: 'doors', color: { catalogId: 'light_grey' } },
]);

/** Every starting template by id. Mirrors PRESET_OPS in backend/app/domain/defaults.py. */
export const PRESETS = Object.freeze({
  basic: BASIC_WARDROBE_OPS,
  kids: KIDS_WARDROBE_OPS,
  sliding: SLIDING_WARDROBE_OPS,
  minimal: MINIMAL_WARDROBE_OPS,
});

/** The predefined starting wardrobe (entry option 3), built through the op protocol. */
export const basicWardrobe = (catalog) => applyOps(null, BASIC_WARDROBE_OPS, catalog);

/** A starting template built through the op protocol. Throws on an unknown id. */
export function presetDesign(id, catalog) {
  if (!Object.hasOwn(PRESETS, id)) throw new Error(`unknown template: ${id}`);
  return applyOps(null, PRESETS[id], catalog);
}
