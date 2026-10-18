# Probe reference data

These small JSON files hold facts consumed by the tools: section extents,
reference classifications, table addresses, hashes and scalar calibration values.
They are not complete execution traces or firmware data dumps.

[tools/inputs.json](../tools/inputs.json) identifies their consumers and original
source hashes. The grain mask is checked by SHA-256 against bytes extracted from
the supplied firmware; the lookup table itself is not needed in this directory.
New probe output belongs under `generated/`.
