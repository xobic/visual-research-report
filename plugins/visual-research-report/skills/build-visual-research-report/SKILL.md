---
name: build-visual-research-report
description: Turn deep reports, research notes, structured tables, source lists, and visual references into polished interactive research websites with a traceable fact layer, one physical "theme atom," four-view cover storytelling, reference-faithful editorial layouts, data-shape-aware charts, clickable evidence drilldowns, responsive and print QA, and offline multi-file plus single-file packaging. Use when asked to visualize a report, match a research-page reference, build an institutional or editorial research microsite, convert a report to HTML/PDF, make report numbers auditable, choose non-generic charts, or package an interactive report that opens through file://.
---

# Build Visual Research Report

Compile the report as evidence-backed data first, then render it through the bundled publication system. Treat the report as the factual ceiling: improve structure and legibility without inventing claims.

## Required workflow

1. Inspect the supplied report, tables, source list, and local assets. Preserve the user's original files.
2. Establish the input contract. Confirm or infer only these items: report body, structured data, dates and sources for key numbers, one theme atom, evidence status, desired deliverables, and any reference image/brand target. If a missing item blocks factual accuracy, ask; otherwise proceed with an explicitly labeled assumption.
3. Read [input-and-data-contract.md](references/input-and-data-contract.md) completely. Compile `report.json` before writing presentation code.
   If the report is a public-equity earnings review, also read [public-equity-earnings.md](references/public-equity-earnings.md) and use the `public-equity-earnings` preset.
4. Select one concrete physical theme atom from the industry's causal machinery. Use the same object for every cover state. Never substitute a generic network, glowing orb, city skyline, or abstract geometry.
5. Read [chart-router.md](references/chart-router.md) completely. Select each chart from the data shape and reader task. Do not default to line or bar charts.
6. Read [design-system.md](references/design-system.md) completely. Choose a visual contract before coding: `editorial-longform` for reference-led paper pages and `institutional-rail` for dashboard-led research. If a reference is supplied, also read [editorial-longform.md](references/editorial-longform.md) completely and record the measured contract in `reference_contract`; reference fidelity outranks a default rail.
7. Build the site with the bundled scripts and template. Do not introduce a framework or remote CDN unless the user requests it. Figma is optional: when unavailable, continue with supplied assets, image generation, or the bundled engineering schematic, then export normally.
8. Read [qa-and-packaging.md](references/qa-and-packaging.md) completely. Run deterministic validation, build both deliverables, inspect responsive renders when browser automation is available, and report any remaining limitations.

## Fact discipline

- Assign every source a stable `Sxx` ID and every clickable quantitative claim an `Fxx` ID.
- Store display values and machine-readable values separately when formatting could obscure the underlying number.
- Attach at least one source ID and an as-of date to each material fact. Mark calculations as derived and list their input fact IDs.
- Record formula, comparison basis, adjustment scope, boundary, and precision whenever they affect interpretation. A concise basis sentence is not a substitute for these machine-checkable fields.
- Classify sources as primary or secondary and include a page, section, table, or timestamp locator whenever the source supports one.
- Make chart marks, KPI tiles, inline fact chips, and table cells open the same evidence drawer.
- Keep source titles, publishers, dates, URLs, and access notes in the data layer. Do not hard-code citations inside chart code.
- Distinguish reported values, estimates, scenarios, and probabilities visually and in the evidence basis.
- Never manufacture a source, date, or level of precision. For illustrative input, label it synthetic.
- Set `evidence_status` to `verified`, `mixed`, or `synthetic`. Synthetic or mixed reports require a prominent structured disclosure; never rely on a vague sentence hidden in body copy.
- Keep chart values consistent with their linked facts. Every matrix score, paired value, probability, balance weight, and tripwire must reference a fact; decorative marks remain non-interactive.

## Theme atom and cover

Choose the most specific recognizable physical object that explains the industry: for example a die/package, an industrial pig barn, or a container vessel. Reject an atom that cannot support all four views:

1. Recursive: the object repeats into its own system or value chain.
2. Exploded: physical parts separate along real assembly relationships.
3. Blueprint: engineering lines expose interfaces, constraints, and dimensions.
4. Impact: an unboxing or arrival moment creates narrative force.

Prefer four supplied or generated assets. Put their relative paths in `theme_atom.views[].asset`. The template supplies an honest diagrammatic fallback when assets are absent; treat that fallback as a draft, not a finished hero. All four views must depict the same object, not four adjacent industry concepts.

## Build commands

Set `SKILL_DIR` to this skill folder and `REPORT_JSON` to the compiled data file.

```bash
python3 "$SKILL_DIR/scripts/validate_report.py" "$REPORT_JSON" --strict
python3 "$SKILL_DIR/scripts/build_report.py" "$REPORT_JSON" --output <output-directory>
python3 "$SKILL_DIR/scripts/qa_report.py" <output-directory>
python3 "$SKILL_DIR/scripts/browser_qa.py" <output-directory>
python3 "$SKILL_DIR/scripts/export_pdf.py" <output-directory> --optional
python3 "$SKILL_DIR/scripts/finalize_package.py" <output-directory>
python3 "$SKILL_DIR/scripts/qa_report.py" <output-directory> --require-final
```

The builder creates:

- `<output-directory>/site/`: multi-file offline website
- `<output-directory>/report.html`: self-contained single-file version
- `<output-directory>/report.json`: compiled fact/source contract
- `<output-directory>/report.pdf`: optional print export when a supported browser is available
- `<output-directory>/build-manifest.json`: reproducibility metadata and file hashes

Start from [report.example.json](assets/report.example.json) only as a structural example. Replace every synthetic fact and source before presenting real research.

## Completion criteria

Do not call the work complete until all of the following hold:

- Every fact and source reference resolves.
- Every chart type matches its declared data shape.
- All four cover modes use the same theme atom.
- Clicking any marked number opens value, basis, date, and sources.
- The source register has stable anchors.
- The multi-file site and single-file report both build without external network dependencies.
- The single-file report embeds CSS, JavaScript, data, and every supplied cover asset; inline JavaScript parses independently.
- Script validation passes and browser console errors are zero when browser QA is available.
- Per-image and single-file resource budgets pass; generated raster covers are resized/compressed to WebP when that reduces cost.
- Desktop, tablet, and mobile layouts have no clipped labels, unintended horizontal scrolling, or rail overlap.
- Wide matrices scroll only inside their labeled regions. Print mode hides transient controls, keeps the cover to one page, and fits every scorecard dimension.
- Reference-led work includes a combined reference/implementation comparison and a written `design-qa.md`; do not claim visual parity from automated geometry alone.
