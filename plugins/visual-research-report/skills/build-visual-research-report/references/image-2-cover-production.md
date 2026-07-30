# Image 2 theme-atom cover production

Use this workflow whenever the report needs production raster artwork and the user has not supplied four approved cover assets. The four states are not independent illustrations: they are four presentations of one frozen physical object.

## Execution path

Use the built-in `image_gen` tool, backed by `gpt-image-2`. Do not make the offline Python builder call an image API. Do not switch to a different model or CLI path silently. If the built-in tool is unavailable, report the limitation and use `production.mode: "schematic"` only after an explicit fallback decision.

Generate five audit assets:

1. one hidden canonical identity anchor;
2. `recursive`, edited directly from the anchor;
3. `exploded`, edited directly from the anchor;
4. `blueprint`, edited directly from the anchor;
5. `impact`, edited directly from the anchor.

Never chain `recursive → exploded → blueprint → impact`. Image generation has no seed-level identity guarantee; direct edits, recorded locks and visual QA provide the continuity control.

## Freeze the identity contract

Compile `theme_atom.identity_lock` from the report and, when present, the engineering schematic. Record:

- physical class and recognizable silhouette;
- stable part IDs and one-to-one topology;
- material and color language;
- at least two visible fiducials, such as a clipped corner, asymmetric hatch, named deck layout, inspection window or contact-pad pattern;
- exact camera projection, yaw, pitch, roll, focal length, center and crop-safe margin.

The object must support all four states without invented machinery. Reject a generic atom whose identity depends on glow, text or abstract networks.

## Anchor prompt

Use this normalized prompt and replace every bracketed value:

```text
Use case: product-mockup
Asset type: canonical identity anchor for a four-state institutional research website cover

Create exactly one fully assembled [ATOM_NAME], a real physical [PHYSICAL_CLASS].
Its fixed identity is:
- silhouette: [SILHOUETTE]
- topology: [TOPOLOGY]
- proportions: [PROPORTIONS]
- materials: [MATERIALS]
- unique fiducials: [FIDUCIALS]

Camera lock: [PROJECTION], yaw [YAW] degrees, pitch [PITCH] degrees,
roll [ROLL] degrees, [FOCAL_LENGTH] mm-equivalent lens. Center the object at
[CENTER], keep it inside the declared assembled scale, and leave at least
[SAFE_MARGIN] clear space on every side.

Style: production-grade scientific product visualization for an institutional
research publication; physically plausible materials; restrained, precise and
editorial rather than cinematic.

Scene: a plain controlled studio field with a subtle engineering grid.
Constraints: exactly one object; no cutaway or exploded gaps; no added or
missing components; no text, labels, numbers, logo, trademark or watermark;
no generic circuit-board scenery.
```

Inspect the anchor before continuing. Fix one defect at a time. Once accepted, copy it from the generated-images directory into the report workspace and never regenerate it during the same cover set.

## Shared edit lock

Prefix every state prompt with the complete identity and camera lock:

```text
Image 1 is the canonical identity anchor and the only identity authority.
Change only the requested presentation state.

Keep unchanged: physical class, silhouette, part count, topology, proportions,
materials, colors, fiducials, orientation, camera projection, yaw, pitch, roll,
focal length, center and assembled scale. Do not redesign, simplify, beautify
or substitute the object. No text, labels, numbers, logo or watermark.
```

## State prompts

Recursive:

```text
Keep the foreground object unchanged, fully assembled and dominant. Add exactly
three exact copies receding at monotonically smaller scales into its physical
system. Every copy preserves the same silhouette, part arrangement, materials
and fiducials. Use restrained repetition, not an abstract fractal, network,
glowing orb or unrelated machinery.
```

Exploded:

```text
Separate only the existing declared parts along one assembly axis in the real
order [SEPARATION_ORDER]. Preserve every part's lateral registration, shape,
material and orientation. Show a one-to-one mapping from the anchor with subtle
unlabelled alignment guides. Add, delete, duplicate and merge nothing.
```

Blueprint:

```text
Change only the rendering treatment. Preserve the exact anchor geometry,
silhouette, seams, part count, topology, camera and framing. Render pale-cyan
and off-white technical linework on a deep cobalt field with restrained
construction lines. Do not invent dimensions, annotations, glyphs, labels,
numbers or internal parts.
```

Impact:

```text
Keep the exact object fully assembled, undeformed and in the same pose, camera
and scale. Show it arriving from [INDUSTRY-SPECIFIC CARRIER OR CONTAINER] with
restrained external motion cues and one semantic-red impact accent. External
elements may not alter the object or obscure more than 8% of its silhouette.
Do not use a generic consumer cardboard unboxing scene.
```

## Persistence and provenance

Copy the anchor and all four accepted masters into the report directory. Use stable descriptive names. Record:

- `production.mode: "image-2"` and `model: "gpt-image-2"`;
- `workflow: "canonical-anchor-plus-direct-edits"`;
- anchor asset, canvas, prompt version, master format, delivery format and print view;
- per-view parent anchor, prompt ID, invariants, generated time and QA status;
- input and output SHA-256 values;
- optional prompt hash or a full sidecar manifest when exact reproduction matters.

The builder converts the four visible assets to delivery images and embeds them in the single-file report. The anchor remains an audit asset and must be available during validation.

## Acceptance gate

Create one contact sheet containing the anchor and four states. Inspect it manually before browser QA.

Global requirements:

- the anchor and four masters share one canvas and aspect ratio;
- all five file hashes are distinct;
- subject center, camera direction and assembled scale remain stable;
- every declared part, material and visible fiducial survives all applicable states;
- no mirror, camera reversal, substituted object, pseudo-text, logo or watermark;
- at least 8% crop-safe space protects the object at desktop and mobile widths.

State requirements:

- recursive copies are exact objects at strictly decreasing scales;
- exploded parts appear once each in a physically credible order;
- blueprint geometry aligns with the anchor and invents no dimensions;
- impact keeps the object assembled and uses an industry-real arrival context.

If any check fails, set that view's `qa_status` to `rejected` and regenerate only that direct edit. Perceptual hashes and automated geometry support this review but cannot replace it.
