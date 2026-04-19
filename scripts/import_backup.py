#!/usr/bin/env python3
"""
One-time script: import older reports from backup into downloads/
using the project's naming convention: {issue}_{date}_1.pdf
"""

import glob
import os
import re
import shutil
import subprocess
import unicodedata


DOWNLOADS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'downloads')
BACKUP = os.path.expanduser('~/下載/sunshine.cy-master/data/pdf/journal')


MANUAL_DATES = {
    '46': '101-11-22',
    '59': '102-11-29',
}


def extract_date(pdf_path, issue):
    if issue in MANUAL_DATES:
        return MANUAL_DATES[issue]

    result = subprocess.run(['pdftotext', pdf_path, '-'], capture_output=True, text=True)
    text = unicodedata.normalize('NFKC', result.stdout[:5000])
    normalized = re.sub(r'\s+', ' ', text)

    # Match "N 年 M 月 D 日 出 版" or typo "N 日 M 月 D 日出 版"
    m = re.search(r'(\d+)\s*[年日]\s*(\d+)\s*月\s*(\d+)\s*日\s*出\s*版', normalized)
    if m:
        return f'{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}'
    return None


def get_existing_issues():
    issues = set()
    for f in glob.glob(os.path.join(DOWNLOADS, '*.pdf')):
        issue = os.path.basename(f).split('_')[0]
        issues.add(issue)
    return issues


def main():
    existing = get_existing_issues()

    backup_files = {}
    for f in os.listdir(BACKUP):
        m = re.search(r'第([\d-]+)期', f)
        if m:
            backup_files[m.group(1)] = os.path.join(BACKUP, f)

    imported = 0
    skipped = 0

    for issue in sorted(backup_files.keys(), key=lambda x: int(x.split('-')[0])):
        if issue in existing:
            continue

        src = backup_files[issue]
        date = extract_date(src, issue)
        if not date:
            print(f'SKIP issue {issue}: could not extract date')
            skipped += 1
            continue

        # Handle combined issues like "16-17"
        filename = f'{issue}_{date}_1.pdf'
        dst = os.path.join(DOWNLOADS, filename)

        shutil.copy2(src, dst)
        size_kb = os.path.getsize(dst) // 1024
        print(f'IMPORTED {filename} ({size_kb}KB)')
        imported += 1

    print(f'\nImported: {imported}, Skipped: {skipped}')


if __name__ == '__main__':
    main()
