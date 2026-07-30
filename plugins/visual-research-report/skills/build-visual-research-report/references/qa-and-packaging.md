# QA and packaging

The deliverable is not complete when it merely renders once. Validate the data, build both formats, run deterministic package checks, then exercise the interface in a real browser.

## Required commands

```bash
python3 scripts/validate_report.py report.json --strict
python3 scripts/build_report.py report.json --output output
python3 scripts/qa_report.py output
python3 scripts/browser_qa.py output
python3 scripts/export_pdf.py output --optional
python3 scripts/finalize_package.py output
python3 scripts/qa_report.py output --require-final
```

The browser runner uses the bundled Playwright skill wrapper when available. Use `--playwright-cli` to point at another compatible wrapper and `--artifacts` to select screenshot output.

## Deterministic checks

- All fact/source/chart references resolve and IDs are unique.
- Share stacks sum to their declared total; negative layers use absolute encoding.
- Probabilities, percentage shares, units, unique series styles, and year-over-year adjustment scopes are semantically valid.
- The multi-file site has no remote runtime dependency.
- The single-file version has embedded CSS, JS, data, and cover assets. Verify this deterministically even when browser URL policy prevents direct `file://` navigation; report that browser limitation honestly.
- Every inline executable script in the single-file version passes a syntax check when Node is available. Use callback replacers when inserting user-authored text into JavaScript strings so `$&`-style replacement tokens cannot corrupt output.
- The build manifest hashes every delivered file and records schema `build-manifest@2` resource metadata.
- In Image 2 mode, the identity anchor and every visible cover file resolve inside the report root, decode as an allowed raster format, share the declared canvas/aspect, and have distinct hashes. Missing production art never silently becomes a schematic.
- The single-file Image 2 check parses the embedded report data and validates each of the four view-specific `data:image/...;base64` assets independently.
- Finalize the manifest after screenshots and optional PDF export so it covers `report.json`, QA assets, and `report.pdf` when present.
- JavaScript passes `node --check` when Node is available.

## Resource budget

Defaults are 2.5 MB per cover image, 6 MB total for the four built cover images, 10 MB for `report.html`, 2000px maximum raster dimension, and WebP quality 82. `image-2` and `provided` builds require Pillow because the builder must decode, verify, resize, and compress every PNG/JPEG/WebP cover asset; the build fails explicitly if Pillow is unavailable. Install it in the Python runtime with `python3 -m pip install Pillow` when needed. The manifest records relative provenance, source and built hashes, dimensions, aspect ratio, original size, built size, strategy, and result. Preserve blueprint linework with a suitable lossless or higher-quality treatment when the common setting visibly erases it. `qa_report.py` fails if an individual, total-cover, or single-file limit is exceeded. Override limits only for a documented delivery constraint, not to silence accidental bloat.

## Browser checks

Run desktop (1440×1000), tablet (1024×900), and mobile (390×844):

- zero console errors, page errors, and failed local requests;
- no document-level horizontal overflow; intentionally wide matrices must expose `data-contained-overflow="true"` and scroll only inside their labeled region;
- rail precedes the first section below 1100px;
- cover tabs support pointer and roving-keyboard navigation;
- drawer opens from a fact, exposes structured evidence, traps focus, marks the report inert, closes with Escape, and returns focus;
- no duplicate focusable fact IDs within a chart and no visible numeric mark without a fact-backed control;
- touch targets are at least 40px;
- value-stack ribbon widths match declared shares;
- multi-series line styles are distinct and the mobile scroller starts at the latest observation;
- source links resolve to stable anchors and reduced-motion mode remains usable.
- `editorial-scrollspy` keeps its chapter track sticky without covering anchored headings or creating page overflow;
- `editorial-dashboard` keeps a 48–52px desktop chapter track, a 25–32% sticky evidence rail, exactly one visible chapter state, and the first chart within the chapter opener viewport; selecting another chapter updates both navigation and rail state;
- every `history-scrolly` scene activates in order, updates the declared focus window, and falls back to a complete static chart under reduced motion;
- every causal node exposes direction and confidence in text, keeps its sparkline inside the node, and preserves one local focus target per fact;
- engineering schematic parts remain the same across all four cover views when schematic mode is selected;
- Image 2 mode loads four unique raster assets in both multi-file and single-file output, waits for each image to decode before capture, preserves the declared focal point, and never exposes a broken or blank intermediate state;
- cover animation is absent under reduced motion and in print.

Save viewport screenshots for all three widths plus cover and key chart anchors. Browser full-page stitching may repeat content, so use it only when verified. Inspect for label collision, clipped copy, directory/rail overlap, broken images, and unintended blank regions. Automated geometry is necessary but not sufficient.

For Image 2 production, create a contact sheet containing the identity anchor and all four states. Manually verify the same silhouette, part count, topology, materials, fiducials and camera in every panel; check state semantics, absence of pseudo-text/logos/watermarks, and at least 8% crop-safe space. Reject and regenerate only the failing direct edit. Pixel similarity or perceptual hashes cannot replace this review.

For a supplied reference, create `design-qa.md` and compare a combined reference/implementation view. Record measured differences and end with `final result: passed` only after the comparison actually passes.

## Print and PDF

Print CSS must hide transient controls, keep the cover to one A4 page, avoid scorecard column loss, and prevent print-only artifacts. `export_pdf.py` uses an installed Chromium-family browser when available; `--optional` records a skipped export without making an otherwise valid web package fail. Render or inspect representative PDF pages before handoff when PDF is requested.

## Handoff

Deliver `site/`, `report.html`, `report.json`, `build-manifest.json`, browser QA artifacts, optional `report.pdf`, and `design-qa.md` for reference-led work. State which checks ran, any intentionally overridden budgets, and any cover fallback still awaiting production imagery.
