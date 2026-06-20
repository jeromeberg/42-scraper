#!/usr/bin/env python3

'''
File: scraper.py
Repo: https://github.com/jeromeberg/42-projects-scraper
Author: Jerome Berg
Date: 2026/06/21
'''

import argparse
import os
import re
import time
import logging
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://projects.intra.42.fr"
LIST_URL = f"{BASE_URL}/projects/list"
COOKIE = os.environ.get("INTRA_COOKIE", "")
DELAY = 0.5

OUTPUT_DIR = Path("output")
PDF_DIR = OUTPUT_DIR / "pdfs"
SUMMARY_FILE = OUTPUT_DIR / "projects.md"

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "Cookie": COOKIE,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:138.0) Gecko/20100101 Firefox/138.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })
    return session


SORT_MAP = {"name": "project-name", "duration": "project-duration", "xp": "project-xp"}


def scrape_project_list(session: requests.Session, all_projects: bool = False, sort: str | None = None, limit: int | None = None) -> list[dict]:
    projects: list[dict] = []
    page = 1
    filter_param = "cursus=42cursus" if all_projects else "filters=recommended-projects"
    sort_param = SORT_MAP.get(sort) if sort else None
    while True:
        url = f"{LIST_URL}?{filter_param}&page={page}"
        if sort_param:
            url += f"&sort={sort_param}"
        log.info(f"Fetching page {page} ...")
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("li.project-item")
        if not items:
            log.info(f"  No items on page {page}, stopping.")
            break
        for item in items:
            link = item.select_one(".project-name a")
            if not link:
                continue
            name = link.get_text(strip=True)
            href = link["href"]
            detail_url = BASE_URL + href if href.startswith("/") else href
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            duration_el = item.select_one(".project-duration")
            xp_el = item.select_one(".project-difficulty span")
            duration = duration_el.get_text(strip=True) if duration_el else ""
            xp = xp_el.get_text(strip=True) if xp_el else ""
            projects.append({"name": name, "slug": slug, "url": detail_url, "duration": duration, "xp": xp})
            if limit and len(projects) >= limit:
                return projects
        page += 1
        time.sleep(DELAY)
    return projects



def scrape_project_page(session: requests.Session, project: dict) -> tuple[str, str, str | None]:
    """Return (description_text, keywords, pdf_url_or_None)."""
    resp = session.get(project["url"], timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    description = ""
    keywords = ""
    desc_section = soup.select_one(".project-description")
    if desc_section:
        for item in desc_section.select(".project-desc-item"):
            h4 = item.select_one("h4")
            if h4 and h4.get_text(strip=True) == "Description":
                p = item.select_one("p")
                if p:
                    description = p.get_text(strip=True)
                break

        kw_header = desc_section.find("h4", string=re.compile(r"Keywords?", re.I))
        if kw_header:
            sibling = kw_header.find_next_sibling("p")
            if sibling:
                kws = [t.strip() for t in sibling.get_text(separator="\n").split("\n") if t.strip()]
                keywords = ", ".join(kws)

    pdf_url: str | None = None
    pdf_link = soup.select_one(".project-attachment-item .attachment-name a[href]")
    if pdf_link:
        href = pdf_link["href"]
        pdf_url = href if href.startswith("http") else BASE_URL + href

    return description, keywords, pdf_url


def download_pdf(session: requests.Session, pdf_url: str, pdf_path: Path) -> None:
    resp = session.get(pdf_url, timeout=60)
    resp.raise_for_status()
    pdf_path.write_bytes(resp.content)



def _md_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def build_markdown_table(rows: list[dict]) -> str:
    lines = [
        "| Name | Description | Keywords | XP | Duration |",
        "|------|-------------|----------|----|----------|",
    ]
    for r in rows:
        name = _md_cell(r.get("name", ""))
        desc = _md_cell(r.get("description", "N/A"))
        keywords = _md_cell(r.get("keywords", ""))
        xp = _md_cell(r.get("xp", ""))
        duration = _md_cell(r.get("duration", ""))
        lines.append(f"| {name} | {desc} | {keywords} | {xp} | {duration} |")
    return "\n".join(lines) + "\n"


def main(pdfs_only: bool = False, all_projects: bool = False, sort: str | None = None, limit: int | None = None, out_dir: str | None = None) -> None:
    global OUTPUT_DIR, PDF_DIR, SUMMARY_FILE
    if out_dir:
        OUTPUT_DIR = Path(out_dir)
        PDF_DIR = OUTPUT_DIR / "pdfs"
        SUMMARY_FILE = OUTPUT_DIR / "projects.md"

    if not COOKIE:
        log.error("ERROR: INTRA_COOKIE is not set. Add it to your .env file.")
        return

    PDF_DIR.mkdir(parents=True, exist_ok=True)

    session = make_session()

    log.info("=== Scraping project list ===")
    effective_limit = limit if limit is not None else None
    projects = scrape_project_list(session, all_projects=all_projects, sort=sort, limit=effective_limit)
    log.info(f"Found {len(projects)} projects.\n")

    summary_rows: list[dict] = []

    for idx, project in enumerate(projects, 1):
        name = project["name"]
        slug = project["slug"]
        log.info(f"[{idx}/{len(projects)}] {name}")

        pdf_path = PDF_DIR / f"{slug}.subject.pdf"

        description = "N/A"
        keywords = ""

        try:
            log.info("  Fetching project page ...")
            scraped_desc, keywords, pdf_url = scrape_project_page(session, project)
            if not pdfs_only:
                description = scraped_desc.strip() or "N/A"
            time.sleep(DELAY)

            if pdf_path.exists():
                log.info("  [SKIP] PDF already downloaded.")
            elif pdf_url:
                log.info(f"  Downloading PDF: {pdf_url}")
                download_pdf(session, pdf_url, pdf_path)
                log.info("  Saved PDF.")
                time.sleep(DELAY)
            else:
                log.info("  No PDF attachment found.")

        except requests.HTTPError as exc:
            log.error(f"  HTTP error: {exc}")
        except Exception as exc:
            log.error(f"  Error: {exc}")

        if not pdfs_only:
            summary_rows.append({
                "name": name,
                "keywords": keywords,
                "description": description,
                "duration": project.get("duration", ""),
                "xp": project.get("xp", ""),
            })
        log.info("")

    if pdfs_only:
        log.info("Done. Subjects saved to output/pdfs/")
        return

    log.info("=== Building summary table ===")
    md = build_markdown_table(summary_rows)
    SUMMARY_FILE.write_text(md, encoding="utf-8")
    log.info(f"Saved: {SUMMARY_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    #parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose mode")
    parser.add_argument("--limit", type=int, default=None, help="Limit to first N projects")
    parser.add_argument("--pdfs-only", action="store_true", help="Only download PDFs")
    parser.add_argument("--all", action="store_true", help="Scrape all 42cursus projects")
    parser.add_argument("--sort", choices=["name", "duration", "xp"], default=None, help="Sort order")
    parser.add_argument("--out", type=str, default=None, help="Output directory (default: output/)")
    args = parser.parse_args()
    main(pdfs_only=args.pdfs_only, all_projects=args.all, sort=args.sort, limit=args.limit, out_dir=args.out)
