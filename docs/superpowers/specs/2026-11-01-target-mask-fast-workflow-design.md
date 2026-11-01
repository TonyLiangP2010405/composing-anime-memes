# Target Masks and Fast Sample Workflow Design

## Intent

Make anime avatar template creation faster and ensure the avatar inherits the target's shape instead of defaulting to a circular sticker.

## Goals

- Start with one representative sample and expand only after its preview is accepted.
- Reuse verified sources and static masks; annotate only necessary keyframes for moving targets.
- Require `target_mask` for character and chalk scenes, `quad_fill` for photo scenes, and `surface_mask` for print scenes.
- Validate real mask assets, their dimensions and contents, and frame references.
- Preserve full-GIF model review and user approval.

## Non-goals and anti-goals

- Do not add automatic circularity detection or a new general renderer.
- Do not replace target masks with AI segmentation.
- Do not permit `circle`, `ellipse`, or a universal avatar shape.
- Do not trade visual acceptance for speed or return to batch-first production.

## Approaches

The chosen approach is lightweight target-shape contracts plus real asset validation and a single-sample workflow. Strict geometric validation was rejected because it is slower and can misclassify face-like ellipses.

## Implementation decisions

- Add actor-level `shape` with the mode-specific values above.
- Resolve mask paths relative to the scene JSON and read them with Pillow.
- Require grayscale, non-empty masks matching `source_size`; character and print masks must also retain some unchanged pixels rather than covering the whole frame.
- Require four finite, non-degenerate vertices for `quad_fill`.
- Update the example, existing validator tests, and user-facing skill references.
