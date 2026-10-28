# OM-3 Wi-Fi research client

Read-only discovery against an OM-3 camera's private Wi-Fi HTTP service.
It identifies the model and lists advertised OI.Share commands. It does **not**
implement COLOR/HSL recipe upload, settings-backup transfer or live view.

Stock OM-3 protocol descriptions are larger than PEN-F's. Named backup or
partial-transfer commands may appear in `get_commandlist.cgi`; their presence
is not evidence that this client can safely drive them. No HSL1 capability is
claimed for stock OM-3 firmware.

## Usage

From `camera_client/`, with the computer already on the camera's Wi-Fi:

```bash
python3 -m om3_wifi discover
python3 -m om3_wifi identify
```

For PEN-F COLOR workflows use `python3 -m penf_wifi` instead. Cross-model
uploads are refused deliberately.

## Simulation

`om3_wifi.fake.FakeOm3Camera` provides an in-process HTTP edge for unit tests.
It models identity and command-list replies only.
