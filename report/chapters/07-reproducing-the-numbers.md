# Reproducing the numbers

Every number in the results tables, the figure captions and the results chapters is a
pin: a value the build reads from a record in the project's repository at the moment the
PDF is rendered, so the prose cannot drift from the data. The statistical figures and the
costs are read from the committed public results file. That file is a projection of the
single evaluation artifact and is recorded by the artifact's digest; before the file was
committed, an offline acceptance command regenerated it and compared the result byte for
byte. The caps, levels, output maximum and budget are read from the bound registration
file. The operational counts (calls stopped at the output maximum, and input tokens per
run) and the world's audit counts are read from the recorded findings by exact text; the
script behind the operational counts needs the run exports and is not rerun at build, so
the build checks those against the record and does not recompute them. A few numbers in
the prose about the instrument and the calibration, such as the probe's counts and the
forty seeds of the runtime-truth comparison, are quoted from the cited records, and a
number derived by hand says so where it appears.

| Handle | Value |
|---|---|
| Repository | github.com/arda-basarici/leave-impact-agent |
| Committed results file | `src/leaveimpact/results/m2-reported.json` |
| Evaluation artifact, SHA-256 | {{pin:provenance.artifact_digest}} |
| Measurement world, version | {{pin:provenance.world_version}} |
| Registration, digest | {{pin:provenance.registration_digest}} |
| Registration, bound at commit | {{pin:provenance.registration_commit}} |
| Evaluator, commit | {{pin:provenance.evaluator_commit}} |
| Registration and protocol | `preregistration/registration.json`, `preregistration/PROTOCOL.md` |
| Findings | `probes/FINDINGS.md`, section `phase-c` |
| This report's chapters, pins and figures | `report/chapters/`, `report/pins.py`, `report/figures/` |

The committed results file is validated by the test suite on every change, and the
headline figures this report cites are asserted there against the values the findings
record. The measurement world's contents stay embargoed. The golden world's seed and
recipe are open and its audit findings are published; its scenario keys and its audit
record are released with the project's demo, not before.
