import re
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date, time
import time as tmod
import trafilatura

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class NewsArticle:
    """Class representing a news article with financial information."""
    def __init__(self, title, summary, url, published_date: date, published_time: time, tickers=None):
        self.title = title
        self.summary = summary
        self.url = url
        self.published_date = published_date  # datetime.date
        self.published_time = published_time  # datetime.time
        self.tickers = tickers or []
        self.float_data = {}

    def __str__(self):
        time_str = self.published_time.strftime('%H:%M') if self.published_time else ''
        date_str = self.published_date.isoformat() if self.published_date else ''
        tickers = ','.join(self.tickers) if self.tickers else 'No tickers'
        return f"{date_str} {time_str} — {self.title} [{tickers}]"

class PRNewswireScraper:
    """Class for scraping paginated news releases from PRNewswire."""
    BASE_URL = (
        "https://www.prnewswire.com/news-releases/financial-services-latest-news/"
        "financial-services-latest-news-list/"
    )

    def __init__(self, headers=None):
        self.headers = headers or {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }

    def get_latest_news(self, max_pages=1):
        """
        Fetch up to max_pages of news. Return list of NewsArticle sorted newest first.
        """
        articles = []
        page = 1
        selectors = [
            'div.card.col-view',
            'div.col-sm-8.col-lg-9.pull-left.card',
            '.card-list-item',
            '.news-release-item',
            '.release-card',
            '.news-card',
        ]

        while page <= max_pages:
            url = f"{self.BASE_URL}?page={page}&pagesize=100"
            logger.info(f"Fetching PRNewswire page {page}: {url}")
            try:
                resp = requests.get(url, headers=self.headers, timeout=30)
                resp.raise_for_status()
            except Exception as e:
                logger.error(f"Error fetching page {page}: {e}")
                break

            soup = BeautifulSoup(resp.text, 'html.parser')
            items = []
            for sel in selectors:
                found = soup.select(sel)
                if found:
                    items = found
                    logger.info(f"Using selector '{sel}' with {len(items)} items")
                    break
            if not items:
                logger.warning(f"No news items found on page {page}")
                break

            for idx, item in enumerate(items, start=1):
                try:
                    h3 = item.find('h3')
                    small = h3.find('small') if h3 else None
                    raw_date = small.text.strip() if small else ''
                    if small:
                        small.extract()
                    raw_date = raw_date.replace(' ET', '')
                    parts = [p.strip() for p in raw_date.split(',')]
                    try:
                        date_part = f"{parts[0]}, {parts[1]}"
                        time_part = parts[2]
                        pub_date = datetime.strptime(date_part, '%b %d, %Y').date()
                        pub_time = datetime.strptime(time_part, '%H:%M').time()
                    except (IndexError, ValueError):
                        logger.warning(f"Couldn't parse date '{raw_date}', defaulting to now")
                        now = datetime.utcnow()
                        pub_date = now.date()
                        pub_time = now.time().replace(second=0, microsecond=0)

                    title = h3.get_text(strip=True) if h3 else 'No title'

                    link = item.select_one('a.newsreleaseconsolidatelink')
                    if not link or not link.get('href'):
                        logger.warning(f"Item {idx} missing link, skipping")
                        continue
                    article_url = link['href']
                    if not article_url.startswith('http'):
                        article_url = f"https://www.prnewswire.com{article_url}"

                    summary = self.get_article_content(article_url)
                    tickers = self.extract_tickers(f"{title} {summary}")
                    if not tickers:
                        logger.info(f"Item {idx} has no valid tickers, skipping")
                        continue

                    # skip if no float data later in saving logic
                    art = NewsArticle(title, summary, article_url, pub_date, pub_time, tickers)
                    logger.info(f"Parsed article: {art}")
                    articles.append(art)

                except Exception as e:
                    logger.error(f"Error parsing item {idx}: {e}")
                    continue

            page += 1
            tmod.sleep(1)

        articles.sort(key=lambda a: (a.published_date, a.published_time), reverse=True)
        logger.info(f"Scraped {len(articles)} articles")
        return articles

    def get_article_content(self, url):
        try:
            raw = trafilatura.fetch_url(url)
            text = trafilatura.extract(raw)
            if text:
                return text
        except Exception:
            pass
        try:
            resp = requests.get(url, headers=self.headers, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            body = soup.select_one('.release-body')
            return body.get_text(strip=True) if body else ''
        except Exception as e:
            logger.error(f"Error fetching article content: {e}")
            return ''

    def extract_tickers(self, text):
        """Extract all NASDAQ/NYSE tickers like (NASDAQ:META), (NYSE: T), etc."""
        patterns = [
            r'\b(?:NASDAQ|Nasdaq|nasdaq):\s*([A-Z][A-Z0-9\.]{1,10})',
            r'\b(?:NYSE|Nyse|nyse):\s*([A-Z][A-Z0-9\.]{1,10})'
        ]
        found = []
        for pat in patterns:
            matches = re.findall(pat, text)
            found.extend(matches)

        # Deduplicate while preserving order
        seen = set()
        tickers = []
        for t in found:
            t = t.upper().strip()
            if t not in seen:
                tickers.append(t)
                seen.add(t)

        return tickers

        raw = []
        # extract comma-lists
        for grp in list_pat.findall(text):
            parts = [p.strip() for p in grp.split(',')]
            raw.extend(parts)
        # extract simple
        raw.extend(simple_pat.findall(text))

        unique = []
        for sym in raw:
            s = sym.upper()
            if s in ("NASDAQ", "NYSE"):  # skip plain mentions
                continue
            if re.fullmatch(r"[A-Z]{1,5}(?:\.[A-Z])?", s) and s not in unique:
                unique.append(s)
        return unique


# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     scraper = PRNewswireScraper()
#     articles = scraper.get_latest_news(max_pages=1)
#
#     for idx, article in enumerate(articles, start=1):
#         print(f"\n[{idx}] {article.title}")
#         print(f"URL: {article.url}")
#         print(f"Tickers: {article.tickers}")
