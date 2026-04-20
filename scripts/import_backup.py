#!/usr/bin/env python3
"""
Replace TOC-only PDFs in downloads/ with complete versions from backup.
Matches by issue number; replaces when the backup file is larger.
"""

import glob
import os
import re
import shutil


DOWNLOADS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'downloads')
BACKUP = os.path.expanduser('~/下載/ardata_doc-20260420T085857Z-3-001/ardata_doc')


def main():
    existing = {}
    for f in glob.glob(os.path.join(DOWNLOADS, '*.pdf')):
        issue = os.path.basename(f).split('_')[0]
        existing[issue] = f

    backup_files = {}
    for f in os.listdir(BACKUP):
        m = re.search(r'第(\d+)期', f)
        if m:
            backup_files[m.group(1)] = os.path.join(BACKUP, f)

    replaced = 0
    for issue in sorted(backup_files.keys(), key=int):
        if issue not in existing:
            continue
        src = backup_files[issue]
        dst = existing[issue]
        if os.path.getsize(src) <= os.path.getsize(dst):
            continue
        shutil.copy2(src, dst)
        print(f'REPLACED {os.path.basename(dst)} ({os.path.getsize(dst) // 1024}KB)')
        replaced += 1

    print(f'\nReplaced: {replaced}')


if __name__ == '__main__':
    main()
