#!/usr/bin/env python3
"""
Parse Control Yuan property declaration PDFs into structured JSON.
Each PDF may contain multiple persons' 公職人員財產申報表 and 變動財產申報表.
"""

import glob
import json
import os
import re
import subprocess
import sys

import pandas as pd
import tabula


def clean_text(text):
    if pd.isna(text):
        return ""
    return re.sub(r'\s+', ' ', str(text).replace('\r', ' ')).strip()


def normalize_header(text):
    return re.sub(r'\s+', '', clean_text(text))


def is_header_table(df):
    if df.shape[1] < 4:
        return False
    first_cell = normalize_header(df.iloc[0, 0])
    return '申報人姓名' in first_cell


def is_political_donation_table(df):
    if df.shape[0] < 2:
        return False
    first_cell = normalize_header(df.iloc[0, 0])
    return '收支科目' in first_cell


def is_empty_section(df):
    for _, row in df.iterrows():
        for val in row:
            if '本欄空白' in str(val):
                return True
    return False


def drop_nan_columns(df):
    return df.dropna(axis=1, how='all')


def classify_table(df):
    df = drop_nan_columns(df)
    if df.empty or df.shape[0] == 0:
        return 'unknown', df

    headers = [normalize_header(df.iloc[0, i]) for i in range(df.shape[1])]
    joined = ''.join(headers)

    if '申報人姓名' in joined:
        return 'header', df

    if '土地坐落' in joined or ('土地' in joined and '坐落' in joined):
        if '變動時間' in joined or '變動原因' in joined:
            return 'change_land', df
        return 'land', df

    if '建物標示' in joined or ('建物' in joined and '標示' in joined):
        if '變動時間' in joined or '變動原因' in joined:
            return 'change_buildings', df
        return 'buildings', df

    if '總噸數' in joined or '船籍港' in joined:
        return 'vessels', df

    if '廠牌' in joined or ('汽缸' in joined and '容量' in joined):
        return 'vehicles', df

    if '製造廠' in joined or '航空器' in joined:
        return 'aircraft', df

    if '幣別' in joined and '外幣總額' not in joined and df.shape[1] <= 5:
        return 'cash', df

    if '存放機構' in joined or '分支機構' in joined:
        return 'deposits', df

    if ('名稱' in headers[0] or '名' in headers[0]) and '股數' in joined and '變動' not in joined:
        return 'stocks', df

    if ('名稱' in headers[0] or '名' in headers[0]) and '股數' in joined and '變動' in joined:
        return 'change_stocks', df

    if '代碼' in joined and '買賣機構' in joined:
        return 'bonds', df

    if '受託投資機構' in joined:
        return 'funds', df

    if '財產種類' in joined or '珠寶' in joined:
        return 'jewelry_antiques', df

    if '保險公司' in joined or '保單號碼' in joined:
        return 'insurance', df

    if '虛擬資產' in joined or ('錢包' in joined and '帳戶' in joined):
        return 'virtual_assets', df

    if '債權人' in joined and '債務' not in headers[0] if headers else True:
        return 'credits', df

    if '債務人' in joined or ('債務' in joined and '種類' in joined):
        return 'debts', df

    if '投資人' in joined and '事業名稱' in joined:
        return 'business_investments', df

    if '單位數' in joined and '價額' in joined:
        return 'other_securities', df

    if '備註' in joined or '備' in joined and df.shape[1] <= 2:
        return 'notes', df

    return 'unknown', df


def parse_header_table(df):
    result = {}
    df = drop_nan_columns(df)

    # Row 0: [申報人姓名, name, 服務機關, 1.agency, 職稱, 1.title]
    # Row 1: [nan, 2.agency, 2.title, ...]  (if multiple agencies)
    # Row 2: [申報日, date, 申報類別/變動期間, type/period, ...]
    # Row 3+: family header then data rows

    # Find key columns by scanning row 0
    name_col = agency_col = title_col = -1
    for j in range(df.shape[1]):
        h = normalize_header(df.iloc[0, j])
        if '申報人姓名' in h:
            name_col = j
        elif '服務機關' in h:
            agency_col = j
        elif '職稱' in h:
            title_col = j

    if name_col >= 0 and name_col + 1 < df.shape[1]:
        result['name'] = clean_text(df.iloc[0, name_col + 1])

    # Collect all numbered items (1.xxx, 2.xxx) from row 0 and continuation rows
    numbered_items = []
    for i in range(min(3, df.shape[0])):
        for j in range(df.shape[1]):
            val = clean_text(df.iloc[i, j])
            m = re.match(r'^(\d+)\.(.+)', val)
            if m:
                numbered_items.append((int(m.group(1)), m.group(2), i, j))

    # In row 0, items at agency_col+1 are agencies, at title_col+1 are titles
    # In continuation rows, items appear left-to-right as agency then title
    agencies = []
    titles = []

    if agency_col >= 0 and title_col >= 0:
        # Row 0: identify by column position
        row0_agency_col = None
        row0_title_col = None
        for num, text, row, col in numbered_items:
            if row == 0:
                if col == agency_col + 1 or col == agency_col:
                    agencies.append((num, text))
                    row0_agency_col = col
                elif col == title_col + 1 or col == title_col:
                    titles.append((num, text))
                    row0_title_col = col

        # Continuation rows: items appear in column order, alternating agency/title
        for row_idx in range(1, min(3, df.shape[0])):
            row_items = sorted([(num, text, col) for num, text, r, col in numbered_items if r == row_idx], key=lambda x: x[2])
            for idx, (num, text, col) in enumerate(row_items):
                if idx % 2 == 0:
                    agencies.append((num, text))
                else:
                    titles.append((num, text))

    agencies = [t for _, t in sorted(agencies)]
    titles = [t for _, t in sorted(titles)]

    # Fallback: if no numbered entries found, grab raw values
    if not agencies and agency_col >= 0 and agency_col + 1 < df.shape[1]:
        v = clean_text(df.iloc[0, agency_col + 1])
        if v:
            agencies = [v]
    if not titles and title_col >= 0 and title_col + 1 < df.shape[1]:
        v = clean_text(df.iloc[0, title_col + 1])
        if v:
            titles = [v]

    result['agency'] = agencies if len(agencies) > 1 else (agencies[0] if agencies else '')
    result['title'] = titles if len(titles) > 1 else (titles[0] if titles else '')

    # Row 2: date and type/period
    for i in range(min(4, df.shape[0])):
        row_norm = normalize_header(' '.join([str(df.iloc[i, j]) for j in range(df.shape[1])]))
        if '申報日' not in row_norm and '變動期間' not in row_norm:
            continue
        for j in range(df.shape[1]):
            val = clean_text(df.iloc[i, j])
            h = normalize_header(df.iloc[i, j]) if not pd.isna(df.iloc[i, j]) else ''
            if '申報日' in h:
                if j + 1 < df.shape[1]:
                    result['date'] = clean_text(df.iloc[i, j + 1])
            if '申報類別' in h:
                if j + 1 < df.shape[1]:
                    result['type'] = clean_text(df.iloc[i, j + 1])
            if '變動期間' in h:
                result['report_kind'] = 'change'
                if j + 1 < df.shape[1]:
                    result['period'] = clean_text(df.iloc[i, j + 1])
                # Also grab the date from the same row
                for k in range(df.shape[1]):
                    hk = normalize_header(df.iloc[i, k]) if not pd.isna(df.iloc[i, k]) else ''
                    if '申報日' in hk and k + 1 < df.shape[1]:
                        result['date'] = clean_text(df.iloc[i, k + 1])

    if 'report_kind' not in result:
        result['report_kind'] = 'declaration'

    family = []
    for i in range(df.shape[0]):
        row_vals = [clean_text(df.iloc[i, j]) for j in range(df.shape[1])]
        for j, val in enumerate(row_vals):
            if val in ('配偶', '未成年子女') and j + 1 < len(row_vals):
                name = row_vals[j + 1]
                if name and normalize_header(name) not in ('姓名', '稱謂', ''):
                    family.append({'relation': val, 'name': name})
    result['family'] = family

    return result


def rows_to_dicts(df):
    df = drop_nan_columns(df)
    if df.shape[0] < 2:
        return []

    headers = [clean_text(df.iloc[0, j]) for j in range(df.shape[1])]

    if is_empty_section(df):
        return []

    rows = []
    for i in range(1, df.shape[0]):
        row = {}
        all_empty = True
        for j in range(df.shape[1]):
            val = clean_text(df.iloc[i, j])
            if val and val != '本欄空白':
                all_empty = False
            key = headers[j] if headers[j] else f'col_{j}'
            key = re.sub(r'\s+', '', key)
            row[key] = val
        if not all_empty:
            rows.append(row)

    return rows


def can_concat(prev_df, curr_df):
    prev_df = drop_nan_columns(prev_df)
    curr_df = drop_nan_columns(curr_df)
    if prev_df.shape[1] != curr_df.shape[1]:
        return False
    first_cell = normalize_header(curr_df.iloc[0, 0])
    if any(kw in first_cell for kw in ['申報人', '土地', '建物', '種類', '廠牌', '型式',
                                         '幣別', '存放', '名稱', '財產', '保險', '投資',
                                         '債權', '債務']):
        return False
    return True


def split_into_persons(tables):
    persons = []
    current = []
    for t in tables:
        if is_header_table(t):
            if current:
                persons.append(current)
            current = [t]
        else:
            if current:
                current.append(t)
    if current:
        persons.append(current)
    return persons


def merge_continuation_tables(tables):
    merged = []
    for t in tables:
        if merged and can_concat(merged[-1], t):
            merged[-1] = pd.concat([merged[-1], t], ignore_index=True)
        else:
            merged.append(t)
    return merged


def parse_person_tables(tables):
    if not tables:
        return None

    tables = merge_continuation_tables(tables)

    header_info = parse_header_table(tables[0])

    sections = {}
    for t in tables[1:]:
        ttype, cleaned = classify_table(t)
        if ttype == 'unknown':
            continue
        if ttype == 'header':
            continue

        data = rows_to_dicts(cleaned)
        if ttype in sections and data:
            sections[ttype].extend(data)
        else:
            sections[ttype] = data

    result = {
        'name': header_info.get('name', ''),
        'agency': header_info.get('agency', ''),
        'title': header_info.get('title', ''),
        'date': header_info.get('date', ''),
        'type': header_info.get('type', ''),
        'report_kind': header_info.get('report_kind', 'declaration'),
        'family': header_info.get('family', []),
    }

    if header_info.get('period'):
        result['period'] = header_info['period']

    section_keys = [
        'land', 'buildings', 'vessels', 'vehicles', 'aircraft',
        'cash', 'deposits', 'stocks', 'bonds', 'funds',
        'other_securities', 'jewelry_antiques', 'insurance',
        'virtual_assets', 'credits', 'debts', 'business_investments',
        'notes', 'change_land', 'change_buildings', 'change_stocks',
    ]
    for key in section_keys:
        result[key] = sections.get(key, [])

    return result


def merge_person_reports(persons):
    merged = []
    i = 0
    while i < len(persons):
        p = persons[i]
        if i + 1 < len(persons):
            nxt = persons[i + 1]
            if p.get('name') == nxt.get('name'):
                if p.get('report_kind') == 'declaration' and nxt.get('report_kind') == 'change':
                    combined = {
                        'name': p['name'],
                        'agency': p['agency'],
                        'title': p['title'],
                        'declaration': {k: v for k, v in p.items() if k not in ('name', 'agency', 'title', 'report_kind')},
                        'change_report': {k: v for k, v in nxt.items() if k not in ('name', 'agency', 'title', 'report_kind')},
                    }
                    merged.append(combined)
                    i += 2
                    continue
                elif p.get('report_kind') == 'change' and nxt.get('report_kind') == 'declaration':
                    combined = {
                        'name': p['name'],
                        'agency': nxt['agency'],
                        'title': nxt['title'],
                        'declaration': {k: v for k, v in nxt.items() if k not in ('name', 'agency', 'title', 'report_kind')},
                        'change_report': {k: v for k, v in p.items() if k not in ('name', 'agency', 'title', 'report_kind')},
                    }
                    merged.append(combined)
                    i += 2
                    continue

        if p.get('report_kind') == 'declaration':
            merged.append({
                'name': p['name'],
                'agency': p['agency'],
                'title': p['title'],
                'declaration': {k: v for k, v in p.items() if k not in ('name', 'agency', 'title', 'report_kind')},
            })
        else:
            merged.append({
                'name': p['name'],
                'agency': p['agency'],
                'title': p['title'],
                'change_report': {k: v for k, v in p.items() if k not in ('name', 'agency', 'title', 'report_kind')},
            })
        i += 1

    return merged


def parse_political_donation_table(df):
    df = drop_nan_columns(df)
    result = {'income': {}, 'expense': {}, 'adjustment': {}, 'summary': {}}
    section = None

    for i in range(1, df.shape[0]):
        col0 = clean_text(df.iloc[i, 0])
        col1 = clean_text(df.iloc[i, 1])
        col2 = clean_text(df.iloc[i, 2])

        if '收' in col0 and '入' in col0:
            section = 'income'
        elif '支' in col0 and '出' in col0:
            section = 'expense'
        elif '調' in col0 and '整' in col0:
            section = 'adjustment'

        if section and col1 and col2:
            result[section][col1] = col2

        # Grab summary fields from later columns
        for j in range(3, df.shape[1]):
            val = clean_text(df.iloc[i, j])
            if val:
                for part in val.split('\r'):
                    part = part.strip()
                    if ':' in part or '：' in part:
                        k, _, v = part.partition(':') if ':' in part else part.partition('：')
                        result['summary'][k.strip()] = v.strip()

        if '餘額' in col1:
            result['summary']['餘額'] = col2

    return result


def detect_pdf_type(tables):
    has_property = any(is_header_table(t) for t in tables)
    has_political = any(is_political_donation_table(t) for t in tables)
    if has_property:
        return 'property'
    if has_political:
        return 'political'
    return None


def process_pdf(pdf_path):
    try:
        tables = tabula.read_pdf(
            pdf_path,
            pages='all',
            multiple_tables=True,
            lattice=True,
            pandas_options={'header': None},
        )
    except Exception as e:
        print(f"  Error reading PDF: {e}")
        return None, None

    if not tables:
        return None, None

    pdf_type = detect_pdf_type(tables)

    if pdf_type == 'property':
        person_groups = split_into_persons(tables)
        persons = []
        for group in person_groups:
            parsed = parse_person_tables(group)
            if parsed and parsed.get('name'):
                persons.append(parsed)
        if not persons:
            return None, None
        return 'property', merge_person_reports(persons)

    if pdf_type == 'political':
        reports = []
        for t in tables:
            if is_political_donation_table(t):
                reports.append(parse_political_donation_table(t))
        if not reports:
            return None, None
        return 'political', reports

    return None, None


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    downloads_dir = os.path.join(project_dir, 'downloads')
    property_dir = os.path.join(project_dir, 'json', 'property')
    political_dir = os.path.join(project_dir, 'json', 'political')

    os.makedirs(property_dir, exist_ok=True)
    os.makedirs(political_dir, exist_ok=True)

    if len(sys.argv) > 1:
        pdf_files = [os.path.join(downloads_dir, f) for f in sys.argv[1:]]
    else:
        pdf_files = sorted(glob.glob(os.path.join(downloads_dir, '*.pdf')))

    missing_csv = os.path.join(script_dir, 'missing.csv')

    total = len(pdf_files)
    processed = 0
    skipped = 0
    missing = []

    for idx, pdf_path in enumerate(pdf_files, 1):
        stem = os.path.splitext(os.path.basename(pdf_path))[0]
        property_path = os.path.join(property_dir, f'{stem}.json')
        political_path = os.path.join(political_dir, f'{stem}.json')

        if os.path.exists(property_path) or os.path.exists(political_path):
            print(f'[{idx}/{total}] SKIP (exists): {stem}')
            skipped += 1
            continue

        print(f'[{idx}/{total}] Processing: {stem}...', end=' ', flush=True)
        pdf_type, result = process_pdf(pdf_path)

        if result is None:
            parts = stem.split('_')
            issue = parts[0]
            date = parts[1] if len(parts) > 1 else ''
            pages = ''
            try:
                r = subprocess.run(['pdfinfo', pdf_path], capture_output=True, text=True)
                for line in r.stdout.split('\n'):
                    if 'Pages' in line:
                        pages = line.split()[-1]
            except Exception:
                pass
            missing.append((stem, issue, date, pages))
            print('no data found (TOC only)')
            skipped += 1
            continue

        if pdf_type == 'property':
            with open(property_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f'property: {len(result)} persons')
        elif pdf_type == 'political':
            with open(political_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f'political: {len(result)} reports')

        processed += 1

    if missing:
        with open(missing_csv, 'w', encoding='utf-8') as f:
            f.write('filename,issue,date,pages\n')
            for stem, issue, date, pages in missing:
                f.write(f'{stem}.pdf,{issue},{date},{pages}\n')
        print(f'\nWrote {len(missing)} TOC-only entries to {missing_csv}')

    print(f'\nDone. Processed: {processed}, Skipped (TOC/exists): {skipped}, Total: {total}')


if __name__ == '__main__':
    main()
