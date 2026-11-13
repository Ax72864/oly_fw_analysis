# OM-3 已验证 / 待验证固件能力说明

**基准机身固件：** OM-3 1.1 / 1100

## 当前推荐上卡包

### Caduceus v0.26.2 + 预埋快门音（稳定版，2026-11-13 机身通过）

`generated/om3-sd-ready/caduceus-v0262-shutter-only-resident/`  
容器 SHA-256：`71e5de2c84691dcb636edb729a6d5ea702f1df09b22881c8aee51e925eaad0ab`

| 项 | 状态 |
| --- | --- |
| Caduceus 色彩配方（LOOKS/TONES） | **通过** |
| 电子快门音效选槽 / 播放 | **通过**（不崩溃） |
| ring / Wi‑Fi 5 GHz | 未合并 |

整合步骤与已知限制：[CADUCEUS_V0262_SHUTTER_STABLE.md](CADUCEUS_V0262_SHUTTER_STABLE.md)。

**已知限制：** 静音快门自定义音仅在「焦点锁定提示音」开启时出声；关闭则无声。非本包刻意门控，暂不修。

### 对照：Caduceus v0.22 + 快门音（机身已通过）

`generated/om3-sd-ready/caduceus-v022-shutter-only-blog-looks/`

开机 / HSL / 色彩预设 / 快门音效菜单与播放已通过（2026-11）。

## 失败包（已移出推荐树，勿刷）

| 包 | 摘要 |
| --- | --- |
| `caduceus-v0262-shutter-only`（`14701245…`） | 槽2 崩；槽3 硬死机 |
| `…-descfix`（`09ddf208…`） | 槽1/3 选即重启；槽2 无声 |
| `…-shutter-sd` 旧 `e631ad84…` / 中期 `952c4fc1…` | 进菜单重启或未基于 resident |

## SD 卡读音效

须以 **resident 主镜像** 为底重建（见 `tools/om3_shutter_sd_patch.py`）。未再经机身确认前不作推荐。

## 刻意未合并

| 能力 | 原因 |
| --- | --- |
| 松下光圈环 ring-native | 与 Caduceus 同包仍未作为稳定推荐 |
| Wi‑Fi 5 GHz | 同分位排除 |

## 相关文档

- [CADUCEUS_V0262_SHUTTER_STABLE.md](CADUCEUS_V0262_SHUTTER_STABLE.md)
- [CADUCEUS_MERGE.md](CADUCEUS_MERGE.md)
- [MERGE_MISTAKES.md](MERGE_MISTAKES.md)
- [FLASH_WORKFLOW.md](../../boot/om-3/FLASH_WORKFLOW.md)
