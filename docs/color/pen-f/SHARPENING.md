# JPEG sharpening controls

PEN-F sharpening is configured by CPU code and performed by an image-processing
unit. Workspace exposes a corresponding software edge-enhancement stage with
coring, variable gain and asymmetric limits. Calling the complete camera method
a simple Gaussian unsharp mask is not justified by the available evidence.

## Camera path

For build 3101, COLOR1–3 sharpness settings are 913–915. Parameter `chSharp` at
+`1626` becomes request byte +`422`:

```text
604f3405: mode / sensitivity / user-value selection
  → 604f3ba1: YC parameter packing
  → 604b4933 → 604b5006: register upload
  → 9e001800 or 9e005800
```

“YC” refers to luminance and chroma processing. The gain is not solely a function
of the UI slider: sensitivity, picture mode and processing stage affect selection.
The table at `60619ade` contains `64,96,128,160,208,256,256,256,256,256,256`.
Baseline indices and clamping explain plateaus in isolated configurations, but
do not prove that complete +0/+1/+2 photographs are identical.

The packed controls reach bank+`40`; the following limits reach bank+`44`.
Two spatial piecewise tables and sensitivity interpolation provide further
controls. Even the stock −2 setting leaves nonzero sharpening in the checked
path; UI zero is not sharpening off.

## Software edge shaping

The active Workspace block implementation shares edge shaping at
OlyPomegranate RVA `ed820`, luminance-dependent gain at `daac0`, and limiting at
`daec0`. Its composition routine is `c80c0`. With blend zero and both spatial
maps fixed to 64, the verified simplified rule is:

```text
positive edge:  min(max(0,  edge-A) * K >> 6, positive_limit, 1023)
negative edge: -min(max(0, -edge-A) * K >> 6, negative_limit, 1023)
```

A is coring: a dead zone for weak edges, with the threshold subtracted outside
that zone. K scales the surviving correction. The result is added to Y and
clipped to the output range. Separate chroma handling follows. The limits bound
correction magnitude, not local neighboring extrema; halos can remain.

A real render observes A=8, K=34, positive/negative limits 144/384 and flat spatial
maps in this branch. These are internal controls, not measured JPEG overshoot.
Other branches and settings can differ.

## Available controls and limits of reuse

The observed controls include edge-source selection, base gain, coring, a
signal-dependent blend, X/Y gain maps, luminance-dependent gain, gain-map threshold,
positive/negative correction limits, sign inversion and output clipping/shift.
The camera builder exposes only part of this as user sharpness.

Desktop zero-gain and independently zeroed-edge renders agree, providing a
useful YC-sharpening-off reference. Camera host-memory probes can set the gain
without changing coring or limits and verify the register upload. This is not a
physical camera qualification of an “off” modification.

The complete spatial extraction kernel, its relationship to demosaicing, and
bit-exact camera/desktop equivalence are not established. Replacing this stage
with a CPU algorithm would additionally require accessible image buffers, correct
pipeline placement and measured memory/runtime budgets. Applying sharpening to
a finished JPEG also sharpens its compression artifacts.

Tool: [penf_sharpening_probe.py](../../../tools/penf_sharpening_probe.py).
