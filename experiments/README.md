# experiments/ 说明

本目录只保留每个探索阶段中「最终版 / 已知效果最好」的脚本，完整的 16 个按日期迭代的测试脚本已打包为 `experiments-archive.zip`，上传在本仓库的 GitHub Release 中。

| 保留脚本 | 原文件名 | 说明 |
|---|---|---|
| `2025-10-27_multi_modal_final.py` | `20251027test5_Multi.py` | 10-27 当天多模态方案的最终迭代版本 |
| `2025-10-28_gpt_referencevideo_accuracy90.py` | `20251028test5_OnlyWithReferVideo_Accuracy90 - GPT.py` | 引入参考视频对比后，GPT-4V 达到约 90% 准确率的版本 |
| `2025-10-28_referencevideo_detailed_final.py` | `20251028test8_OnlyWithReferVideo_ForDetailedTest.py` | 10-28 当天最后一次细化测试版本 |
| `2025-10-29_claude_referencevideo_accuracy90.py` | `20251029test2_OnlyWithReferVideo_Accuracy90 - Claude.py` | Claude 版本，同样达到约 90% 准确率 |

> 选择标准：基于文件名中的准确率标注（Accuracy90/70/40）以及每天最后一次迭代，判断为该阶段的最终/最优版本。如果实际上有其他版本更能代表最终结论，请告诉我，我再调整保留哪几个。

其余 12 个脚本（包括 Accuracy40、Accuracy70、BadPerformance 等对比/失败案例）保留在 `experiments-archive.zip` 中，它们同样是有价值的对照实验记录，只是不作为"主线"版本放进仓库根目录。
