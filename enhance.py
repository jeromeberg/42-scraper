#!/usr/bin/env python3

'''
File: enhance.py
Repo: https://github.com/jeromeberg/42-projects-scraper
Author: Jerome Berg
Date: 2026/06/21
'''

import re
import argparse
import json
import logging
import os
import pdfplumber
import time
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = Path("output")
PDF_DIR = OUTPUT_DIR / "pdfs"
INPUT_FILE = OUTPUT_DIR / "projects.md"
OUTPUT_FILE = OUTPUT_DIR / "enhanced.md"
CHECKPOINT_FILE = OUTPUT_DIR / "processed.json"

OLLAMA_ENDPOINT = os.environ.get("OLLAMA_ENDPOINT", "http://localhost:11434").rstrip("/") + "/api/generate"
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_TEMPERATURE = 0.15
DELAY = 0.2

OUTPUT_HEADERS = ["Name", "Description", "Keywords", "Stack", "Instructions", "XP", "Duration"]

PROMPT_TEMPLATE = """\
Extract structured information from this 42 school project PDF.

Project: {name}
Description: {description}

PDF content:
{pdf_text}

Task 1 - STACK: A clean comma-separated list of required programming languages, frameworks, and tools. Infer from context if not explicitly listed.
Task 2 - INSTRUCTIONS: 2-3 sentences summarizing the mandatory part. Start with an imperative verb (Implement, Build, Write, Create, Recode...). Be concrete about what gets built and the key constraints. Plain active voice only.

Respond in EXACTLY this format, nothing else:
STACK: lang1, lang2, tool3
INSTRUCTIONS: <your summary>

---
Example:
STACK: C, Makefile, Assembly
INSTRUCTIONS: Implement strlen, strcpy, strcmp, write, read and strdup in x86 Intel-syntax assembly, package them as libasm.a, and submit a test program with correct errno handling.
---

Now do it for the project above.\
"""


logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


def name_to_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def extract_pdf_text(pdf_path: Path, max_chars: int = 8000) -> str:
    full_text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    full_text += t + "\n"
                if len(full_text) >= max_chars:
                    break
    except Exception as exc:
        log.error(f"  PDF parse error ({pdf_path.name}): {exc}")
        return ""
    return full_text[:max_chars]


def parse_md_table(text: str) -> tuple[list[str], list[dict]]:
    lines = [ln for ln in text.splitlines() if ln.startswith("|")]
    if len(lines) < 3:
        raise ValueError("No table found.")
    headers = [h.strip() for h in lines[0].strip("|").split("|")]
    rows = []
    for line in lines[2:]:
        safe = line.replace("\\|", "\x00")
        cells = [c.strip().replace("\x00", "|") for c in safe.strip("|").split("|")]
        while len(cells) < len(headers):
            cells.append("")
        rows.append(dict(zip(headers, cells[:len(headers)])))
    return headers, rows


def build_md_table(headers: list[str], rows: list[dict]) -> str:
    sep = "|" + "|".join("-" * (len(h) + 2) for h in headers) + "|"
    header_line = "| " + " | ".join(headers) + " |"
    data_lines = [
        "| " + " | ".join(row.get(h, "").replace("|", "\\|") for h in headers) + " |"
        for row in rows
    ]
    return "\n".join([header_line, sep] + data_lines) + "\n"


def call_ollama(prompt: str) -> str:
    resp = requests.post(
        OLLAMA_ENDPOINT,
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": OLLAMA_TEMPERATURE},
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


def parse_response(text: str) -> tuple[str, str] | None:
    stack = None
    instructions = None
    for line in text.splitlines():
        if line.startswith("STACK:") and stack is None:
            stack = line[len("STACK:"):].strip()
        elif line.startswith("INSTRUCTIONS:") and instructions is None:
            instructions = line[len("INSTRUCTIONS:"):].strip()
    if stack and instructions:
        return stack, instructions
    return None


def process_row(row: dict, pdf_text: str) -> tuple[str, str] | None:
    prompt = PROMPT_TEMPLATE.format(
        name=row.get("Name", ""),
        description=row.get("Description", ""),
        pdf_text=pdf_text,
    )
    for attempt in range(2):
        try:
            response = call_ollama(prompt)
            result = parse_response(response)
            if result:
                return result
            if attempt == 0:
                log.warning("  Parse failed, retrying...")
        except Exception as exc:
            if attempt == 0:
                log.warning(f"  Error: {exc}, retrying...")
            else:
                raise
    return None


def load_checkpoint() -> dict:
    if CHECKPOINT_FILE.exists():
        return json.loads(CHECKPOINT_FILE.read_text())
    return {}


def save_checkpoint(checkpoint: dict) -> None:
    CHECKPOINT_FILE.write_text(json.dumps(checkpoint, indent=2))


def log_failure(name: str, reason: str) -> None:
    log.error(f"  FAILED: {reason}")


def main(overwrite: bool = False, limit: int | None = None, model: str | None = None, out_dir: str | None = None) -> None:
    global OLLAMA_MODEL, OUTPUT_DIR, PDF_DIR, INPUT_FILE, OUTPUT_FILE, CHECKPOINT_FILE
    if model:
        OLLAMA_MODEL = model
    if out_dir:
        OUTPUT_DIR = Path(out_dir)
        PDF_DIR = OUTPUT_DIR / "pdfs"
        INPUT_FILE = OUTPUT_DIR / "projects.md"
        OUTPUT_FILE = OUTPUT_DIR / "enhanced.md"
        CHECKPOINT_FILE = OUTPUT_DIR / "processed.json"
    output_path = INPUT_FILE if overwrite else OUTPUT_FILE

    if not INPUT_FILE.exists():
        log.error(f"ERROR: {INPUT_FILE} not found. Run scraper.py first.")
        return

    text = INPUT_FILE.read_text(encoding="utf-8")
    headers, rows = parse_md_table(text)

    if "Name" not in headers:
        log.error("ERROR: Expected column 'Name' not found in table.")
        return

    if limit is not None:
        rows = rows[:limit]

    checkpoint = load_checkpoint()
    log.info(f"Enhancing {len(rows)} projects with AI ({OLLAMA_MODEL})...")
    log.info(f"{len(checkpoint)} already processed.\n")

    for i, row in enumerate(rows):
        name = row.get("Name", f"row {i + 1}")

        if name in checkpoint and "instructions" in checkpoint[name]:
            log.info(f"[{i + 1}/{len(rows)}] {name} skipped (already done)")
            row["Stack"] = checkpoint[name]["stack"]
            row["Instructions"] = checkpoint[name]["instructions"]
            continue

        log.info(f"[{i + 1}/{len(rows)}] {name} ...")

        slug = name_to_slug(name)
        pdf_path = PDF_DIR / f"{slug}.subject.pdf"

        if not pdf_path.exists():
            log.warning(f"  No PDF found for '{name}' (tried {pdf_path.name}), skipping.")
            row["Stack"] = "N/A"
            row["Instructions"] = "N/A"
            continue

        pdf_text = extract_pdf_text(pdf_path)
        if not pdf_text:
            log.warning(f"  Empty PDF for '{name}', skipping.")
            row["Stack"] = "N/A"
            row["Instructions"] = "N/A"
            continue

        try:
            result = process_row(row, pdf_text)
        except Exception as exc:
            log_failure(name, str(exc))
            row["Stack"] = "N/A"
            row["Instructions"] = "N/A"
            continue

        if result is None:
            log_failure(name, "could not parse response after retry")
            row["Stack"] = "N/A"
            row["Instructions"] = "N/A"
            continue

        stack, instructions = result
        row["Stack"] = stack
        row["Instructions"] = instructions

        checkpoint[name] = {"stack": stack, "instructions": instructions}
        save_checkpoint(checkpoint)

        log.info(f"  Stack: {stack[:80]}")
        log.info(f"  Instructions: {instructions[:80]}...")
        time.sleep(DELAY)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_md_table(OUTPUT_HEADERS, rows), encoding="utf-8")
    log.info(f"Saved: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    #parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing table")
    parser.add_argument("--limit", type=int, default=None, help="Limit to first N projects")
    parser.add_argument("--model", type=str, default=None, help="Ollama model to use (overrides OLLAMA_MODEL)")
    parser.add_argument("--out", type=str, default=None, help="Output directory (default: output/)")
    args = parser.parse_args()
    main(overwrite=args.overwrite, limit=args.limit, model=args.model, out_dir=args.out)
