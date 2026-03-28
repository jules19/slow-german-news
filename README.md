# Langsame Nachrichten

A daily German news reader for language learners. Fresh stories from Deutsche Welle, simplified to two difficulty levels (A1 and B1), with audio narration. Runs as a static PWA on GitHub Pages.

**Live site:** https://jules19.github.io/slow-german-news/

## How it works

A Python pipeline runs daily at 6am via macOS launchd:

1. **Fetches** 3 stories from the DW news API
2. **Simplifies** each story to A1 (beginner) and B1 (intermediate) using OpenAI gpt-4o-mini
3. **Generates audio** for each level using Qwen3-TTS (local, free, runs on Apple Silicon)
4. **Deploys** to GitHub Pages via the `gh-pages` branch

The site keeps a rolling 3-day archive with date tabs.

## Setup

### Prerequisites

- macOS with Apple Silicon (M1/M2/M3/M4) — required for local Qwen3-TTS
- Python 3.11+
- Node.js (for Tailwind CSS build)
- ffmpeg (`brew install ffmpeg`)
- An OpenAI API key

### Install

```bash
# Create venv with all dependencies (project + mlx-audio for TTS)
python3 -m venv .venv-qwen-tts
source .venv-qwen-tts/bin/activate
pip install -e .
pip install mlx-audio

# Create .env with your API key
echo "OPENAI_API_KEY=sk-your-key-here" > .env
echo "TTS_BACKEND=qwen" >> .env
```

### Run manually

```bash
source .venv-qwen-tts/bin/activate

# Run the full pipeline (fetch, generate levels, generate audio, deploy)
TTS_BACKEND=qwen ./scripts/build-and-deploy.sh

# Or run just the pipeline without deploying
TTS_BACKEND=qwen python -m backend.build

# Run tests
pytest tests/ -v
```

### Set up daily automation

The launchd job runs the build at 6am daily. If your Mac is asleep at 6am, it catches up on wake.

**Install:**
```bash
cp scripts/com.langsame-nachrichten.build.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.langsame-nachrichten.build.plist
```

**Check status:**
```bash
launchctl list | grep langsame
```

**Uninstall:**
```bash
launchctl unload ~/Library/LaunchAgents/com.langsame-nachrichten.build.plist
rm ~/Library/LaunchAgents/com.langsame-nachrichten.build.plist
```

**View logs:**
```bash
cat build.log                # build script log
cat build-stdout.log         # pipeline stdout (when run via launchd)
cat build-stderr.log         # pipeline stderr (when run via launchd)
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (required) | OpenAI API key for LLM |
| `TTS_BACKEND` | `openai` | `qwen` for free local TTS, `openai` for API |
| `TTS_VOICE` | `nova` | OpenAI voice (ignored when TTS_BACKEND=qwen) |
| `LLM_MODEL` | `gpt-4o-mini` | OpenAI model for text generation |
| `MAX_STORIES` | `3` | Number of stories per day |
| `VENV_PATH` | `.venv-qwen-tts` | Python venv path for the build script |
| `KEEP_DAYS` | `3` | Days of content to keep in rolling archive |

## Project structure

```
backend/
  build.py          — Pipeline orchestrator
  levels.py         — CEFR level generation (C1→B1→A1)
  audio.py          — TTS audio generation (OpenAI or Qwen3-TTS)
  sources.py        — DW news API client
  models.py         — Data models
  prompts.py        — LLM prompt templates
  assets/           — Voice clone reference audio
frontend/
  index.html        — PWA shell
  app.js            — Client-side logic, audio player, date tabs
  sw.js             — Service worker
  input.css         — Tailwind source
scripts/
  build-and-deploy.sh              — Daily build + deploy automation
  com.langsame-nachrichten.build.plist  — macOS launchd schedule
tests/                             — 43 unit tests
docs/
  brainstorms/      — Requirements documents
  plans/            — Implementation plans
  ideation/         — Feature ideation
  solutions/        — Documented solutions
```

## Costs

- **TTS:** Free (local Qwen3-TTS on Apple Silicon)
- **LLM:** ~$0.60/month (gpt-4o-mini, 3 stories/day)
- **Hosting:** Free (GitHub Pages)

## CI fallback

The GitHub Actions workflow (`.github/workflows/build-and-deploy.yml`) can still deploy using OpenAI TTS as a backup. Trigger it manually from the Actions tab.
