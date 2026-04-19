#!/usr/bin/env python3
"""
One-time script: replace TOC-only PDFs in downloads/ with full versions
from the backup at ~/下載/sunshine.cy-master/data/pdf/journal/
"""

import glob
import os
import re
import shutil

DOWNLOADS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'downloads')
BACKUP = os.path.expanduser('~/下載/sunshine.cy-master/data/pdf/journal')
PROPERTY_DIR = os.path.join(os.path.dirname(DOWNLOADS), 'json', 'property')
POLITICAL_DIR = os.path.join(os.path.dirname(DOWNLOADS), 'json', 'political')


def main():
    backup_files = {}
    for f in os.listdir(BACKUP):
        m = re.search(r'第([\d-]+)期', f)
        if m:
            backup_files[m.group(1)] = os.path.join(BACKUP, f)

    replaced = 0
    for pdf_path in sorted(glob.glob(os.path.join(DOWNLOADS, '*.pdf'))):
        stem = os.path.splitext(os.path.basename(pdf_path))[0]

        if os.path.exists(os.path.join(PROPERTY_DIR, f'{stem}.json')):
            continue
        if os.path.exists(os.path.join(POLITICAL_DIR, f'{stem}.json')):
            continue

        issue = stem.split('_')[0]
        if issue not in backup_files:
            continue

        backup_path = backup_files[issue]
        old_size = os.path.getsize(pdf_path)
        new_size = os.path.getsize(backup_path)

        if new_size <= old_size:
            print(f'SKIP {stem}: backup not larger ({new_size} <= {old_size})')
            continue

        shutil.copy2(backup_path, pdf_path)
        print(f'REPLACED {stem}.pdf: {old_size // 1024}KB -> {new_size // 1024}KB (from {os.path.basename(backup_path)})')
        replaced += 1

    print(f'\nReplaced {replaced} files.')


if __name__ == '__main__':
    main()
