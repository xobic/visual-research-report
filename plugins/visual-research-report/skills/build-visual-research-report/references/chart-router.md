# Chart router

Choose from the reader's task and the data's shape. A chart is an argument with evidence, not a decorative library choice.

| Data shape / task | Chart | Required behavior |
|---|---|---|
| Discrete capacity or scale ramp | `entity-ramp` | Use a recognizable industry unit; disclose glyph size. |
| Entities moving through stages | `destiny-flow` | Preserve stages, direction, attrition, and source/destination semantics. |
| Dated events and regime changes | `timeline` | Show sequence without implying forecast certainty. |
| Multiple windows × multiple dimensions | `matrix-heat` | Keep exact values visible; color only supports scanning. |
| Value-chain layers | `value-stack` | Use proportional `absolute` or `share` encoding; negative values automatically use zero-axis bars. |
| Analyst probability | `odds-board` | Require probability, horizon, trigger, and evidence basis. |
| Exact ordered trend reading | `line` | Use only when slope/path is the task. |
| Exact named pair comparison | `paired-bars` | Compare compatible units and explicit bases. |
| Forces on two sides plus falsifiers | `tension-balance` | Bind every weight and tripwire to a fact; show an actual score scale. |
| Long history with named regimes | `history-scrolly` | Bind scroll scenes to ordered focus windows; retain a full static reduced-motion view. |
| Signals propagating across time horizons | `causal-horizon-map` | Encode direction, confidence, lag, threshold, sparkline and directed relationships. |

## Value stacks

Never draw equal-height blocks for unequal values. `encoding: "share"` normalizes non-negative values and validates the declared total. `encoding: "absolute"` preserves magnitude; if any layer is negative the renderer switches to diverging rows around a zero axis. One interactive legend row represents each fact so keyboard users do not encounter duplicate controls.

## Multi-series lines

Use the full categorical palette and optional unique series colors, not a two-color alternation. Label each series at its latest point and label meaningful extrema. Resolve nearby labels vertically. On narrow screens preserve the latest observation by scrolling the chart to the right after render; do not let the newest point disappear outside the initial viewport. If more than six dense series remain illegible, split into small multiples instead of shrinking text.

## Actual scales and multipliers

Matrix, line, paired-bar, and tension-balance charts use `scale.mode: "actual"` with a finite increasing domain and ordered ticks. Never show normalized 0–100 geometry under an index, score, currency, or unit subtitle. If paired groups use incompatible units, use `scale.mode: "per-pair-actual"` and declare a scale on every item.

A visible multiplier is a derived fact, not decorative copy. Its fact must derive from the two paired values, equal right ÷ left, use numeric precision, and render canonically as `×n.n` (or the declared precision). Baseline zero is an error.

## Tension balances

Use a balance when the argument is explicitly about competing forces. `long` and `short` items represent the two sides; `tripwires` are observable falsifiers underneath. Every item has a `fact_id`, and its value comes from that fact. Do not use a balance as a generic pros/cons list.

## Scroll-driven history

Use `history-scrolly` only when named regimes materially improve comprehension. Every scene must select an ordered start/end label from the first series. Do not duplicate or mutate data between scenes. Keep the full path visible in reduced-motion and print modes, and keep scene prose useful without animation.

## Causal horizons

Use `causal-horizon-map` when the thesis distinguishes leading, coincident, and lagging signals or similar time windows. Direction and confidence are categorical; numeric signal, lag, threshold, and sparkline values come from facts. Edges express the report's claimed mechanism and require a methodology caveat; they do not imply statistical causality by themselves.

## Interaction contract

Each fact appears as one focusable target per local visual context. Clicking it opens the evidence drawer. Decorative marks stay `aria-hidden`. Chart wrappers expose `data-chart-type`; stack shares, line scroll behavior, active history scenes, and causal nodes expose QA attributes. Never encode kind, sign, direction, confidence, or scene state by color alone.

## Rejection rules

Reject a chart when it hides the comparison basis, mixes incompatible units without an explicit per-pair scale decision, normalizes an actual scale, visually overstates equal blocks, duplicates focus targets for the same local fact, leaves a visible number without a fact, or clips the latest observation on mobile. Use prose/table when the dataset is too small or the visual adds no reading advantage.
