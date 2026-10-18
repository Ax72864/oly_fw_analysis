# Licenses and attribution

The original analysis tools and writing have no repository-wide license.
Existing component licenses apply within their stated scope:

- The GNU MN103 runner and simulator changes carry GPL-3.0-or-later notices.
  The license text is in [LICENSES/GPL-3.0.txt](LICENSES/GPL-3.0.txt).
- External research and firmware identities are attributed in
  [provenance](provenance/README.md).
- The authored Value lettering derives from DejaVu Sans Condensed; its
  [font notice](LICENSES/DejaVu.txt) applies to that artwork, not the firmware.

The HSL source includes short displaced stock instructions at hook boundaries
and small before/after byte edits. It does not include a firmware image or
bulk disassembly. Those vendor-derived fragments and the separately obtained
IDA processor module retain their own provenance; the project's license choice
cannot grant rights to them.

A license for these tools does not grant rights to vendor firmware, Workspace,
third-party patchers or extracted resources. Obtain required inputs separately
under their applicable terms. Source hashes identify material; they do not
establish redistribution permission.
