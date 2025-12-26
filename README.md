# CY Integrity Monthly Crawler

Automated crawler to download PDF/ZIP files from the Control Yuan (Taiwan) Sunshine Laws website - Integrity Monthly publications.

## Features

- Web scraping using Goutte (Symfony DomCrawler + Guzzle)
- Parses table to extract issue number and publication date
- File naming format: `{issue}_{date}_{seq}.pdf/zip`
- URL hash-based duplicate detection to save bandwidth
- Supports both PDF and ZIP file downloads
- Automated cron script with git auto-commit

## Installation

```bash
composer install
```

## Usage

### Run crawler manually

```bash
php crawler.php
```

### Automated scheduling (Cron)

```bash
# Run crawler and auto git commit
./scripts/cron.sh

# Add to crontab (e.g., daily at 6am)
0 6 * * * /path/to/scripts/cron.sh
```

## File Structure

```
├── crawler.php              # Main crawler script
├── composer.json            # Composer configuration
├── scripts/
│   └── cron.sh              # Cron automation script
└── downloads/
    ├── downloaded_urls.json # URL hash database
    └── *.pdf, *.zip         # Downloaded files
```

## Data Source

- [Control Yuan Sunshine Laws - Integrity Monthly](https://sunshine.cy.gov.tw/News.aspx?n=17&sms=8861)

---

# 監察院廉政專刊爬蟲

自動下載監察院陽光法令主題網廉政專刊的 PDF/ZIP 檔案。

## 功能

- 使用 Goutte (Symfony DomCrawler + Guzzle) 進行網頁爬取
- 解析表格取得期別與出刊日期
- 檔案命名格式：`{期別}_{出刊日期}_{序號}.pdf/zip`
- URL 雜湊檢測避免重複下載，節省頻寬
- 支援 PDF 與 ZIP 檔案下載
- 自動化排程腳本，含 git 自動提交

## 安裝

```bash
composer install
```

## 使用方式

### 手動執行爬蟲

```bash
php crawler.php
```

### 自動排程 (Cron)

```bash
# 執行爬蟲並自動 git commit
./scripts/cron.sh

# 加入 crontab (例如每日早上6點執行)
0 6 * * * /path/to/scripts/cron.sh
```

## 檔案結構

```
├── crawler.php              # 主爬蟲程式
├── composer.json            # Composer 設定
├── scripts/
│   └── cron.sh              # 自動排程腳本
└── downloads/
    ├── downloaded_urls.json # URL 雜湊資料庫
    └── *.pdf, *.zip         # 下載的檔案
```

## 資料來源

- [監察院陽光法令主題網 - 廉政專刊](https://sunshine.cy.gov.tw/News.aspx?n=17&sms=8861)

---

## License

MIT License

Copyright (c) 2025 Finjon Kiang

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
