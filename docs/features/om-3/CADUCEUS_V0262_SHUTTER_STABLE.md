# Caduceus v0.26.2 + 电子快门音效（稳定版）

**机身状态（2026-11-13）：已通过。**  
包：`generated/om3-sd-ready/caduceus-v0262-shutter-only-resident/`  
容器 SHA-256：`71e5de2c84691dcb636edb729a6d5ea702f1df09b22881c8aee51e925eaad0ab`

含 Caduceus v0.26.2 色彩（LOOKS/TONES 等）+ 预埋三槽电子快门 WAV。不含 ring / Wi‑Fi 5 GHz。

## 已知限制（先不修）

静音/电子快门自定义音效 **仅在「焦点锁定提示音」开启时才出声**；关闭该提示音后，菜单里可选槽位，但快门触发无声。

这不是本包刻意做的门控（上游 shutter 资产亦声明 `no_forced_af_beep_setting`），更像机身提示音/音频通路共用静音条件。记为 **已知限制**，暂不改固件。

## 整合方法（可复现）

离线步骤，不写相机：

```bash
# 1) Caduceus v0.26.2 + shutter-sound 代码（无自定义 PCM）
python tools/om3_caduceus_feature_merge.py --features shutter-sound \
  --caduceus-release third_party/caduceus-om3/releases/v0.26.2 \
  --out generated/om3-caduceus-shutter-only --write-container

# 2) 灌入三槽 WAV（transplant 或 om3_shutter_slots.py）
python tools/om3_transplant_shutter_slots.py \
  --target-main generated/om3-caduceus-shutter-only/main.decoded.bin \
  --out generated/om3-caduceus-shutter-only-slots123 --write-container

# 3) resident 修复：抬高 section-3/8 加载尾 + 恢复 v0.22 菜单/提交洞穴
python tools/om3_shutter_v0262_resident_fix.py
# 产出：generated/om3-sd-ready/caduceus-v0262-shutter-only-resident/
```

相对「仅 merge + transplant」必须多做第 3 步，否则会出现：

- 槽 1/3 选中即重启（WAV 在文件里但不在加载尾内）
- 槽 2 能选无声（`runtime_menu` / `runtime_controls` 被未验证覆盖层换掉）

细节与错题：[MERGE_MISTAKES.md](MERGE_MISTAKES.md) 错题 7、[CADUCEUS_MERGE.md](CADUCEUS_MERGE.md)。

## 刷机

将包内 `DCOLYMP/` 与 `OM3MOD/` 拷到 SD 根目录，Slot 1，关机后 **按住 OK 开机**。刷完保留 `OM3MOD`，半按一次加载 Caduceus。回退用同卡 `restore/E1479999.BIN`（官方 1.1）。

## SD 卡读音效

另案：须以 **本 resident 主镜像** 为底再叠 SD loader，见 `tools/om3_shutter_sd_patch.py`。早期 `…-shutter-sd` 机身失败，勿混用。
