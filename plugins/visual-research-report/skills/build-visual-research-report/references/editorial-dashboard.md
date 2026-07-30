# Editorial dashboard contract

Use `presentation.preset: "editorial-dashboard"` when the reading task benefits from seeing the current chapter thesis and its evidence at the same time. This preset combines editorial longform hierarchy with a chapter-synchronized right rail; it is not a generic application dashboard.

## Desktop geometry

- Reference viewport: 1440px wide.
- Page width: at most 1440px with 16px minimum outer gutters.
- Chapter track: 48–52px high, sticky at the viewport top, short labels only.
- Main grid: argument column plus a 25–32% evidence rail, separated by 24–36px.
- Prose: at most 720px. Charts may use the full argument column.
- Rail: sticky below the chapter track, fully readable within the remaining viewport height, with no dark card stack or decorative shadow.

At widths below 1100px, hide the synchronized rail and retain the sticky, horizontally scrollable chapter track. The body becomes one column. Print hides both navigation and rail.

## Chapter rhythm

The opener must establish a conclusion and expose evidence in one viewport:

1. compact eyebrow, title, and deck;
2. one argument paragraph or bounded callout;
3. the first chart title and at least the beginning of its plot;
4. the synchronized evidence rail.

Target 280–380px for the opener before the first chart. At a 1440×1000 viewport, the first chart should begin before 720px; on a shorter reference viewport, aim for 480–560px below the chapter track. Put the first body block before the first chart, then continue with remaining body and visuals. Avoid consecutive gaps above 120px that carry no new information.

## Evidence rail anatomy

Each rail state reuses the active section's eyebrow, title, and deck, then renders:

- one large `primary_fact_id` current reading;
- an optional ordered `trend_fact_ids` micro-chart;
- a two-by-two block from `metric_fact_ids`;
- up to three probability paths from `scenario_fact_ids`;
- the fact/source count, date, and evidence-drilldown reminder.

Every visible value is a button bound to the shared evidence drawer. Do not duplicate values, dates, or sources inside the dashboard contract. A trend must use facts with one shared unit and the declared order; never connect unrelated KPIs into a decorative line. Scenario slots accept probability facts only.

## Visual language

Use a white sheet, navy ink hierarchy, cobalt for active state and quantitative emphasis, semantic red only for real warnings, and 1px cool-gray rules. Use cards only where containment communicates a real grouping. The rail should read like a compact research worksheet, not a SaaS control panel.

Keep the Image 2 four-state theme-atom cover intact. The dashboard preset changes the research-reading layer, not the physical-object identity system.

## Acceptance checks

Compare the implementation and supplied reference at the same viewport and section state. Do not approve the result if the first screen still contains only a title, the rail remains static across chapters, navigation labels truncate, the rail exceeds one viewport, or any dashboard number cannot open its fact basis, date, and sources.
