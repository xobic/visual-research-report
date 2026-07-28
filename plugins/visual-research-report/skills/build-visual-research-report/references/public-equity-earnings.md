# Public-equity earnings preset

Use this preset only for earnings reviews, results updates, or public-equity quarter readouts. Set `preset` to `public-equity-earnings` and supply all `preset_checks` fields before chart selection.

```json
{
  "preset": "public-equity-earnings",
  "preset_checks": {
    "expectation_delta": "Reported result versus the named consensus/source and cutoff date.",
    "organic_growth": "Growth with FX, acquisition, divestiture, and accounting boundaries stated.",
    "segment_cost_boundary": "Segment allocation and central/unallocated cost treatment.",
    "one_offs": "Material one-offs, period affected, tax treatment, and whether comparatives are restated.",
    "guidance_change": "Old range, new range, midpoint change, scope, and management rationale.",
    "capex_to_fcf": "Capex timing, depreciation/lease treatment, working capital, and FCF bridge.",
    "valuation_implied": "Price/date, share count, net debt/cash, metric year, multiple, and implied expectations.",
    "falsifiers": ["Observable condition that would invalidate the thesis", "Second independent falsifier"]
  }
}
```

## Discipline

- Name the expectation source and timestamp; do not compare against an unlabeled “beat/miss.”
- Organic growth must adjust numerator and denominator symmetrically. If only one period is adjusted, state why and do not label it comparable organic growth.
- Keep company-reported segment economics separate from analyst reallocations.
- Bridge one-offs explicitly and identify cash versus non-cash effects.
- Treat unchanged headline guidance with a changed midpoint, mix, or cost boundary as a change.
- Connect capex to depreciation lag, working capital, and free cash flow rather than presenting capex in isolation.
- Valuation conclusions require the exact market price date and share-count/net-debt basis.
- Falsifiers must be observable and updateable, not generic risk boilerplate.

The renderer includes these checks in the methodology area as a decision framework. Facts supporting the checklist still require normal `Fxx` evidence records.
