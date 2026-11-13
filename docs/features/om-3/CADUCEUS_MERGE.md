# OM-3 Caduceus + feature-pack merge

Builds a single SD package on **OM-3 1.1 / 1100** that combines:

- **Caduceus for OM-3 v0.26.2**（当前默认；v0.22 机身已验证路径可作对照）
- Verified-path **shutter-sound** + three custom WAV slots（ring / wifi 默认不并入）

## Why not a blind stack

| Conflict | Resolution |
| --- | --- |
| `ring-native` cave `0x6031e910` vs Caduceus `ext1` `0x6031e920` | Relocate ring cave to **`0x60339660`**（shutter WAV 后首空闲；拉长 section-1 end）。**勿用** `0x60388000` |
| Shared facade `0x60e57480/90/94` | Keep Caduceus；miss 后 `jmp` 到 shutter 完整入口（再回 stock）。v0.26.2 get/cnt/vbi 先走 `sl_*` |
| Facade `0x60e5749c` | v0.22 可直占；v0.26.2 为 Caduceus `sl_sel`，同样经 miss 链 |
| ext1 miss sites | v0.22：`…c68/…f1b/…f56`；v0.26.2：**+2** → `…c6a/…f1d/…f58`（另链 `sl_sel` `0x60f4ac4d`） |
| MN103 `dc` rel32 | **`target = insn_addr + rel`**（不是 +5） |

Miss path: **Caduceus editor → shutter menu → stock**.

## Rebuild (offline) — 当前默认 v0.26.2

```bash
python tools/om3_caduceus_feature_merge.py --features shutter-sound \
  --caduceus-release third_party/caduceus-om3/releases/v0.26.2 \
  --out generated/om3-caduceus-shutter-only --write-container \
  --stage-sd generated/om3-sd-install/caduceus-v0262-shutter-only

python tools/om3_transplant_shutter_slots.py \
  --target-main generated/om3-caduceus-shutter-only/main.decoded.bin \
  --out generated/om3-caduceus-shutter-only-slots123 --write-container \
  --stage-sd generated/om3-sd-install/caduceus-v0262-shutter-only-slots123 \
  --om3mod generated/om3-sd-install/caduceus-v0262-shutter-only/OM3MOD

python tools/om3_caduceus_merge_selftest.py \
  --caduceus-release third_party/caduceus-om3/releases/v0.26.2 \
  --out generated/om3-caduceus-merge/selftest-v0262
```

## SD 卡快门音（post-merge）

```bash
python tools/om3_caduceus_feature_merge.py --features shutter-sound \
  --out generated/om3-caduceus-shutter-only --write-container
python tools/om3_shutter_sd_patch.py \
  --main generated/om3-caduceus-shutter-only/main.decoded.bin \
  --out generated/om3-caduceus-shutter-sd --rebuild-asm --write-container \
  --stage-sd generated/om3-sd-ready/caduceus-v0262-shutter-sd \
  --om3mod generated/om3-sd-ready/caduceus-v0262-shutter-only/OM3MOD \
  --wav path/to/a.wav --wav path/to/b.wav --wav path/to/c.wav
python tools/om3_shutter_sd_selftest.py \
  --main generated/om3-caduceus-shutter-sd/main.decoded.bin \
  --report generated/om3-caduceus-shutter-sd/report.json \
  --stage-sd generated/om3-sd-ready/caduceus-v0262-shutter-sd \
  --out generated/om3-caduceus-shutter-sd/selftest
```

卡上：`OM3MOD/SHUT01.WAV`…`SHUT99.WAV` + `SHUTSEL.BIN`。源码：`patches/shutter_sd/om-3/ss_sd.s`。

## Install tree（推荐上卡包）

**稳定推荐（2026-11-13 机身通过）— Caduceus v0.26.2 + 预埋快门音：**

`generated/om3-sd-ready/caduceus-v0262-shutter-only-resident/`（`71e5de2c…`）  
整合步骤与已知限制：[CADUCEUS_V0262_SHUTTER_STABLE.md](CADUCEUS_V0262_SHUTTER_STABLE.md)。

**对照（v0.22 机身已通过）：**

`generated/om3-sd-ready/caduceus-v022-shutter-only-blog-looks/`

**SD 读音效（基于 resident 重建，未机身确认）：**

`generated/om3-sd-ready/caduceus-v0262-shutter-sd/`（`d2d7ce49…`）

```bash
# 仅示意：指定 --caduceus-release …/v0.22 可复现旧包
python tools/om3_caduceus_feature_merge.py --features shutter-sound \
  --out generated/om3-caduceus-shutter-only --write-container \
  --stage-sd generated/om3-sd-install/caduceus-v022-shutter-only
```

全量合并（ring/wifi）历史上多次 bootloop，仅作对照。中文说明：[SD_READY_刷机与预设.md](SD_READY_刷机与预设.md)

| Path | Role |
| --- | --- |
| `DCOLYMP/E1479999.BIN` | Merged update |
| `OM3MOD/` GUIDES/LABELS（v0.26.2 另有 LOOKS/TONES） | Caduceus card extras |
| `restore/E1479999.BIN` | Stock 1.1 |

Flash ritual: [FLASH_WORKFLOW.md](../../boot/om-3/FLASH_WORKFLOW.md)（Slot 1，长按 **OK**）。刷完保留 `OM3MOD`；半按一次加载 Caduceus。

## Status

| Check | Result |
| --- | --- |
| **Body（稳定推荐）** | `caduceus-v0262-shutter-only-resident`（`71e5de2c…`）：色彩 + 快门音 **2026-11-13 通过** |
| Body（对照） | `caduceus-v022-shutter-only-blog-looks` 已通过 |
| SD from resident | `…-shutter-sd`（`d2d7ce49…`）离线自检通过，**未机身确认** |
| Offline tools | `om3_caduceus_feature_merge.py --features shutter-sound` + WAV transplant |
| 全量 ring/wifi | **未**在 Caduceus 同包机身验证通过；勿作推荐 |
| 能力说明 / 错题集 | [VERIFIED_CAPABILITIES.md](VERIFIED_CAPABILITIES.md) · [MERGE_MISTAKES.md](MERGE_MISTAKES.md) |
| Prior feature pack alone | Body OK 2026-11-04 |
| Caduceus alone | Upstream camera-tested v0.22 |
