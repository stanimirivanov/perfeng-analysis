# Analysis language

Terms for scientific interpretation of verified performance evidence. Shared terms are defined in the [Perfeng glossary](https://github.com/stanimirivanov/perfeng-contracts/blob/main/GLOSSARY.md).

## Language

**Normalization**
The conversion of supported raw observations to explicitly defined metrics, units and statistics.

**Candidate Measurement**
A normalized measurement evaluated under a Performance Policy.

**Reference Measurement**
A normalized measurement supplied for comparison with a candidate. The caller establishes the reference artifact’s identity and eligibility.

**Measurement Quality**
The policy assessment of whether a metric’s units, sample sufficiency and variability support evaluation.

**SLO Evaluation**
A result comparing an eligible candidate statistic with an inclusive policy bound.

**Regression Evaluation**
A directional candidate-to-reference comparison against a configured practical-degradation threshold.

**Inconclusive**
An outcome indicating insufficient or unsuitable evidence to determine a result.

**Point-Estimate Comparison**
A comparison of the selected candidate and reference statistics against a practical threshold.

**Non-blocking Analysis Report**
An Analysis Report that records evidence and verdicts for consumers. Enforcement is a separate decision at the consuming boundary.
