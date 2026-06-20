#!/usr/bin/env python3

'''
File: main.py
Repo: https://github.com/jeromeberg/42-projects-scraper
Author: Jerome Berg
Date: 2026/06/21
'''

import argparse
from scraper import main as run_scraper
from enhance import main as run_enhance

def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape projects from 42 intra.")
    #parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose mode")
    parser.add_argument("--limit", type=int, default=None, help="Limit to first N projects")
    parser.add_argument("--all", action="store_true", help="Scrape all 42cursus projects")
    parser.add_argument("--sort", choices=["name", "duration", "xp"], default=None, help="Sort order")
    parser.add_argument("--pdfs-only", action="store_true", help="Only download PDFs")
    parser.add_argument("--enhance", action="store_true", help="Run AI enhancement after scraping")
    parser.add_argument("--overwrite", action="store_true", help="Enhancement overwrites existing table")
    parser.add_argument("--model", type=str, default=None, help="Ollama model to use (overrides OLLAMA_MODEL)")
    parser.add_argument("--out", type=str, default=None, help="Output directory (default: output/)")
    args = parser.parse_args()

    run_scraper(pdfs_only=args.pdfs_only, all_projects=args.all, sort=args.sort, limit=args.limit, out_dir=args.out)

    if args.enhance and not args.pdfs_only:
        run_enhance(overwrite=args.overwrite, limit=args.limit, model=args.model, out_dir=args.out)


if __name__ == "__main__":
    main()
