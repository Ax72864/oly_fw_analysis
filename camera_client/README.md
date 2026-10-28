# Camera Wi-Fi research clients

- **PEN-F** (`penf_wifi`): COLOR profile read/transfer research client (below).
- **OM-3** (`om3_wifi`): read-only discovery; see [om3_wifi/README.md](om3_wifi/README.md).

# PEN-F Wi-Fi research client

A Python command-line client for reading COLOR profiles and transferring
numeric recipes through the camera's Wi-Fi HTTP service. It is an experimental
research interface, not a packaged phone app. Python's standard library is
sufficient; the local lock/state implementation targets Linux.

The camera must already be connected through its normal private Wi-Fi mode.
The client does not configure Wi-Fi, acquire credentials, stream live view or
press the shutter. It checks the model before using the researched endpoints.

## Supported settings

One profile contains 12 hue, 12 saturation and 12 lightness values (`−7…+7`),
contrast (`−2…+2`) and highlights/midtones/shadows (`−7…+7`): 40 values total.
The recipe does not choose its destination; `--profile 1`, `2` or `3` does.
Exposure compensation and WB recommendations may be carried as text, but are
not written to the camera. Direct custom-bank uploads are refused; uploads use
PASM bank 0 and custom-mode assignment remains a camera operation.

Stock firmware can expose saturation/tone readback. Missing H/L is reported as
unknown, never silently filled with zeros. **All uploads require a compatible
camera-side receiver advertising `HSL1` (`0x48534c31`)**, including saturation
uploads. Merely having editable HSL in the camera does not establish this
receiver. This source repository does not install or supply that firmware.

## Read, preview and transfer

From this directory, with the computer connected to the camera's Wi-Fi:

```bash
python3 -m penf_wifi discover
python3 -m penf_wifi session rec
python3 -m penf_wifi inspect --profile 2 --recipe-out saved-color2.json
python3 -m penf_wifi preview examples/subtle-color.json --profile 2
python3 -m penf_wifi apply examples/subtle-color.json --profile 2
```

`discover` identifies the camera without a mode change. `session rec` explicitly
requests remote shooting; no live-view stream or capture follows. The recipe
`apply` command above only prints an offline plan. To send that reviewed plan:

```bash
python3 -m penf_wifi apply examples/subtle-color.json --profile 2 --execute
python3 -m penf_wifi verify examples/subtle-color.json --profile 2
python3 -m penf_wifi session play
```

`play` changes the remote session mode; it is not a proven save/commit command.
Native setters perform the persistent update. An immediate successful readback
checks current values; reconnect and verify again after an ordinary manual
camera restart to test persistence. `verify` exits 0 for a match, 3 for a
mismatch, and 2 for an error.

Uploads save a complete pre-edit snapshot and a restore recipe before any
setting write, send only changed values, check context and immediate readback,
then verify the full profile. The client prints the run directory containing
`before.json`, `restore-recipe.json`, `after.json` and command records. Restore
by previewing and applying that restore recipe to the same destination.
Partial recipes intentionally leave omitted settings unchanged.

The camera service processes requests sequentially. The default request gap is
0.05 seconds; full read/verify cycles involve many HTTP requests. `--timeout`,
`--ready-timeout` and `--request-gap` are global options before the command.
Progress goes to stderr; stdout remains JSON. `--help` lists offline snapshot
export/comparison and single-setting commands.

## Recovery after an interrupted operation

A lost reply may mean the camera already changed a value. The client therefore
stops without an automatic retry or rollback and records an uncertainty marker
that prevents further writes from later invocations. Read-only inspection and
verification remain available.

After manually restarting camera Wi-Fi and reconnecting, inspect the actual
profile. Only then acknowledge that reconnect locally:

```bash
python3 -m penf_wifi acknowledge-reconnect --after-manual-reconnect
```

This clears a client marker; it does not contact the camera or repair settings.
Preview the desired or saved restore recipe and explicitly apply it again.
A connection failure before a request is sent is distinguished from an unknown
result after transmission. Re-running `session rec` is not a universal remedy
for a lost Wi-Fi connection.

## Tests and protocol sources

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m unittest discover -s tests -p check_loopback.py
```

The first suite uses mocks, synthetic settings and compact numeric native-probe
observations. The second starts a temporary server on `127.0.0.1` only. Neither
contacts a camera. The firmware-side probes are listed in the
[tool catalog](../tools/README.md).

Run logs and snapshots can contain device information and user settings; keep
`runs/` local. Portable recipes deliberately omit camera identity and context.
The supplied example is a protocol demonstration, not an optimized look.
