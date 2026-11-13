# OM-3 合并固件 + 胶片预设 — 上卡与更换说明

本目录可直接复制到 SD 卡根目录使用。

包含内容：

- **Caduceus for OM-3 v0.22**（色轮 Hue/Light、Extras、Film/Looks）
- 已验证功能包：**光圈环**、**Wi‑Fi 5GHz**、**电子快门三槽自定义音效**
- 预置 **LOOKS.BIN / NAMES.BIN**（按网络经验整理的 COLOR1 五套胶片模拟）

> 风险提示：非官方固件。刷机前请充满电、备份设置，并保留 `restore/` 以便刷回原版 1.1。

---

## 1. 目录结构（本包）

```
caduceus-v022-merged-blog-looks/
├── DCOLYMP/
│   └── E1479999.BIN          ← 合并固件（刷机用）
├── OM3MOD/
│   ├── GUIDES.BIN            ← Caduceus 页面标签 + Extras 代码（必须与本固件同版本）
│   ├── LABELS.BIN            ← Extras 拨盘标签
│   ├── LOOKS.BIN             ← 胶片/Look 参数（已预置 blog-color1）
│   └── NAMES.BIN             ← Film 页显示的名称图
├── restore/
│   └── E1479999.BIN          ← 原版 OM-3 1.1（还原用，勿拷到卡上除非要还原）
├── presets/
│   ├── blog-color1/          ← 当前默认预设源文件备份
│   └── caduceus-default/     ← Caduceus 官方默认 20 Looks（可切换）
├── MANIFEST.json
└── README_刷机与预设.md      ← 本说明
```

**需要拷到 SD 卡根目录（与 `DCIM` 同级）的只有：**

- `DCOLYMP/`
- `OM3MOD/`

`restore/`、`presets/`、本 README **不要**拷到卡上（可留在电脑里）。

---

## 2. 首次刷机（推荐流程）

前提：机身已是官方固件 **1.1**，电池满电。

1. 将本包中的 `DCOLYMP` 与 `OM3MOD` 复制到 SD 卡根目录。
2. 关机 → 卡插入 **卡槽 1** → **按住 OK 键上电**，直到更新开始。
3. 橙色指示灯常亮约 2 分钟（编程中），**勿断电、勿拔卡**。
4. 指示灯开始闪烁后关机，再正常开机。
5. 回到电脑，**删除卡上的 `DCOLYMP/`**（避免下次误刷），**保留 `OM3MOD/`**。
6. 开机后 **半按快门一次**（加载 `LOOKS.BIN` / `NAMES.BIN` / Extras 代码）。
7. 进入 Picture Mode → **COLOR 1** → ▼ 打开色轮 → 应停在 **Film** 页；拨盘 1–5 即为预置胶片。

### COLOR 1 预置（blog-color1）

| 拨盘 | 名称 | 说明 |
| --- | --- | --- |
| 1 | Classic Neg | Fujifilm Classic Negative |
| 2 | Kodachrome 64 | Kodak Kodachrome 64 |
| 3–5 | **Empty** | 中性起点：机内调 HSL/Extras，Film 页长按 OK 存入该槽 |

COLOR 2–3 为幻灯片 / 负片组合。COLOR 4 槽 5 为旧库迁入的 **Vision3 500T**（Kodak **5219**）。拨盘 **0** = 该 COLOR 出厂设置。

### 若 Film / Looks 页不出现（常见坑）

与网上经验一致：相机必须成功读到合法的 `LOOKS.BIN`。

1. 确认卡上存在 `OM3MOD/LOOKS.BIN` 与 `OM3MOD/NAMES.BIN`（两者一起换）。
2. 删掉同目录下损坏的 `LOOKS.NEW` / `LOOKS.BAK`（若有）。
3. 半按快门一次后再进色轮。
4. **不要**把 RapidRAW 的 `.rrpreset` 直接丢进卡里——相机读的是 Caduceus 二进制格式。

---

## 3. 如何更换导入到相机的预设

预设 = `OM3MOD/LOOKS.BIN` + `OM3MOD/NAMES.BIN`（必须成对替换）。

### 方法 A：切换本包已生成的预设集（最快）

电脑上操作：

```text
把 presets\caduceus-default\LOOKS.BIN
    presets\caduceus-default\NAMES.BIN
复制覆盖到 SD 卡的 OM3MOD\ 下
（覆盖原来的 LOOKS.BIN / NAMES.BIN）
```

或改回 blog 五套：

```text
presets\blog-color1\LOOKS.BIN + NAMES.BIN → OM3MOD\
```

然后：卡插回相机 → 开机 → **半按快门一次** → 打开 COLOR 色轮查看 Film 页。

> 不必重新刷固件。只换卡上这两个文件即可。

### 方法 B：用 Caduceus Control Panel（推荐长期使用）

1. 打开：<https://androidfanman.github.io/caduceus-om3/>
2. 顶部选择 **OM SYSTEM OM-3**。
3. 在 COLOR 1–4 × Looks 1–5 中从片库添加/编辑（含 Classic Neg、Kodachrome、Portra 等约 60 套）。
4. **Export → Save to card…**（或下载 zip）写出新的 `LOOKS.BIN` + `NAMES.BIN`。
5. 覆盖到 SD 的 `OM3MOD/`，半按快门加载。

注意：

- 从 v0.20 起，`GUIDES.BIN` 必须与固件同版本；换预设时**不要**换旧版 `GUIDES.BIN`。
- `NAMES.BIN` 是名称位图；只换 `LOOKS.BIN` 不换 `NAMES.BIN` 时，名称可能对不上或只显示 “Film”。

### 方法 C：本仓库命令行重建预设

在工程根目录：

```bash
# 生成 blog COLOR1 五套（与当前默认相同）
py -3.12 tools/om3_build_looks_pack.py --out generated/om3-looks-pack/blog-color1 --pack blog-color1

# 或 Caduceus 官方默认 20 Looks
py -3.12 tools/om3_build_looks_pack.py --out generated/om3-looks-pack/caduceus-default --pack caduceus-default
```

将输出目录中的 `LOOKS.BIN` / `NAMES.BIN` 覆盖到 SD 的 `OM3MOD/`。

片库数据源：`third_party/caduceus-om3/webapp/src/data/om3films.json`。

### 方法 D：机内自制 Look

1. Film 页转到 **Empty** 槽位。
2. 调 Saturation / Hue / Light / Extras。
3. 回到 Film 页，**长按 OK** 保存进该槽。
4. 相机会写回 `LOOKS.BIN`（经 `LOOKS.NEW` 校验）；`NAMES.BIN` 不会被相机改写，名称仍可能是 Empty，可用 Control Panel 补名称图。

---

## 4. 还原原版固件

1. 将本包 `restore/E1479999.BIN` 复制为卡上 `DCOLYMP/E1479999.BIN`。
2. 同样：**按住 OK 上电**完成刷写。
3. 完成后删除卡上 `DCOLYMP`；`OM3MOD` 可删可留（原版不读这些文件）。

---

## 5. 功能自检清单（刷后）

| 项目 | 怎么确认 |
| --- | --- |
| Caduceus Film 页 | COLOR1 色轮 INFO 可到 Film；1–5 有名称 |
| 胶片效果 | 切换 Look 后实拍 JPEG 色彩有变化 |
| 光圈环 | 带光圈环的松下/徕卡镜头，A/M 下环控光圈 |
| Wi‑Fi 5GHz | 热点扫描可见 5GHz |
| 电子快门音 | 静音快门菜单 1/2/3 槽有自定义音 |
| Extras | Glow/Grain 等需同版本 `GUIDES.BIN`+`LABELS.BIN` |

---

## 6. 相关工程路径

| 用途 | 路径 |
| --- | --- |
| 合并构建脚本 | `tools/om3_caduceus_feature_merge.py` |
| 预设构建 | `tools/om3_build_looks_pack.py` |
| 合并说明 | `docs/features/om-3/CADUCEUS_MERGE.md` |
| Caduceus 使用说明 | `third_party/caduceus-om3/docs/USING.md` |
| 卡文件格式 | `third_party/caduceus-om3/docs/FORMATS.md` |
