# Target Masks and Fast Sample Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make template production start with one fast sample and enforce target-derived avatar shapes with real mask validation.

**Architecture:** Extend the existing scene JSON with an actor-level `shape` contract. Keep validation in `scripts/validate_scene.py`, using Pillow to inspect masks relative to each scene file; update the existing documentation and example rather than adding a renderer.

**Tech Stack:** Python 3, Pillow, pytest, Markdown, JSON.

**Spec:** `docs/superpowers/specs/2026-11-01-target-mask-fast-workflow-design.md`

## Global Constraints

- Allowed mode/shape pairs: `character: target_mask`, `photo: quad_fill`, `print: surface_mask`, `chalk: target_mask`.
- Do not accept `circle`, `ellipse`, or a universal avatar shape.
- Preserve full-GIF model review and user approval.
- Do not add automatic circularity detection or a general renderer.
- Do not commit unless the user explicitly asks.

## Review Focus

- Missing, unreadable, or non-image mask paths must produce validation errors rather than exceptions; cover in Task 1 Step 1.
- RGB, empty, full-frame, and wrong-size masks must be rejected; cover in Task 1 Step 1.
- `quad_fill` must reject missing, non-finite, and degenerate vertices; cover in Task 1 Step 1.
- Direct Python callers and the CLI must resolve assets relative to the scene JSON, not the process working directory; cover in Task 1 Step 1 and Step 6.
- Existing structural and approval validation must keep working; cover with the complete existing test file in Task 1 Step 5.

---

### Task 1: Target Shape and Mask Validation

**Files:**
- Create: `examples/assets/teddy/change-00.png`
- Create: `examples/assets/teddy/change-01.png`
- Modify: `examples/character_scene.json`
- Modify: `scripts/validate_scene.py`
- Test: `tests/test_validate_scene.py`

**Interfaces:**
- Consumes: Existing scene dictionaries with `source_size`, `actors[].frames`, and mask paths.
- Produces: `validate_scene(config: dict, *, completed: bool = False, base_dir: Path | None = None) -> list[str]`; the CLI passes the scene JSON's parent as `base_dir`. Actor-level `shape` uses the global mode/shape mapping.

- [ ] **Step 1: Write failing validation tests**

Add tests that load the example with `base_dir=EXAMPLE.parent` and cover: every allowed mode/shape pair; missing or unknown `shape`; a forbidden `circle` shape; missing and unreadable mask files; RGB, all-black, all-white, and wrong-size masks; missing frame masks for `target_mask` and `surface_mask`; and absent, non-finite, wrong-length, or zero-area quads for `quad_fill`. Assert the relevant field name appears in the returned errors and that invalid image input never raises.

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python3 -m pytest tests/test_validate_scene.py -v`
Expected: FAIL because `shape`, `base_dir`, mask contents, and quad geometry are not yet validated.

- [ ] **Step 3: Implement minimal shape and asset validation**

In `scripts/validate_scene.py`, add the exact signature above and use Pillow. Resolve `change_mask` and frame `mask` paths against `base_dir`; require mode `L` or `1`, dimensions equal to `source_size`, and at least one white pixel. For `target_mask` and `surface_mask`, also require at least one black pixel. For `quad_fill`, require four numeric finite vertices with non-zero polygon area. Return field-specific errors and catch image/filesystem errors without aborting other checks.

Update `examples/character_scene.json` with `"shape": "target_mask"`, and create the two referenced 100×100 grayscale example masks with distinct black and white regions so the example remains valid.

- [ ] **Step 4: Run the validator tests to verify they pass**

Run: `python3 -m pytest tests/test_validate_scene.py -v`
Expected: PASS.

- [ ] **Step 5: Confirm existing behavior remains covered**

Run: `python3 -m pytest tests/test_validate_scene.py::test_completed_scene_requires_visual_approval tests/test_validate_scene.py::test_valid_approval_is_accepted tests/test_validate_scene.py::test_reject_requires_reason_and_cannot_be_approved -v`
Expected: PASS.

- [ ] **Step 6: Verify CLI path resolution**

Run: `python3 scripts/validate_scene.py examples/character_scene.json`
Expected: `SCENE_VALID` regardless of the caller's current working directory.

### Task 2: Fast Workflow and Shape Guidance

**Files:**
- Modify: `SKILL.md`
- Modify: `references/composition-patterns.md`
- Modify: `references/acceptance-contract.md`

**Interfaces:**
- Consumes: Task 1's actor-level `shape` values and mask requirements.
- Produces: User-facing instructions that use the same names and default to one representative sample.

- [ ] **Step 1: Rewrite the required workflow around one sample**

In `SKILL.md`, require one representative sample before expansion, reuse of verified sources, the first suitable source candidate, reuse of static masks, and keyframe interpolation for moving targets. Explicitly prohibit circular or universal avatar shapes. Preserve source provenance and final visual acceptance.

- [ ] **Step 2: Document exact mode-specific shape assets**

In `references/composition-patterns.md`, map character and chalk to `target_mask`, photo and rectangular drawings to `quad_fill`, and print/cups to `surface_mask`. State that white reveals avatar pixels and black preserves source pixels; cups must retain shading and foreground occlusion, while rectangular artwork fills its actual quadrilateral.

- [ ] **Step 3: Align acceptance evidence with the fast workflow**

In `references/acceptance-contract.md`, require mechanical and full-GIF checks for the single sample before further batch work, without repeating unchanged mechanical checks unnecessarily or weakening final approval.

- [ ] **Step 4: Check documentation consistency**

Run: `python3 -m pytest -v`
Expected: all existing and new tests PASS. Search the modified Markdown and example for `circle`, `ellipse`, `target_mask`, `quad_fill`, and `surface_mask`; confirm forbidden shapes appear only as prohibitions and all documented shape names match the validator.
