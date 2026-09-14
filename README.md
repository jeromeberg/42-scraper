# 42-scraper

![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)

Scrape projects from the 42 intra, download subject PDFs and build a markdown table with extracted data.
Optionally scrape stack and instructions from subjects using AI (locally via Ollama).

<img width="925" height="840" alt="Screenshot 2026-06-20 at 20 29 54" src="https://github.com/user-attachments/assets/6a654bbb-6e74-42cd-859e-cddde215705c" />


## Features

- Scrape recommended projects list (default) or all 42cursus projects.
- Sort projects by name (default), duration or XP.
- Download all subject PDFs.
- Extract name, description, keywords, XP, duration into a markdown table.
- Optional: scrape stack and summarise instructions from subjects using local AI (Ollama).

## Instructions

### Prerequisites

- Python 3.10+
- Pip3
- Optional: Ollama (recommended models: `qwen2.5:3b` or `llama3.2:3b`)

### Set up

#### 1. Create a virtual env

```bash
python3 -m venv venv
source venv/bin/activate
```

#### 2. Install requirements

```bash
pip install -r requirements.txt
```

#### 3. Configure .env

```bash
cp .env.example .env
```

Edit `.env`:

```env
# 42 intra session cookie (required)
INTRA_COOKIE=

# ollama (optional)
OLLAMA_ENDPOINT=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b

```

⚠️ **To get your cookie:** open [projects page](https://projects.intra.42.fr/projects/list) on 42 intra, open DevTools, go to Network tab, click any request and copy the full `Cookie:` header value.

#### 4. Optional: set up Ollama

Install Ollama from the [website](https://ollama.com/download) or `brew install ollama` on macOS.

```bash
# pull model
ollama pull llama3.2:3b

# start ollama server (if not already running)
ollama serve
```

Recommended models: `llama3.2:3b`, `qwen2.5:3b`.

## Usage

```bash
# Scrape recommended projects sorted by duration
python main.py --sort duration

# Scrape and enhance (requires ollama)
python main.py --enhance

# Scrape, enhance, and overwrite projects.md
python main.py --enhance --overwrite

# Only download subject pdfs
python main.py --pdfs-only

# Scrape all projects sorted by XP
python main.py --all --sort xp
```

**Standalone usage:**

```bash
python scraper.py
python enhance.py
python enhance.py --overwrite
```

## Flags

All flags can be used when running `python main.py`.

| Flag | Script | Description |
|------|--------|-------------|
| `--enhance` | main only | Run AI enhancement after scraping. |
| `--limit <N>` | all | Limit to the first N projects. Useful for debugging. |
| `--all` | scraper | Scrape all 42cursus projects instead of recommended ones. |
| `--sort name\|duration\|xp` | scraper | Sort order: `name`, `duration` or `xp`. |
| `--pdfs-only` | scraper | Only download subject PDFs, skip table generation. |
| `--model <model>` | enhance | Overwrite OLLAMA_MODEL set in `.env` |
| `--overwrite` | enhance | Write output back to `projects.md` instead of creating a new file. |
| `--out <directory>` | all | Set custom OUTPUT_DIR (default: `output/`) |
