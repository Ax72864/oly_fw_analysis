# Validating a modification

Different checks answer different questions. A valid update file is not proof of
correct runtime behavior; a successful image effect is not proof of independent
recovery after a broken startup.

| Check | What it establishes |
| --- | --- |
| Input hashes and model/build | The intended firmware is being analyzed |
| Decode/encode round trip | Container handling preserves unchanged bytes |
| Exact metadata and component diff | Changes stay within the intended package scope |
| Native loader and placement tests | Added bytes reach the modeled runtime address |
| ABI, alignment, bounds and ownership probes | Specific code contracts hold under stated fixtures |
| Pipeline and negative controls | Values reach intended consumers; unrelated cases remain unchanged |
| Physical UI / capture / reboot tests | Observed camera behavior for the tested cases |
| Physical recovery test | The particular failed state can be recovered by that procedure |

Use nonzero effects for transport tests. Neutral output can hide an entirely
skipped hook. Exercise all valid operation records, profiles and bank transitions;
several successive images can still all select record zero. Keep output ownership
separate from live editor values, and test preview and recording independently.

## Alignment is a real emulator blind spot

An HSL UI style contained u32 fields but had only two-byte assembly alignment.
Relocation placed it on a non-word boundary. Camera entry into COLOR restarted,
while the then-current emulator accepted its reads. Four-byte alignment corrected
the observed regression.

MN103 requires natural alignment for these word/halfword accesses. GNU simulator
helpers use unaligned host accesses, so “strict memory” does not automatically
check alignment. Use explicit checks at native load/store boundaries and inspect
linked addresses. Strings may need two-byte alignment; structures containing u32
fields need four-byte alignment. Preserve CALL frame, register-save mask, PSW,
MDR and loop-register conventions, not merely the visible argument registers.

## Useful negative controls

Make unselected objects inaccessible; poison unused bytes; test malformed
settings and owner pointers; retain already occupied operation records; and
change neighboring table counts or bounds in an isolated fixture to confirm
that the supposed protection is actually exercised. Keep request kind/length
correct, especially the 624-byte versus 1,132-byte image requests.

The probes stop on unknown accesses/instructions rather than supply broad zero
memory. Still, modeled allocation, hardware completion and deterministic scheduling
can hide physical timing or coherence faults. State those assumptions beside the
result, not only in tool source.

A preflight should also compare the entire stock and modified container,
reconstruct the exact final bytes independently where possible, and verify that
a stale checksum is rejected before a modeled backend write. An accepted backend
request is not a completed NAND write or a guarantee of error propagation.
