# Caduceus × feature 合并错题集

机身曾多次「背光亮起 → 灰屏 → 熄灭 → 循环」。下列为已坐实的错误改动与正确对照，供后续合并避坑。

---

## 错题 1：ring cave 放在 section-1 加载区外

| | |
| --- | --- |
| **错误** | 将 ring-native cave 迁到 `0x60388000` |
| **现象** | 开机循环 |
| **根因** | Section-1 加载 end（含 WAV 后约 `0x60339660`）远小于 `0x60388000`；hook 跳入未映射地址 |
| **正确** | Cave 必须落在 section-1 end 之内。与 shutter WAV 共存时可用 WAV 尾后首空闲字节 `0x60339660`，并 **抬高 end**（对齐到 2 KiB） |
| **判据** | `NEW_CAVE + size ≤ section1_end_getter(0x60045e84)` |

---

## 错题 2：重定位时把数据里的 `0xDC` 当成跳转改写

| | |
| --- | --- |
| **错误** | `relocate_ring_cave` 扫描洞穴内所有 `dc`，凡「目标在洞穴外」就改 rel |
| **现象** | Cave 已在 section 内仍开机循环 |
| **根因** | 洞穴 payload 中有 9 处数据恰好以 `0xDC` 开头；改 rel 破坏常量（如 `6c3719…`） |
| **正确** | 只改写 **目标落在可信代码窗**（如 `0x60000000..0x62000000`）的出口；其余保持原字节 |
| **判据** | 与「仅 plausible 出口」重定位结果逐字节一致；假阳性位点数据不变 |

---

## 错题 3：MN103 `dc` 相对跳转 off-by-5

| | |
| --- | --- |
| **错误** | `encode/decode` 使用 `target = insn_addr + 5 + rel` |
| **现象** | Facade 链或 ring hook 重定向后开机循环；菜单链「看起来」指对地址，实则早 5 字节 |
| **根因** | Caduceus `jmp stock_*`（`editor.ld` 完整入口）与 shutter miss→stock 实证为 **`target = insn_addr + rel`** |
| **正确** | `rel = to - from_addr`；解码 `from_addr + rel` |
| **后果链** | 旧编码器把 Caduceus miss 链到 `shutter_entry - 5` → 跑飞；ring hook 同理偏 5 |

---

## 错题 4：误判「绝不能链到 shutter 完整入口」

| | |
| --- | --- |
| **错误** | 因错题 3，以为 miss→shutter 完整入口会双序言/炸栈，改为只保留 miss→stock，且不接 count/vbi |
| **现象** | 能开机，但电子快门音效菜单只有 OFF / 0，无法调自定义档 |
| **根因** | Caduceus 源码（`editor.s`）在 miss 前已 `movm` 恢复入口状态，再 `jmp` **完整** stock 入口；语义上同样可 `jmp` shutter 完整入口 |
| **正确** | 在 **正确 dc 编码** 下：Caduceus miss → shutter full →（非快门）stock；Caduceus 仍占用 facade `80/90/94`，shutter 占用 write/blocked |
| **判据** | `0x6031ef1b → 0x6031fa00` 等三条链目标与 shutter 入口一致；菜单可选多档 |

---

## 错题 5：Caduceus + ring/wifi 同包过早「宣布修好」

| | |
| --- | --- |
| **错误** | 仅离线结构检查通过就当可刷；或与 shutter 问题缠在一起未二分 |
| **现象** | 多次「修复」后仍循环；官方固件可恢复 → 非刷写流程问题 |
| **正确做法** | **二分：** Caduceus alone → Caduceus+shutter → 再尝试 ring/wifi。当前机身仅验证 **Caduceus + shutter/WAV** |
| **现状** | ring-native / wifi-5ghz **不要**并入当前推荐包 |

---

## 错题 6：无 ring 时忘记扩展 section-1 end

| | |
| --- | --- |
| **错误** | 只打 shutter、不打 ring：end 仍停在 Caduceus/stock 的 `0x6031f000` |
| **现象** | shutter 洞穴从 `0x6031f000` 起写在加载区外（或依赖后续 WAV 才抬 end，中间态危险） |
| **正确** | 合并 shutter 后显式 `ensure_section1_end` 覆盖至少 `0x603244ac`；WAV transplant 再抬到覆盖 PCM |

---

## 错题 7：v0.26.2 + 预埋快门音描述符/加载尾未对齐

| | |
| --- | --- |
| **错误** | 只认 RIFF 在文件里、或只拷 `wav_descriptors`，不核对 section 加载尾与菜单洞穴 |
| **现象** | `14701245…`：槽2 崩 / 槽3 硬死机；`09ddf208…` descfix：槽1/3 选即重启，槽2 无声 |
| **根因** | 槽1/3 的 WAV 落在 section 3/8 **排他加载尾之后**（文件有、内存无）；槽2 在 section1 内故不炸，但 `runtime_menu`/`runtime_controls` 被未验证覆盖层换掉 → 无声 |
| **正确** | 加载尾须盖住 PCM 终点（对照 v0.22：`0x608272b0` / `0x617fd520`）；菜单洞穴与 v0.22 一致；未上机前标 **FAILED**/候选 |
| **同批失败** | `caduceus-v0262-shutter-sd`（`e631ad84…`）亦 **FAILED** |
| **descfix 亦失败** | `caduceus-v0262-shutter-only-descfix`（`09ddf208…`）：描述符改对后，槽 1/3 选即重启，槽 2 可选无声。见错题 8 |

---

## 错题 8：只改描述符，不抬 section-3/8 加载尾

| | |
| --- | --- |
| **错误** | 认为槽 1 `0x60820000`、槽 3 `0x617e4800` 的 RIFF 写进文件就会被加载；descfix 只拷了 126 字节描述符 |
| **现象** | 选槽 1/3 立刻重启；槽 2（在已抬高的 section-1 内）可选但无声 |
| **根因** | 加载尾是 `fc cc` 立即数。v0.26.2 的 section-3 停在 `0x60820000`、section-8 停在 `0x617e4800`，WAV 正好从这两个排他终点开始，落在段间空隙，选中时读指针即故障。v0.22 把这两处抬到 `0x608272b0` / `0x617fd520`。WAV 移植没带上它们：供体功能包在注入 WAV 之前就已经是这个尾值，差值里没有这两条 |
| **槽 2 无声** | 描述符、WAV、捕获钩子与 v0.22 一致，且 PCM 在 section-1 内。唯一的快门代码差是 `runtime_menu` `0x6031fa00` / `runtime_controls` `0x6031fe00` 被未上机验证的 native-commit、`menu_error_propagation` 盖掉；v0.22 仍是 multibody 原字节 |
| **正确** | 只抬 section-3/8（勿把 section-6 从 v0.26.2 的 `0x60f59800` 缩回去），并把上述两段代码换回 v0.22。离线产物 `caduceus-v0262-shutter-only-resident`（`71e5de2c…`）**尚未机身确认** |

---

## 速查：推荐包 vs 对照包

| 包 | 用途 |
| --- | --- |
| `om3-sd-ready/caduceus-v022-shutter-only-blog-looks` | **当前唯一机身验证推荐** |
| `om3-sd-install/stock-1.1-restore` | 官方恢复 |
| `feature-only-rollback` | 无 Caduceus 的 ring/wifi/shutter 对照（历史机身 OK） |
| `caduceus-v0262-shutter-only` / `…-descfix` / SD 旧 `e631ad84…` | **FAILED（2026-11-12 机身）**，勿刷 |
| `…-shutter-sd` 当前 `952c4fc1…` / `…-resident` | 离线候选，**未机身确认** |
| `caduceus-v0262-shutter-only-resident` | 离线候选，**未**机身确认；确认前不要拿它替换 v0.22 |
| 含 `badChain` / `bootloop` / `caveCorrupt` / `0x60388000` 的产物 | **作废**，勿刷 |

更完整的能力表见 [VERIFIED_CAPABILITIES.md](VERIFIED_CAPABILITIES.md)。
