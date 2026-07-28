# Input and data contract

Compile the factual layer before touching presentation code. The minimum input is report prose, structured numbers, source/date metadata for material claims, and one physical theme atom. Missing evidence must remain visibly missing; never repair it by invention.

## Root fields

- `schema`: use `visual-research-report@2` for new work.
- `meta`: `title`, `subtitle`, `kicker`, `publisher`, `as_of`, `language`, and `summary`.
- `evidence_status`: `verified`, `mixed`, or `synthetic`.
- `data_disclosure`: required for `mixed` and `synthetic`; provide `label`, `scope`, and placements such as `top-banner`, `methodology`, and `package-manifest`.
- `presentation`: `preset` is `institutional-rail` or `editorial-longform`; optional `reference_contract` records the supplied reference and measured geometry.
- `ui_labels` (optional): string-to-string overrides for interface copy. The renderer supplies complete `en-US` and `zh-CN` dictionaries, selected from `meta.language`.
- `theme_atom`: `name`, `description`, and exactly four `views` with IDs `recursive`, `exploded`, `blueprint`, and `impact`.
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

## Presentation and reference contract

Use `presentation.preset: "editorial-longform"` for a flat research-paper page. The preset fixes the 1440px page, 1120px chart plate, and 720px prose measures and disables a persistent desktop rail. Use `institutional-rail` when the research dashboard is part of the reading task.

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
