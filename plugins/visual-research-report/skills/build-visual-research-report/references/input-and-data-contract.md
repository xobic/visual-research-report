# Input and data contract

Compile the factual layer before touching presentation code. The minimum input is report prose, structured numbers, source/date metadata for material claims, and one physical theme atom. Missing evidence must remain visibly missing; never repair it by invention.

## Root fields

- `schema`: use `visual-research-report@2` for new work.
- `meta`: `title`, `subtitle`, `kicker`, `publisher`, `as_of`, `language`, and `summary`.
- `evidence_status`: `verified`, `mixed`, or `synthetic`.
- `data_disclosure`: required for `mixed` and `synthetic`; provide `label`, `scope`, and placements such as `top-banner`, `methodology`, and `package-manifest`.
- `presentation`: `preset` is `institutional-rail`, `editorial-longform`, `editorial-scrollspy`, or `editorial-dashboard`; optional `reference_contract` records the supplied reference and measured geometry.
- `ui_labels` (optional): string-to-string overrides for interface copy. The renderer supplies complete `en-US` and `zh-CN` dictionaries, selected from `meta.language`.
- `theme_atom`: `name`, `description`, and exactly four `views` with IDs `recursive`, `exploded`, `blueprint`, and `impact`; `production` declares `image-2`, supplied, or schematic rendering; optional `identity_lock`, `camera_lock`, and `schematic` preserve one physical object across states.
- `sources`: stable `Sxx` source records.
- `facts`: stable `Fxx` quantitative records.
- `kpis`: fact IDs used in the research rail.
- `sections`: narrative blocks and charts.
- `methodology` and `disclosures`: arrays of strings.
- `preset` and `preset_checks` (optional): a domain checklist independent from `presentation.preset`. See the earnings preset reference.

## Source record

Required: `id`, `title`, `publisher`, `date`, and explicit `synthetic`. A source cited by a fact also requires a non-empty `locator`.

Recommended:

```json
{
  "id": "S01",
  "title": "Q2 2026 shareholder letter",
  "publisher": "Example Co.",
  "date": "2026-07-24",
  "url": "https://example.com/filing",
  "source_type": "filing",
  "classification": "primary",
  "locator": {"kind": "document", "page": 8, "section": "Segment results", "table": "Revenue"},
  "accessed_at": "2026-07-27",
  "note": "Values are company-reported unless marked otherwise."
}
```

`classification` is `primary` or `secondary`. `source_type` is a descriptive category such as `filing`, `earnings-release`, `transcript`, `presentation`, `dataset`, `article`, `visual-reference`, or `video`. `locator.kind` is `document`, `dataset`, `web`, `audio-video`, or `visual`; add page/section/table, row/column/version, anchor/access date, timestamp, or asset/region as appropriate.

## Fact record

Required: `id`, `label`, numeric `value`, `display`, `basis`, `date`, `kind`, explicit `synthetic`, and non-empty `source_ids`. `kind` is `reported`, `estimate`, `derived`, `scenario`, `threshold`, or `probability`. Derived facts also require `derived_from` and `formula`.

Use these semantic fields when applicable:

- `formula`: explicit calculation, preferably using fact IDs.
- `comparison_basis`: denominator and window, such as `Q2 2026 vs Q2 2025`.
- `adjustment_scope`: `both-periods`, `current-period-only`, or a precise custom description.
- `boundary`: `point-in-time`, `period`, `percentage-share`, `probability`, `forecast`, or another explicit boundary.
- `precision`: non-negative decimal places. Put prose such as `nearest $0.1bn` in `format_note`.
- `format`: optional machine-verifiable formatting, for example `{ "style": "multiplier", "prefix": "×" }`.

Example:

```json
{
  "id": "F09",
  "label": "Organic revenue growth",
  "value": 12.4,
  "display": "12.4%",
  "unit": "percent",
  "basis": "Constant-currency growth excluding the acquisition in both periods.",
  "date": "2026-Q2",
  "kind": "derived",
  "source_ids": ["S01"],
  "derived_from": ["F07", "F08"],
  "formula": "(F07 / F08 - 1) × 100",
  "comparison_basis": "Q2 2026 vs Q2 2025",
  "adjustment_scope": "both-periods",
  "boundary": "period",
  "precision": 1
}
```

The validator rejects probability facts outside 0–1, `percentage-share` facts outside 0–100, explicitly asymmetric year-over-year adjustments, non-canonical multiplier displays, chart values that drift from their facts, and synthetic facts without synthetic sources/disclosure.

## Narrative and chart references

Narrative blocks are `paragraph`, `quote`, or `callout`. Put cited IDs in `fact_ids` and `source_ids`; quotes require a source. Every chart has stable `id`, `type`, `title`, `subtitle`, `source_ids`, and type-specific `data`.

For `value-stack`, declare `data.encoding` as `absolute` or `share`. Share stacks must sum to `share_total` (default inferred as 1 or 100) within `share_tolerance`. Absolute stacks may contain negative layers and render around a zero axis.

For `line`, series names and optional colors must be unique. Referenced facts must use compatible units unless `data.allow_mixed_units` is explicitly true. Matrix, line, and paired comparisons declare an actual scale. Paired charts with incompatible groups must use `per-pair-actual`, with one explicit scale per pair; they may not share normalized widths.

Every displayed numeric mark must resolve to one fact. Matrix scores, tripwires, balance weights, paired values, derived multipliers, odds, and table cells are never exempt. A decorative shape may omit a fact only when it contains no visible number.

### Scroll-driven history

Use `history-scrolly` when the reader must understand regimes or phases rather than inspect one static trend. Its `data` contains:

- an `actual` scale;
- one or more uniquely named series, each with at least two `{ "label", "value", "fact_id" }` points;
- at least two ordered scenes with unique `id`, `title`, `start_label`, and `end_label` values that resolve to labels in the first series;
- optional scene `body` and `annotation_fact_ids`.

Scenes select a focus window; they do not create new data. Reduced-motion and print output show the complete history while keeping every scene explanation readable.

### Causal-horizon map

Use `causal-horizon-map` when signals move through distinct time horizons with explicit direction, lag, threshold, and evidence strength. Its `data` contains:

- at least two unique horizons `{ "id", "label" }`;
- at least two nodes with unique `id`, `label`, `horizon_id`, `direction` (`up`, `down`, or `mixed`), `confidence` (`low`, `medium`, or `high`), and `signal_fact_id`;
- optional `lag_fact_id` and `threshold_fact_id` rather than untraceable numeric strings;
- a node sparkline with an actual scale and at least two fact-bound points;
- at least one directed edge whose `from` and `to` resolve to different nodes.

The map visualizes an analytical causal hypothesis, not proof of causality. State that limitation in the chart note or methodology.

## Image 2 cover production

Use `theme_atom.production.mode: "image-2"` for generated production artwork. Image 2 generation happens before the offline build; the builder never calls an external image API. Freeze one canonical identity anchor and derive all four states as direct edits of that anchor:

```json
{
  "identity_lock": {
    "object_key": "chip-package-v1",
    "physical_class": "assembled 2.5D semiconductor package",
    "silhouette": "low rectangular substrate with one clipped corner",
    "part_ids": ["substrate", "interposer", "compute", "memory-a", "memory-b"],
    "topology": ["compute and memory on interposer", "interposer on substrate"],
    "materials": ["graphite silicon", "navy memory", "green-black substrate", "copper routing"],
    "fiducials": ["one clipped lower-left corner", "six gold near-edge pads"]
  },
  "camera_lock": {
    "projection": "orthographic-like three-quarter product view",
    "yaw_deg": 35,
    "pitch_deg": 27,
    "roll_deg": 0,
    "focal_length_equiv_mm": 85,
    "object_center": [0.5, 0.51],
    "safe_margin": 0.1
  },
  "production": {
    "mode": "image-2",
    "model": "gpt-image-2",
    "workflow": "canonical-anchor-plus-direct-edits",
    "anchor_asset": "theme-atom/identity-anchor.png",
    "prompt_version": "atom-cover-v1",
    "canvas": {"width": 1448, "height": 1086},
    "master_format": "png",
    "delivery_format": "webp",
    "print_view_id": "recursive",
    "fallback": "schematic-explicit-only"
  }
}
```

Each `image-2` or `provided` view adds `asset`, a required normalized `focal_point`, and generation provenance. `focal_point` may be omitted only in `schematic` mode:

```json
{
  "id": "exploded",
  "label": "Exploded assembly",
  "alt": "The same package separated along its real assembly order.",
  "asset": "theme-atom/exploded.png",
  "focal_point": [0.5, 0.5],
  "generation": {
    "operation": "edit",
    "parent_asset": "theme-atom/identity-anchor.png",
    "prompt_id": "atom-cover-v1/exploded",
    "invariants": ["identity_lock", "camera_lock"],
    "qa_status": "passed",
    "input_asset_sha256": "<sha256>",
    "output_asset_sha256": "<sha256>"
  }
}
```

Image 2 mode is strict. The anchor and four state assets must be distinct, decodable local images inside the report directory. Remote URLs, data URIs, absolute paths and parent-directory traversal are invalid. All five files share one canvas/aspect ratio; every state preserves the declared identity and camera locks. Missing or rejected production imagery is an error, not permission to switch rendering modes. Keep full prompts in a generation sidecar when auditability matters; the data contract may retain stable prompt IDs and hashes.

## Engineering schematic fallback

When Image 2 is unavailable or the user explicitly selects an offline deterministic cover, set `theme_atom.production.mode: "schematic"`. Then `theme_atom.schematic` may define the physical object once and reuse it in every cover state:

```json
{
  "view_box": [100, 100],
  "parts": [
    {"id":"substrate","label":"Substrate","shape":"rect","x":12,"y":62,"width":76,"height":18,"role":"shell"},
    {"id":"die","label":"Compute die","shape":"rect","x":34,"y":32,"width":32,"height":24,"role":"core"}
  ],
  "connections": [{"from":"die","to":"substrate"}]
}
```

Use two to twelve unique parts. Part coordinates are normalized from 0 to 100; `view_box` declares the positive SVG output extent. Shapes are limited to safe `rect` and `circle` primitives. Roles are `shell`, `core`, `interface`, or `detail`. The renderer owns recursive depth, exploded separation, blueprint drawing, and impact motion so authored geometry remains one object rather than four unrelated illustrations.

## Presentation and reference contract

Use `presentation.preset: "editorial-longform"` for a flat research-paper page. Use `editorial-scrollspy` when the same 1440px page, 1120px chart plate, and 720px prose measures need only a sticky segmented chapter track. Use `editorial-dashboard` when each chapter needs a persistent, synchronized evidence rail in addition to the chapter track. Use `institutional-rail` for a conventional persistent KPI/navigation rail.

For `editorial-dashboard`, a section may provide a short `nav_label` plus a fact-only dashboard contract. Values, dates, labels, and sources always come from the referenced facts:

```json
{
  "id": "capacity-system",
  "nav_label": "Capacity",
  "dashboard": {
    "primary_fact_id": "F02",
    "trend_fact_ids": ["F01", "F05", "F02"],
    "metric_fact_ids": ["F06", "F08", "F09", "F10"],
    "scenario_fact_ids": ["F03", "F21", "F22"]
  }
}
```

`primary_fact_id` is required when `dashboard` exists. `metric_fact_ids` contains two to four unique facts. Optional `trend_fact_ids` contains two to twelve ordered facts sharing one unit. Optional `scenario_fact_ids` contains one to three probability facts. If the entire `dashboard` object is absent, the renderer falls back deterministically to section facts and root KPIs; explicit configuration is preferred for production work.

If the user supplies a screenshot or brand target, record it without turning pixel dimensions into arbitrary design knobs:

```json
{
  "presentation": {
    "preset": "editorial-longform",
    "reference_contract": {
      "asset": "reference.png",
      "width": 2940,
      "height": 8192,
      "notes": "White editorial page, serif section titles, wide chart plates."
    }
  }
}
```

## Localization

Set `meta.language` to `zh-CN` or `en-US` for the bundled UI dictionary. `ui_labels` overrides any dictionary key without changing the renderer. Keep authored report prose in the report language; only interface chrome belongs in the dictionary.
