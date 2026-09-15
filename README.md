# cobot-llm-vision-inspector

An experimental system that uses large language models / vision-language models (GPT-4V, Claude) to visually inspect the quality of collaborative robot (Cobot) assembly actions. The system extracts key frames from assembly process videos and, combined with the assembly standards defined in an Excel sheet, asks an LLM/VLM to judge whether the assembly action meets expectations (success/failure), comparing detection accuracy across different models and prompting strategies.

## Repository structure

```
src/                Core system code (independent implementations for Windows / macOS, see below)
experiments/        Representative scripts for each experimental stage (full iteration history in the GitHub Release assets)
docs/               Assembly instructions and the GPT vs Claude comparison report
results/
  reports/          Per-video scoring results (json, small, kept in the repo)
  summary/          Aggregated statistics across multiple experiment runs
media/              Representative sample videos (1 reference video + 1 experiment sample; full video set in the Release)
```

## src/: why there are duplicate `_mac` files

`cobot_controller.py` / `gui.py` / `vision_system.py` each have a corresponding `*_mac.py` version. After a line-by-line diff:

- `cobot_controller.py` and `cobot_controller_mac.py` differ only slightly (mainly log file paths and emoji vs. plain-text logging), and could in principle be merged into one file with a `platform.system()` branch. Since this code directly controls a physical robot, I did not merge it automatically for safety reasons — the two files are kept separate for now; let me know if you'd like them merged.
- `gui.py`/`vision_system.py` differ substantially from their `_mac` counterparts (over 90% rewritten) — they are effectively two independent implementations, so simple merging isn't appropriate and each platform version is kept as-is.

## Environment variables / API keys

All OpenAI / Anthropic API keys that were previously hardcoded in the source have been removed and are now read from environment variables:

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

`src/config.example.json` is a template for local configuration (robot IP, video paths, etc.). Copy it to `config.json` to use it (already in `.gitignore`, so it won't be committed).

## Getting the full data (not included in the repository)

The following items are too large to store directly in git history and have been packaged and uploaded to this repository's GitHub Release — download them from the Releases page:

- `experiments-archive.zip` — all historical test scripts not kept in `experiments/` (the dated exploratory iterations)
- `testresults-archive.zip` — raw key frames, debug frames, logs, and other intermediate artifacts from each testing stage
- `results-frames.zip` — extracted frames from `Results/frames`
- `video-archive.zip` — all original experiment videos except the 2 samples kept in `media/`

## Experimental methodology

See `experiments/README.md` for the method and known accuracy associated with each stage's script.

## License

MIT — see [LICENSE](LICENSE).
