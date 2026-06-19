# Exclusion Rules

These rules prevent candidate fishing and overclaiming.

## Not Allowed Before Bundle Freeze

- Inspecting ranked source IDs.
- Hand-selecting thresholds from visually appealing candidates.
- Re-ranking candidates using LLM judgement.
- Applying all-source `PROGRAM:NIGHT` offsets for candidate scoring.
- Calling screening labels confirmed binaries or confirmed variables.

## Exclude From Primary Candidate Claim

Exclude or downgrade any source if:

- fewer than three OOF-correctable good epochs remain;
- all signal disappears when one epoch is removed;
- the largest residual is confined to one exposure or one known problematic
  night label;
- any scored epoch fails the frozen quality cuts;
- Gaia grouping is ambiguous or appears to merge multiple physical sources;
- spectral-fit quality fields indicate an obvious failed fit;
- the source is a known pulsator or photometric variable and the RV evidence is
  not independently strong;
- the result depends only on a cross-program transition.

## High-Confidence Candidate Minimum

A high-confidence previously uncatalogued RV-variable candidate must have:

- at least three OOF-correctable good epochs;
- at least two nights;
- a corrected RV signal supported by at least two epoch pairs;
- leave-one-epoch-out robustness;
- no single-night or single-exposure explanation;
- no known external catalogue identity explaining the variability;
- an inspected DESI spectrum/model dossier.

