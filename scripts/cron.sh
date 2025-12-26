#!/bin/bash

# PDF/ZIP Crawler Cron Script
# Executes crawler and commits new files to git

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR" || exit 1

echo "=== $(date '+%Y-%m-%d %H:%M:%S') ==="
echo "Running crawler..."

# Run the crawler
php crawler.php

# Check if there are any changes
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    echo "No new files to commit."
    exit 0
fi

# Add all changes
git add -A

# Get count of new/modified files
NEW_COUNT=$(git diff --cached --name-only | wc -l)

# Commit with timestamp
git commit -m "Auto-update: Downloaded ${NEW_COUNT} new/updated files

$(date '+%Y-%m-%d %H:%M:%S')"

echo "Committed ${NEW_COUNT} files."
