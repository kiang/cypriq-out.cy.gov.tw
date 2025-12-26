<?php
/**
 * PDF/ZIP Crawler - Downloads files from sunshine.cy.gov.tw
 * Uses Goutte (Symfony DomCrawler + Guzzle) for web scraping
 * Implements URL hash-based duplicate detection (saves bandwidth)
 * Names files as {期別}_{出刊日期}_{seq}.pdf/zip
 */

require_once __DIR__ . '/vendor/autoload.php';

use Goutte\Client;
use Symfony\Component\HttpClient\HttpClient;

class PdfCrawler
{
    private Client $client;
    private string $downloadDir;
    private string $hashFile;
    private array $downloadedUrls = [];
    private int $downloadCount = 0;
    private int $skipCount = 0;

    public function __construct(string $downloadDir = 'downloads')
    {
        $this->client = new Client(HttpClient::create([
            'timeout' => 60,
            'verify_peer' => false,
            'headers' => [
                'User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            ]
        ]));

        $this->downloadDir = __DIR__ . '/' . $downloadDir;
        $this->hashFile = $this->downloadDir . '/downloaded_urls.json';

        $this->initializeDirectories();
        $this->loadDownloadedUrls();
    }

    private function initializeDirectories(): void
    {
        if (!is_dir($this->downloadDir)) {
            mkdir($this->downloadDir, 0755, true);
            echo "Created download directory: {$this->downloadDir}\n";
        }
    }

    private function loadDownloadedUrls(): void
    {
        if (file_exists($this->hashFile)) {
            $content = file_get_contents($this->hashFile);
            $this->downloadedUrls = json_decode($content, true) ?? [];
            echo "Loaded " . count($this->downloadedUrls) . " previously downloaded URLs\n";
        }
    }

    private function saveDownloadedUrls(): void
    {
        file_put_contents(
            $this->hashFile,
            json_encode($this->downloadedUrls, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE)
        );
    }

    public function crawl(string $url): void
    {
        echo "\n=== Starting PDF/ZIP Crawler ===\n";
        echo "Target URL: {$url}\n\n";

        try {
            $crawler = $this->client->request('GET', $url);

            // Parse the table rows
            $fileLinks = [];

            $crawler->filter('table tbody tr, table tr')->each(function ($row) use (&$fileLinks) {
                $cells = $row->filter('td');

                if ($cells->count() >= 4) {
                    // Get 期別 (issue) from column 2 (index 1)
                    $issueText = trim($cells->eq(1)->text());

                    // Get 出刊日期 (publication date) from column 3 (index 2)
                    $dateText = trim($cells->eq(2)->text());

                    // Extract issue number (e.g., "292" from "廉政專刊第292期")
                    $issueNumber = '';
                    if (preg_match('/第(\d+)期/', $issueText, $matches)) {
                        $issueNumber = $matches[1];
                    }

                    // Clean date (e.g., "114-12-23" -> "114-12-23")
                    $dateClean = preg_replace('/[^\d\-]/', '', $dateText);

                    // Find all download links (PDF and ZIP) in this row
                    $row->filter('a')->each(function ($link) use (&$fileLinks, $issueNumber, $dateClean) {
                        $href = $link->attr('href');

                        // Check if link is a downloadable file (PDF or ZIP)
                        if ($href && (
                            stripos($href, '.pdf') !== false ||
                            stripos($href, '.zip') !== false ||
                            stripos($href, 'Download.ashx') !== false
                        )) {
                            // Determine file extension
                            $ext = 'pdf';
                            if (stripos($href, '.zip') !== false) {
                                $ext = 'zip';
                            } elseif (stripos($href, 'icon=..zip') !== false) {
                                $ext = 'zip';
                            }

                            $fileLinks[] = [
                                'url' => $href,
                                'issue' => $issueNumber,
                                'date' => $dateClean,
                                'ext' => $ext,
                                'text' => trim($link->text())
                            ];
                        }
                    });
                }
            });

            echo "Found " . count($fileLinks) . " downloadable files (PDF/ZIP)\n\n";

            // Group files by issue to assign sequence numbers
            $issueSeq = [];

            foreach ($fileLinks as $index => $link) {
                $issueKey = $link['issue'] . '_' . $link['date'];
                if (!isset($issueSeq[$issueKey])) {
                    $issueSeq[$issueKey] = 0;
                }
                $issueSeq[$issueKey]++;
                $link['seq'] = $issueSeq[$issueKey];

                $this->downloadFile($link, $index + 1, count($fileLinks));
            }

            $this->saveDownloadedUrls();
            $this->printSummary();

        } catch (\Exception $e) {
            echo "Error crawling page: " . $e->getMessage() . "\n";
        }
    }

    private function downloadFile(array $link, int $current, int $total): void
    {
        $url = $link['url'];
        $issue = $link['issue'];
        $date = $link['date'];
        $seq = $link['seq'];
        $ext = $link['ext'];

        // Make URL absolute if relative
        if (!str_starts_with($url, 'http')) {
            $url = 'https://sunshine.cy.gov.tw/' . ltrim($url, '/');
        }

        // Calculate URL hash BEFORE downloading to save bandwidth
        $urlHash = hash('sha256', $url);

        // Generate filename: {期別}_{出刊日期}_{seq}.ext
        $filename = "{$issue}_{$date}_{$seq}.{$ext}";

        echo "[{$current}/{$total}] Processing: {$filename}\n";

        // Check for duplicate URL
        if (isset($this->downloadedUrls[$urlHash])) {
            echo "  SKIP: Already downloaded\n\n";
            $this->skipCount++;
            return;
        }

        echo "  URL: {$url}\n";

        try {
            // Download file content
            $httpClient = HttpClient::create([
                'timeout' => 120,
                'verify_peer' => false,
            ]);

            $response = $httpClient->request('GET', $url);
            $content = $response->getContent();

            $filepath = $this->downloadDir . '/' . $filename;

            // Avoid filename collision
            $filepath = $this->getUniqueFilepath($filepath);
            $filename = basename($filepath);

            // Save file
            file_put_contents($filepath, $content);

            // Store URL hash with metadata
            $this->downloadedUrls[$urlHash] = [
                'filename' => $filename,
                'url' => $url,
                'issue' => $issue,
                'date' => $date,
                'size' => strlen($content),
                'downloaded_at' => date('Y-m-d H:i:s')
            ];

            $size = $this->formatBytes(strlen($content));
            echo "  SAVED: {$filename} ({$size})\n\n";

            $this->downloadCount++;

        } catch (\Exception $e) {
            echo "  ERROR: " . $e->getMessage() . "\n\n";
        }
    }

    private function getUniqueFilepath(string $filepath): string
    {
        if (!file_exists($filepath)) {
            return $filepath;
        }

        $dir = dirname($filepath);
        $ext = pathinfo($filepath, PATHINFO_EXTENSION);
        $name = pathinfo($filepath, PATHINFO_FILENAME);

        $counter = 1;
        do {
            $newPath = $dir . '/' . $name . '_' . $counter . '.' . $ext;
            $counter++;
        } while (file_exists($newPath));

        return $newPath;
    }

    private function formatBytes(int $bytes): string
    {
        $units = ['B', 'KB', 'MB', 'GB'];
        $i = 0;
        while ($bytes >= 1024 && $i < count($units) - 1) {
            $bytes /= 1024;
            $i++;
        }
        return round($bytes, 2) . ' ' . $units[$i];
    }

    private function printSummary(): void
    {
        echo "\n=== Download Summary ===\n";
        echo "New files downloaded: {$this->downloadCount}\n";
        echo "Duplicates skipped (by URL): {$this->skipCount}\n";
        echo "Total URLs tracked: " . count($this->downloadedUrls) . "\n";
        echo "URL database: {$this->hashFile}\n";
        echo "========================\n";
    }
}

// Run the crawler
$targetUrl = 'https://sunshine.cy.gov.tw/News.aspx?n=17&sms=8861&page=1&PageSize=200';
$crawler = new PdfCrawler('downloads');
$crawler->crawl($targetUrl);
