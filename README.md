# Smart PDF Renamer (DOI → Crossref)

Rename research PDFs to the format:

```
Publisher - Title - INITIALS.pdf
```

**How it works**
1. Reads the first page(s) and looks for a DOI.
2. Uses the DOI to fetch clean metadata from Crossref (Title, first author, Publisher/Journal).
3. Falls back to embedded PDF metadata if a DOI isn’t found.
4. Uses author **initials** in the filename.

## Quick start
```bash
pip install -r requirements.txt

# Dry-run (no changes)
python smart_rename_papers_doi.py "/path/to/folder" --recursive --dry-run

# Rename for real
python smart_rename_papers_doi.py "/path/to/folder" --recursive
```

**Tip (be polite to Crossref):**
```bash
python smart_rename_papers_doi.py "/path/to/folder" --recursive --email your.name@domain.com
```

## Options
- `--recursive` : scan subfolders too  
- `--dry-run`   : show what would happen, don’t rename  
- `--local-only`: skip Crossref (use only local metadata)  
- `--email`     : contact email for Crossref user‑agent (optional but recommended)

## Windows examples
```powershell
python smart_rename_papers_doi.py "C:\Users\#####\Documents\Papers" --recursive --dry-run
python smart_rename_papers_doi.py "C:\Users\#####\Documents\Papers" --recursive --email #####@####.###
```

## macOS/Linux examples
```bash
python smart_rename_papers_doi.py "/Users/you/Documents/Papers" --recursive --dry-run
python smart_rename_papers_doi.py "/Users/you/Documents/Papers" --recursive --email you@university.edu
```

## Notes
- Close any PDFs that are open in a viewer before renaming (on Windows this can block file moves).
- If a file already follows the correct name, it’s skipped.
- If a name collision happens, a suffix like `(1)` is added automatically.
- Scanned/image-only PDFs won’t expose a DOI unless OCR is used (not included here).

---

**License:** None
**Author:** Johnny Jang
