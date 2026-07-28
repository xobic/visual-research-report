# Editorial longform contract

Use this contract when the user supplies a tall research-page reference or asks for a McKinsey/GS-like editorial report rather than an application dashboard.

## Measure the reference first

Record the source asset, pixel dimensions, background, type hierarchy, prose width, chart width, section spacing, rules, source-line treatment, and any recurring blue/red semantics. Separate observed traits from inferred implementation choices. Do not copy logos, proprietary artwork, or unsupported claims.

The bundled preset fixes three nested measures:

- page: 1440px maximum;
- chart plate: 1120px maximum;
- prose: 720px maximum.

Use a white paper surface, navy primary ink, cobalt emphasis, semantic red, restrained rules, serif display headings, and sans-serif metadata. Prefer whitespace and alignment over thick cards, shadows, or a dark interface shell.

## Cover and directory

The cover still uses the same theme atom across recursive, exploded, blueprint, and impact views. Keep the visual area editorial and object-led. Place the directory after the cover as a flat band; it is not sticky. If Figma cannot be reached, continue with supplied artwork, image generation, or the schematic fallback.

## Charts and evidence

Chart plates may exceed the prose width but stay inside the 1120px measure. Every title has subtitle, source line, and optional analyst note. Every visible number maps to a fact and opens the same evidence drawer. Wide scorecards use a labeled internal scroller on narrow screens.

## Print

Use A4 print CSS with one-page cover intent. Hide skip links, cover tabs, directory chrome, scrims, and drawers. Keep every scorecard column visible by reducing type/padding in print; never crop columns. Avoid page breaks inside chart plates when practical.

## Visual QA

Capture desktop, tablet, and mobile viewport screenshots plus key anchor sections; full-page browser stitching can duplicate sticky elements or repeat content. For reference-led work create `design-qa.md` with the reference and implementation shown together or linked side-by-side. Compare hierarchy, density, alignment, color, typography, and chart anatomy. Geometry checks are necessary but cannot establish visual parity by themselves.
