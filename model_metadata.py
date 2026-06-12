#!/usr/bin/env python3
"""
update_ttl_metadata.py — Bulk TTL Metadata Updater
The Value Enablement Group, LLC

Makes the following changes across all .ttl and .rdf files:
  1. Replace verizon.com → enablingvalue.com (in URIs)
  2. Replace milsh69 → Jeffrey Wallk (in author/creator fields)
  3. Set dct:modified → current date/time
  4. Set dct:created → 2026-01-01T00:00:00Z

Usage:
    python3 update_ttl_metadata.py --dir /path/to/Knowledge-Artifacts
    python3 update_ttl_metadata.py --dir /path/to/Knowledge-Artifacts --dry-run

Options:
    --dir      Path to the root directory containing TTL/RDF files
    --dry-run  Preview changes without writing files
    --backup   Create .bak backup of each file before modifying (default: True)
"""

import os
import re
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime, timezone

# ── Configuration ──
REPLACEMENTS = [
    # 1. Namespace: verizon.com → enablingvalue.com
    (r'ontologies\.verizon\.com',             'ontologies.enablingvalue.com'),
    (r'taxonomies\.verizon\.com',             'taxonomies.enablingvalue.com'),
    (r'www\.verizon\.com',                    'www.enablingvalue.com'),
    (r'verizon\.com/',                         'enablingvalue.com/'),

    # 2. semanticweb.org/jeffrey → www.enablingvalue.com
    (r'www\.semanticweb\.org/jeffrey[^"\s]*', 'www.enablingvalue.com'),
    (r'semanticweb\.org/jeffrey[^"\s]*',       'www.enablingvalue.com'),

    # 3. Email: sherri.miller1@one.verizon.com → jeffrey.wallk@gmail.com
    (r'sherri\.miller1@one\.verizon\.com',   'jeffrey.wallk@gmail.com'),
    (r'sherri\.miller1@[^"\s]*',              'jeffrey.wallk@gmail.com'),

    # 4. Author: milsh69 → Jeffrey Wallk
    (r'\bmilsh69\b',                           'Jeffrey Wallk'),
    (r'"milsh69"',                              '"Jeffrey Wallk"'),

    # 5. Remove "Verizon's" (possessive) — replace with empty or generic
    (r"Verizon\'s\s+",                        ''),
    (r'Verizon\'s\s+',                        ''),
]

SUPPORTED = {'.ttl', '.rdf', '.owl', '.n3', '.trig', '.nq'}


def get_timestamps():
    """Return formatted timestamps for dct:modified and dct:created."""
    now = datetime.now(timezone.utc)
    modified = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    created  = '2026-01-01T00:00:00Z'
    return modified, created


def update_dct_dates(content: str, modified: str, created: str) -> str:
    """
    Update dct:modified, dct:created, dct:creator, dct:contributor.
    Handles both full xsd:dateTime and plain string literals.
    """

    # dct:modified
    content = re.sub(
        r'(dct:modified\s+)"[^"]*"(\^\^[^\s;,.]*)?',
        f'\\1"{modified}"^^<http://www.w3.org/2001/XMLSchema#dateTime>',
        content
    )
    content = re.sub(
        r'(dcterms:modified\s+)"[^"]*"(\^\^[^\s;,.]*)?',
        f'\\1"{modified}"^^<http://www.w3.org/2001/XMLSchema#dateTime>',
        content
    )

    # dct:created
    content = re.sub(
        r'(dct:created\s+)"[^"]*"(\^\^[^\s;,.]*)?',
        f'\\1"{created}"^^<http://www.w3.org/2001/XMLSchema#dateTime>',
        content
    )
    content = re.sub(
        r'(dcterms:created\s+)"[^"]*"(\^\^[^\s;,.]*)?',
        f'\\1"{created}"^^<http://www.w3.org/2001/XMLSchema#dateTime>',
        content
    )

    # dct:creator — replace any existing value
    content = re.sub(
        r'(dct:creator\s+)"[^"]*"',
        '\\1"Jeffrey Wallk"',
        content
    )
    content = re.sub(
        r'(dcterms:creator\s+)"[^"]*"',
        '\\1"Jeffrey Wallk"',
        content
    )

    # dct:contributor — replace any existing value
    content = re.sub(
        r'(dct:contributor\s+)"[^"]*"',
        '\\1"Jeffrey Wallk"',
        content
    )
    content = re.sub(
        r'(dcterms:contributor\s+)"[^"]*"',
        '\\1"Jeffrey Wallk"',
        content
    )

    return content


def process_file(filepath: Path, modified: str, created: str,
                 dry_run: bool = False, backup: bool = True) -> dict:
    """
    Process a single TTL/RDF file.
    Returns a summary dict of changes made.
    """
    try:
        original = filepath.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        return {'file': str(filepath), 'error': str(e), 'changes': 0}

    content = original

    # Apply text replacements
    change_count = 0
    details = []

    for pattern, replacement in REPLACEMENTS:
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            matches = len(re.findall(pattern, content))
            details.append(f"{pattern} → {replacement} ({matches}x)")
            change_count += matches
            content = new_content

    # Update date fields
    content_after_dates = update_dct_dates(content, modified, created)
    if content_after_dates != content:
        details.append(f"dct:modified → {modified}")
        details.append(f"dct:created → {created}")
        change_count += 1
        content = content_after_dates

    result = {
        'file':    str(filepath),
        'changes': change_count,
        'details': details
    }

    if change_count > 0 and not dry_run:
        # Backup original
        if backup:
            shutil.copy2(filepath, filepath.with_suffix(filepath.suffix + '.bak'))

        # Write updated content
        filepath.write_text(content, encoding='utf-8')
        result['written'] = True
    else:
        result['written'] = False

    return result


def main():
    parser = argparse.ArgumentParser(description='Bulk update TTL metadata')
    parser.add_argument('--dir',     required=True, help='Root directory of TTL files')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing')
    parser.add_argument('--no-backup', action='store_true', help='Skip .bak backup files')
    args = parser.parse_args()

    root = Path(args.dir).expanduser().resolve()
    if not root.exists():
        print(f"❌ Directory not found: {root}")
        sys.exit(1)

    dry_run = args.dry_run
    backup  = not args.no_backup
    modified, created = get_timestamps()

    print("=" * 60)
    print("  VEG TTL Metadata Updater")
    print("=" * 60)
    print(f"  Directory:    {root}")
    print(f"  Mode:         {'DRY RUN — no files written' if dry_run else 'LIVE — files will be updated'}")
    print(f"  Backup:       {'Yes (.bak)' if backup and not dry_run else 'No'}")
    print(f"  dct:modified: {modified}")
    print(f"  dct:created:  {created}")
    print()
    print("  Replacements:")
    print("    verizon.com              → enablingvalue.com")
    print("    semanticweb.org/jeffrey  → www.enablingvalue.com")
    print("    sherri.miller1@...       → jeffrey.wallk@gmail.com")
    print("    milsh69                  → Jeffrey Wallk")
    print("    Verizon's                → (removed)")
    print("    dct:creator              → Jeffrey Wallk")
    print("    dct:contributor          → Jeffrey Wallk")
    print("    dct:modified             → current timestamp")
    print("    dct:created              → 2026-01-01T00:00:00Z")
    print()

    # Find all supported files
    files = sorted([
        f for f in root.rglob('*')
        if f.is_file()
        and f.suffix.lower() in SUPPORTED
        and '.bak' not in f.suffixes
    ])

    if not files:
        print(f"⚠ No TTL/RDF files found in {root}")
        sys.exit(0)

    print(f"Found {len(files)} files\n")

    total_changes = 0
    total_files_changed = 0
    errors = []

    for filepath in files:
        result = process_file(filepath, modified, created, dry_run, backup)

        if 'error' in result:
            errors.append(result)
            print(f"  ✗ ERROR: {filepath.name} — {result['error']}")
            continue

        rel = filepath.relative_to(root)

        if result['changes'] > 0:
            status = '→' if dry_run else '✓'
            print(f"  {status} {rel} ({result['changes']} changes)")
            for d in result['details']:
                print(f"      {d}")
            total_changes += result['changes']
            total_files_changed += 1
        else:
            print(f"  · {rel} (no changes)")

    print()
    print("=" * 60)
    if dry_run:
        print(f"  DRY RUN complete: {total_files_changed} files would be updated")
        print(f"  {total_changes} total replacements pending")
        print(f"  Run without --dry-run to apply changes")
    else:
        print(f"  ✓ Complete: {total_files_changed}/{len(files)} files updated")
        print(f"  {total_changes} total replacements made")
        if backup:
            print(f"  Originals backed up as .bak files")

    if errors:
        print(f"  ✗ {len(errors)} errors:")
        for e in errors:
            print(f"    {e['file']}: {e['error']}")

    print("=" * 60)

    # After live run, remind about GraphDB reload
    if not dry_run and total_files_changed > 0:
        print()
        print("  NEXT STEP: Reload updated files into GraphDB")
        print("  1. Open http://localhost:7200")
        print("  2. Go to your Value-kb repository")
        print("  3. Import → RDF Files → Upload updated TTL files")
        print("  4. Or clear and reimport the entire directory")


if __name__ == '__main__':
    main()
