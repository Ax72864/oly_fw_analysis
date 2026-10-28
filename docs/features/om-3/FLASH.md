# OM-3 external flash

Cross-model parser comparison lives in
[features/FLASH.md](../FLASH.md). For OM-3 build 1100:

| Item | Address / value |
| --- | --- |
| Parser | `601e75ba` |
| Class-2 control branch | `601e6644` |
| Logical port | 22 |

Parser behaviour after address normalization agrees with E-P7/OM-5 on the
inspected builds. That does not prove hotshoe power electronics or FL-LM3
compatibility. Tools:
[compare_external_flash.py](../../../tools/compare_external_flash.py).
