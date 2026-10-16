# Carpenter PDF

The **Carpenter PDF** button in the top bar downloads a dimensioned spec sheet of the committed design for the carpenter.
It's a design document, not a manufacturing drawing.

## Flow
1. The browser renders two still images of the committed design off-screen with `viewer.snapshot()`: doors closed, and the
   interior. The live view, selection and toggles are untouched, and a pending AI proposal is not included.
2. `POST /api/carpenter/pdf {design, images: {closed, interior}}`.
   - The server validates the design (`apply_ops(design, [], catalog)`).
   - Images must be PNG data URLs, at most 3 MB and 4096 px each, verified with Pillow.
   - The route body cap is 9 MB, and the chat rate limit applies.
3. The response is an A4 PDF (`attachment; filename="banai-wardrobe-YYYYMMDD.pdf"`, `no-store`). Nothing is stored.

## Contents
1. **Cover**
   - title, date, and design reference (the first 8 characters of the design hash)
   - 3D view with the doors
   - key dimensions: overall W×H×D, panel thickness, interior W×H, compartment widths, partitions, doors, item counts, finishes
2. **Front elevation (doors removed)**
   - drawn to scale, with dimension lines for the overall width and height, the interior height and each compartment width
   - the y of every item
   - the 3D interior view
3. **Tables:** compartments and items (x-range, width, kind, y, thickness or height, finish override), partitions (left-face x,
   thickness), and doors (what each covers, hinge side, finish).

**Coordinates:** x is measured from the inner face of the left side panel, and y from the top face of the bottom panel
(`domain/geometry.py`). All lengths are integer millimetres.

## What it deliberately does not contain
Back panel, door thickness and gaps, joinery, edge banding, hinges, runners, handles and other hardware. None of these are
part of the design model; the 3D view uses visual-only values for them (`viewer/units.js` `VISUAL`). They're the
carpenter's choice, and the PDF says so.

## Rules
- Every page footer reads: "Dimensions as designed by the customer, in millimetres. Not a manufacturing drawing. Verify on
  site and against your manufacturing method before cutting."
- The app never claims a design is manufacturable.
- Customer-provided names (custom colours) may be Hebrew or Arabic. They're shaped with `python-bidi` and drawn with the
  bundled DejaVu Sans (`backend/app/carpenter/fonts/`, licence in `DejaVu-LICENSE.txt`).

## Tests
- `backend/tests/test_carpenter.py`: the spec numbers equal the design's; the PDF has 3 pages with every dimension and the
  disclaimer on every page; Hebrew names; image and design validation; body cap.
- `frontend/tests/e2e/ux.spec.js` › "carpenter PDF": download, a 3-page PDF, and the live view unchanged afterwards.
