# Institutional research design system

Use the bundled tokens and components as a restrained publication system: paper-like sheet, layered ink, one emphasis blue, semantic red, narrow prose, wider chart plate, rigorous title/subtitle/source anatomy, and analyst annotations. Choose one layout contract; a persistent rail is not mandatory.

## Layout contracts

- `editorial-longform`: reference-led flat paper, 1440px page, 1120px chart plate, 720px prose, white background, navy ink, cobalt emphasis, semantic red, and a non-sticky directory band. Use it for the long Chinese editorial research page shown in a supplied reference.
- `institutional-rail`: dashboard-led layout with a sticky desktop rail and wider interactive cover. Use it only when persistent navigation and KPIs materially help the task.

Read [editorial-longform.md](editorial-longform.md) for reference measurement, print, and comparison rules. Do not combine the two contracts into a hybrid card dashboard.

## Hierarchy and layout

- The cover establishes the theme atom and publication identity.
- Immediately after the cover, place key numbers, contents, and the research contract. The institutional preset uses a sticky desktop rail. The editorial preset uses a flat directory band before the article and never introduces a dark side dashboard.
- Keep prose at its readable measure and allow chart plates to widen independently.
- Every chart includes title, subtitle, source line, and optional analyst note.
- Stable source anchors use `#source-Sxx`.

## Cover system

The four cover tabs show the same real object as recursive system, exploded physical view, engineering blueprint, and impact/unboxing moment. Tabs use `role=tab`, matching tabpanels, roving `tabindex`, ArrowLeft/ArrowRight and Home/End. The active view is never conveyed by color alone. Honor reduced motion.

## Evidence interaction

- KPI tiles, fact chips, chart marks, and table cells open one dark evidence drawer.
- The drawer shows value, basis, date, source links, and any formula, comparison basis, adjustment scope, boundary, or precision.
- While open, the report is inert, focus is trapped inside the drawer, Escape closes it, and focus returns to the originating control.
- Do not create multiple focusable controls for the same fact in a single visual context; use decorative marks plus one labeled control.
- All tap targets are at least 40px, with 44px preferred.

## Language

The renderer ships complete `en-US` and `zh-CN` interface dictionaries and derives the active one from `meta.language`. Report-specific `ui_labels` override dictionary values. Do not hard-code a second language into source labels, navigation, accessibility names, disclosure headings, or drawer fields.

## Responsive rules

- At desktop width, preserve the wide chart plate and the selected layout contract.
- At tablet width, move the rail above the body and keep cover controls reachable.
- At mobile width, wrap long Chinese/English titles, avoid page-level horizontal overflow, maintain touch targets, and let intentionally wide line charts scroll internally to the latest point.
- Dense tables may scroll inside their own labeled region. The document itself may not scroll horizontally. Labels may not overlap or escape their chart plate.

The system should feel authored and analytical, but fidelity to the fact layer takes precedence over visual flourish.
