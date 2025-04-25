import logging
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from curl_cffi import requests
from news_scraper import NewsArticle  # Assuming it's defined as per your earlier script

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class AccesswireScraper:
    BASE_URL = "https://www.accessnewswire.com/newsroom/api"

    def __init__(self):
        self.headers = {
            "origin": "https://www.accessnewswire.com",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/134.0.0.0 Safari/537.36"
            )
        }

    def get_latest_news(self, max_pages=10):
        articles = []

        for page in range(max_pages):
            url = (
                f"{self.BASE_URL}?pageindex={page}"
                f"&pageSize=20"
            )

            success = False
            for attempt in range(3):
                try:
                    resp = requests.post(url, headers=self.headers, impersonate="chrome110")
                    resp.raise_for_status()
                    data = resp.json()
                    success = True
                    break
                except Exception as e:
                    logger.warning(f"[Accesswire] Attempt {attempt+1}/3 failed for page {page}: {e}")
                    time.sleep(1)  # optional short delay between retries
            if not success:
                logger.error(f"[Accesswire] Failed to fetch page {page} after 3 attempts.")
                continue

            items = data.get("data", {}).get("articles", [])
            if not items:
                logger.warning(f"[Accesswire] No articles found on page {page}")
                continue

            for idx, item in enumerate(items):
                try:
                    title = item.get("title", "No title").strip()
                    url = item.get("releaseurl")
                    summary_html = item.get("body", "")
                    summary = BeautifulSoup(summary_html, "html.parser").get_text(strip=True)

                    dt = datetime.fromisoformat(item["adate"]).astimezone(ZoneInfo("America/New_York"))

                    tickers = self.extract_tickers(summary)
                    if not tickers:
                        continue

                    article = NewsArticle(
                        title=title,
                        summary=summary,
                        url=url,
                        published_date=dt.date(),
                        published_time=dt.time(),
                        tickers=tickers
                    )
                    articles.append(article)

                except Exception as e:
                    logger.error(f"[Accesswire] Failed to parse article {idx}: {e}")

        logger.info(f"[Accesswire] Scraped {len(articles)} valid articles")
        return articles

    def extract_tickers(self, text):
        patterns = [
            r'\b(?:NASDAQ|Nasdaq|nasdaq):\s*([A-Z][A-Z0-9\.]{1,10})',
            r'\b(?:NYSE|Nyse|nyse):\s*([A-Z][A-Z0-9\.]{1,10})'
        ]
        found = []
        for pat in patterns:
            found.extend(re.findall(pat, text))

        return list({t.upper().strip() for t in found if t})

# if __name__ == "__main__":
#     scraper = AccesswireScraper()
#     articles = scraper.get_latest_news(max_pages=10)
#
#     print(f"✅ Scraped {len(articles)} articles from Accesswire\n")
#     for i, article in enumerate(articles, 1):
#         print(f"[{i}] {article.title}")
#         print(f"    🕒 {article.published_date} {article.published_time}")
#         print(f"    🔗 {article.url}")
#         print(f"    💹 Tickers: {', '.join(article.tickers)}")
#         print(f"    🔍 Summary: {article.summary[:200]}...\n")
