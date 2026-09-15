# experiments/

This directory keeps only the "final / best-known-performing" script from each exploratory stage. The full set of 16 dated iteration scripts has been packaged as `experiments-archive.zip` and uploaded to this repository's GitHub Release.

| Kept script | Original filename | Notes |
|---|---|---|
| `2025-10-27_multi_modal_final.py` | `20251027test5_Multi.py` | Final iteration of the multi-modal approach from 10-27 |
| `2025-10-28_gpt_referencevideo_accuracy90.py` | `20251028test5_OnlyWithReferVideo_Accuracy90 - GPT.py` | GPT-4V reaching ~90% accuracy after introducing reference-video comparison |
| `2025-10-28_referencevideo_detailed_final.py` | `20251028test8_OnlyWithReferVideo_ForDetailedTest.py` | Final refined test version from 10-28 |
| `2025-10-29_claude_referencevideo_accuracy90.py` | `20251029test2_OnlyWithReferVideo_Accuracy90 - Claude.py` | Claude version, also reaching ~90% accuracy |

> Selection criteria: based on the accuracy annotations in the filenames (Accuracy90/70/40) and each day's last iteration, judged to be the final/best version of that stage. If a different version actually better represents the final conclusion, let me know and I'll adjust which ones are kept.

The remaining 12 scripts (including Accuracy40, Accuracy70, BadPerformance, and other comparison/failure cases) are kept in `experiments-archive.zip` — they are still valuable as comparative experimental records, just not part of the "main line" kept at the repository root.
