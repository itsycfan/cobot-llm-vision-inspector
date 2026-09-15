# cobot-llm-vision-inspector

利用大语言模型 / 视觉语言模型（GPT-4V、Claude）对协作机器人（Cobot）装配动作进行视觉质量检测的实验系统。系统通过抓取装配过程视频的关键帧，结合 Excel 中定义的装配标准，让 LLM/VLM 判断装配动作是否符合预期（成功/失败），并对比不同模型、不同 Prompt 策略的检测准确率。

## 目录结构

```
src/                核心系统代码（跨 Windows / macOS 两个平台的独立实现，见下）
experiments/        各阶段代表性实验脚本（完整迭代记录见 GitHub Release 附件）
docs/               装配说明文档、GPT vs Claude 对比报告
results/
  reports/          每段测试视频的评分结果（json，体积小，随仓库保留）
  summary/          多轮实验的汇总统计
media/              代表性样例视频（参考视频 + 1 个实验样例，完整视频集见 Release）
```

## src/ 说明：为什么有 `_mac` 后缀的重复文件

`cobot_controller.py` / `gui.py` / `vision_system.py` 各自有一个 `*_mac.py` 版本。经过逐行 diff 后发现：

- `cobot_controller.py` 与 `cobot_controller_mac.py` 差异较小（主要是日志路径、emoji 换成纯文本），理论上可以合并成一份用 `platform.system()` 做分支，但由于这是直接控制物理机器人的代码，出于安全考虑我没有自动合并，暂时保留两份独立文件，你确认后我们可以再做合并。
- `gui.py`/`vision_system.py` 与其 `_mac` 版本差异非常大（改写比例超过 90%），本质上是两套独立实现，不适合简单合并，因此按平台各自保留。

## 环境变量 / API Key

代码中原先硬编码的 OpenAI / Anthropic API Key 已全部移除，改为从环境变量读取：

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

`src/config.example.json` 是机器人 IP、视频路径等本地配置的模板，使用时复制为 `config.json`（已加入 `.gitignore`，不会被提交）。

## 完整数据获取（未随仓库上传的部分）

以下内容体积较大，不适合直接存进 git 历史，已打包上传到本仓库的 GitHub Release，可在 Releases 页面下载：

- `experiments-archive.zip` — `experiments/` 之外的全部历史测试脚本（按日期迭代的探索版本）
- `testresults-archive.zip` — 各阶段调试用的关键帧图片、debug frames、日志等原始中间产物
- `results-frames.zip` — `Results/frames` 抽帧图片
- `video-archive.zip` — 除 `media/` 中 2 个样例外的全部原始实验视频

## 实验方法简述

见 `experiments/README.md`，记录了各阶段脚本对应的方法与已知准确率。

## License

尚未确定，待补充。
