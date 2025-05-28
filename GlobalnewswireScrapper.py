class GlobalNewswireScraper:
    BASE_URL = "https://www.globenewswire.com/newsroom"

    def __init__(self, headers=None):
        self.headers = headers or {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/134.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Origin": "https://www.globenewswire.com"
        }

    def get_latest_news(self, max_pages=1):
        from curl_cffi import requests
        from bs4 import BeautifulSoup
        from datetime import datetime
        from zoneinfo import ZoneInfo
        import logging
        # NewsArticle must be imported from the project where defined
        try:
            from news_scraper import NewsArticle
        except ImportError:
            NewsArticle = dict  # fallback to dict for demonstration

        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(levelname)s:%(message)s'))
        logger.addHandler(handler)
        articles = []

        for page in range(1, max_pages + 1):
            try:
                url = f"{self.BASE_URL}?page={page}&pageSize=50"
                resp = requests.get(url, headers=self.headers, impersonate="chrome110", timeout=30)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                parent_divs = soup.select("div.newsLink")

                for parent_div in parent_divs:
                    try:
                        title_tag = parent_div.select_one("div.mainLink > a")
                        date_tag = parent_div.select_one("div.date-source span")

                        if not title_tag or not date_tag:
                            continue

                        title = title_tag.text.strip()
                        article_url = "https://www.globenewswire.com" + title_tag["href"]
                        date_str = date_tag.text.strip()  # e.g. April 25, 2025 06:16 ET
                        print("⏱️ Date string found:", date_str)

                        dt = datetime.strptime(date_str.replace(" ET", ""), "%B %d, %Y %H:%M")
                        dt = dt.replace(tzinfo=ZoneInfo("America/New_York"))

                        summary = title  # Placeholder as summary extraction isn't detailed
                        # Fetch the article content and extract tickers from it
                        article_resp = requests.get(article_url, headers=self.headers, impersonate="chrome110", timeout=30)
                        article_resp.raise_for_status()
                        article_soup = BeautifulSoup(article_resp.text, "html.parser")
                        article_body_text = article_soup.get_text(separator=' ', strip=True)
                        tickers = self.extract_tickers(article_body_text)

                        if not tickers:
                            continue

                        article = NewsArticle(
                            title=title,
                            summary=summary,
                            url=article_url,
                            published_date=dt.date(),
                            published_time=dt.time(),
                            tickers=tickers
                        )
                        articles.append(article)
                    except Exception as e:
                        logger.warning(f"[GlobalNewswire] Error parsing article: {e}")
            except Exception as e:
                logger.error(f"[GlobalNewswire] Failed to fetch page {page}: {e}")
        return articles

    def extract_tickers(self, text):
        import re
        patterns = [
            r'\b(?:NASDAQ|Nasdaq|nasdaq):\s*([A-Z][A-Z0-9\.]{1,10})',
            r'\b(?:NYSE|Nyse|nyse)(?:\s+American)?:\s*([A-Z][A-Z0-9\.]{1,10})'
        ]
        found = []
        for pat in patterns:
            found.extend(re.findall(pat, text))
        return list(set(t.upper().strip() for t in found if t))


# if __name__ == "__main__":
#     scraper = GlobalNewswireScraper()
#     articles = scraper.get_latest_news(max_pages=2)  # or more pages if needed
#
#     print(f"✅ Total articles scraped: {len(articles)}\n")
#     for i, article in enumerate(articles, 1):
#         print(f"[{i}] {article.title}")
#         print(f"    📰 URL      : {article.url}")
#         print(f"    🕒 Published: {article.published_date} {article.published_time}")
#         print(f"    💹 Tickers  : {', '.join(article.tickers)}")
#         print(f"    🔍 Summary  : {article.summary[:200]}...\n")