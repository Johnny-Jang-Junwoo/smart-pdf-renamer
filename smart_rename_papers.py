#!/usr/bin/env python3
"""
Smart PDF Renamer using DOI and Crossref

What it does:
  1) Scans the first pages of a PDF to find a Digital Object Identifier (DOI).
  2) Uses the DOI to look up the paper's metadata (Title, Author, Publisher) on Crossref.org.
  3) Falls back to the PDF's embedded metadata if a DOI is not found.
  4) Renames files to: "Publisher - Title - INITIALS.pdf"

Quick start:
  pip install pymupdf requests
  python smart_rename_papers_doi.py "/path/to/folder" --recursive --dry-run
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from urllib.parse import quote

import fitz  # PyMuPDF
import requests

# -------------------- Utilities --------------------

INVALID_CHARS = r'<>:"/\\|?*'
REPLACEMENT = ' '

def sanitize(text: str) -> str:
    if not isinstance(text, str):
        text = str(text) if text is not None else ''
    for ch in INVALID_CHARS:
        text = text.replace(ch, REPLACEMENT)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def truncate_filename(name: str, max_len: int = 180) -> str:
    if len(name) <= max_len:
        return name
    return name[:max_len].rstrip()

def safe_rename(path: Path, new_name: str, dry_run: bool = False) -> Path:
    target = path.with_name(new_name)
    if target == path:
        return target
    if target.exists():
        stem, suf = target.stem, target.suffix
        i = 1
        while True:
            cand = path.with_name(f"{stem} ({i}){suf}")
            if not cand.exists():
                target = cand
                break
            i += 1
    if not dry_run:
        path.rename(target)
    return target

def to_initials(name: str) -> str:
    if not name:
        return "NA"
    name = re.sub(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Za-z]{2,}\b', ' ', name)
    name = re.sub(r'\bORCID\b[:\s]*\S+', ' ', name, flags=re.I)
    tokens = re.split(r'[\s\-]+', name.strip())
    initials = [t[0] for t in tokens if t and t[0].isalpha()]
    return ''.join(initials).upper() if initials else "NA"

# -------------------- Data Extraction --------------------

DOI_PATTERN = re.compile(r'10\.\d{4,9}/[-._;()/:A-Z0-9]+', re.I)

def extract_visible_text(doc: fitz.Document, max_pages: int = 2) -> str:
    text = []
    for i in range(min(max_pages, doc.page_count)):
        try:
            text.append(doc.load_page(i).get_text())
        except Exception:
            continue
    return '\n'.join(text)

def find_doi(text: str) -> Optional[str]:
    m = DOI_PATTERN.search(text or '')
    if not m:
        return None
    return m.group(0).rstrip(').,;]}>')

def query_crossref_by_doi(doi: str, email: Optional[str] = None) -> Dict:
    url = f'https://api.crossref.org/works/{quote(doi)}'
    headers = {'User-Agent': f'paper-renamer/1.0 (mailto:{email})' if email else 'paper-renamer/1.0'}
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()
    return data.get('message', {})

# -------------------- Compose name --------------------

def compose_name(publisher: Optional[str], title: Optional[str], first_author: Optional[str]) -> str:
    pub = sanitize(publisher or 'Unknown Publisher')
    ttl = sanitize(title or 'Untitled')
    auth_initials = to_initials(first_author or 'Unknown Author')
    return truncate_filename(f"{pub} - {ttl} - {auth_initials}.pdf")

# -------------------- Main processing --------------------

def process_pdf(pdf_path: Path, local_only: bool = False, email: Optional[str] = None) -> Tuple[str, str, str]:
    log = []
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        raise RuntimeError(f"Cannot open PDF: {e}")

    text_first = extract_visible_text(doc, max_pages=2)
    title, first_author, publisher = None, None, None

    # 1) Primary Method: Crossref DOI (unless local-only)
    if not local_only:
        try:
            doi = find_doi(text_first)
            if doi:
                log.append(f"found DOI {doi}")
                msg = query_crossref_by_doi(doi, email=email)
                if not title and msg.get('title'):
                    title = msg['title'][0]
                    log.append("title from Crossref")
                if not first_author and msg.get('author'):
                    a0 = msg['author'][0]
                    first_author = ' '.join([a0.get('given',''), a0.get('family','')]).strip()
                    log.append("author from Crossref")
                if not publisher and msg.get('publisher'):
                    publisher = msg['publisher']
                    log.append("publisher from Crossref")
        except Exception as e:
            log.append(f"Crossref failed: {e}")

    # 2) Fallback: Embedded PDF metadata
    if not all([title, first_author]):
        meta = doc.metadata or {}
        if not title and meta.get('title'):
            title = meta['title'].strip()
            log.append("title from embedded metadata")
        if not first_author and meta.get('author'):
            first_author = meta['author'].strip()
            log.append("author from embedded metadata")

    # 3) Final fallbacks
    if not title:
        title = pdf_path.stem
        log.append("fallback: title from filename")
    if not first_author:
        first_author = "Unknown Author"
        log.append("fallback: unknown author")
    if not publisher:
        publisher = "Unknown Publisher"
        log.append("fallback: unknown publisher")

    new_name = compose_name(publisher, title, first_author)
    doc.close()

    return pdf_path.name, new_name, '; '.join(log) or 'ok'

def gather_pdfs(inputs: List[Path], recursive: bool) -> List[Path]:
    pdfs: List[Path] = []
    for inp in inputs:
        if inp.is_file() and inp.suffix.lower() == '.pdf':
            pdfs.append(inp)
        elif inp.is_dir():
            globber = '**/*.pdf' if recursive else '*.pdf'
            pdfs.extend(sorted(inp.glob(globber)))
    return pdfs

def main():
    ap = argparse.ArgumentParser(description="Rename PDFs using DOI to Crossref lookup, with metadata fallback.")
    ap.add_argument('inputs', nargs='+', type=Path, help='PDF files and/or folders')
    ap.add_argument('--recursive', '-r', action='store_true', help='Scan folders recursively')
    ap.add_argument('--dry-run', action='store_true', help="Preview changes without renaming")
    ap.add_argument('--local-only', action='store_true', help="Do not query Crossref; use only local metadata")
    ap.add_argument('--email', type=str, default=None, help='Contact email for Crossref User-Agent (optional)')
    args = ap.parse_args()

    pdfs = gather_pdfs(args.inputs, args.recursive)
    if not pdfs:
        print("No PDFs found.", file=sys.stderr)
        sys.exit(2)

    renamed = 0
    print(f"Found {len(pdfs)} PDF(s). Processing...\n")
    for p in pdfs:
        try:
            src_name, new_name, why = process_pdf(
                p,
                local_only=args.local_only,
                email=args.email,
            )
            if src_name == new_name:
                print(f"[SKIP] {src_name}  (already named correctly)  |  {why}")
            elif args.dry_run:
                print(f"[DRY] {src_name}  →  {new_name}  |  {why}")
            else:
                target = safe_rename(p, new_name, dry_run=False)
                print(f"[OK ] {src_name}  →  {target.name}  |  {why}")
                renamed += 1
        except Exception as e:
            print(f"[ERR] {p.name}: {e}", file=sys.stderr)

    if not args.dry_run:
        print(f"\nDone. Renamed {renamed} file(s).")

if __name__ == '__main__':
    main()