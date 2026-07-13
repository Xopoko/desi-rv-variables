# Independent Confirmation Protocol

This document freezes the minimum design for a confirmatory analysis on data
that were not used to develop the current workflow. The public DESI DR1 MAIN
sample is exploratory and must not be relabelled as an independent confirmation
by changing folds or random seeds.

## Eligible Confirmation Data

One of the following is required:

- a future DESI stellar release not available during workflow development;
- a pre-declared DESI survey slice with no source, exposure, or night overlap
  with the exploratory sample;
- an external spectroscopic survey with a documented source and epoch mapping.

## Frozen Inputs

Before opening source-level outcomes, record:

- immutable code commits and dependency lockfiles;
- input file names, sizes, and SHA-256 hashes;
- source-association rules;
- quality cuts and adopted uncertainty model;
- fold assignment algorithm;
- offset-model hyperparameters;
- screening and robustness thresholds;
- injection-recovery grid and random seeds;
- external catalogue versions and match radii.

## Primary Confirmation Outcomes

1. Holdout raw-scatter reduction for the declared residual model.
2. Candidate-level transition count relative to the full-pipeline permutation
   distribution.
3. Bootstrap stability of source classifications.
4. Null false-positive rate and injection recovery on the untouched cadence
   distribution.
5. Program-pair metrics reported separately and as a macro-average.

No source may be called new or astrophysically confirmed solely because it is
absent from a finite set of external catalogues. Novelty requires the declared,
versioned crossmatches plus direct spectrum/model review and independent
follow-up evidence.

## Decision Rule

The confirmation succeeds only if the direction of the primary aggregate
effects is reproduced without changing the frozen rules and no declared
program-pair control shows material degradation. Otherwise the result is
reported as non-replicated or inconclusive; thresholds are not retuned on the
confirmation sample.
