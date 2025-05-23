import re
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import time as tmod
import trafilatura
import gc

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class NewsArticle:
    def __init__(self, title, summary, url, published_date, published_time, tickers=None):
        self.title = title
        self.summary = summary
        self.url = url
        self.published_date = published_date
        self.published_time = published_time
        self.tickers = tickers or []
        self.float_data = {}

    def __str__(self):
        time_str = self.published_time.strftime('%H:%M') if self.published_time else ''
        date_str = self.published_date.isoformat() if self.published_date else ''
        tickers = ','.join(self.tickers) if self.tickers else 'No tickers'
        return f"{date_str} {time_str} — {self.title} [{tickers}]"


class PRNewswireScraper:
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
                    link = item.select_one('a.newsreleaseconsolidatelink')
                    if not link or not link.get('href'):
                        logger.warning(f"Item {idx} missing link, skipping")
                        continue

                    article_url = link['href']
                    if not article_url.startswith('http'):
                        article_url = f"https://www.prnewswire.com{article_url}"

                    # parse publication timestamp
                    pub_date, pub_time = self.extract_date_from_article(article_url)

                    title = h3.get_text(strip=True) if h3 else 'No title'

                    # fetch the body
                    summary = self.get_article_content(article_url)
                    if not summary:
                        logger.warning(f"Item {idx} ('{title}') empty content, skipping")
                        continue

                    # extract tickers
                    tickers = self.extract_tickers(summary)
                    if not tickers:
                        logger.info(f"Item {idx} ('{title}') has no valid tickers, skipping")
                        continue

                    # build and collect
                    article = NewsArticle(
                        title=title,
                        summary=summary,
                        url=article_url,
                        published_date=pub_date,
                        published_time=pub_time,
                        tickers=tickers
                    )
                    articles.append(article)

                    # memory cleanup
                    del summary, article
                    gc.collect()

                except Exception as e:
                    logger.error(f"Error parsing item {idx}: {e}")
                    continue

            del soup, items, resp
            gc.collect()
            page += 1
            tmod.sleep(1)

        # sort newest first
        articles.sort(key=lambda a: (a.published_date, a.published_time), reverse=True)
        logger.info(f"Scraped {len(articles)} articles")
        return articles

    def extract_date_from_article(self, url):
        try:
            resp = requests.get(url, headers=self.headers, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            meta_p = soup.select_one('p.mb-no')
            if meta_p:
                ts = meta_p.get_text(strip=True).replace(' ET', '')
                dt = datetime.strptime(ts, '%b %d, %Y, %H:%M')
                dt = dt.replace(tzinfo=ZoneInfo("America/New_York"))
                return dt.date(), dt.time()
        except Exception as e:
            logger.warning(f"Failed to extract date from article {url}: {e}")

        # fallback to “now”
        now = datetime.now(ZoneInfo("America/New_York"))
        return now.date(), now.time().replace(second=0, microsecond=0)

    def get_article_content(self, url):
        # first try trafilatura
        try:
            raw = trafilatura.fetch_url(url)
            if raw:
                text = trafilatura.extract(raw) or ''
                if text:
                    return text
        except Exception:
            pass

        # fallback to BS4
        try:
            resp = requests.get(url, headers=self.headers, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            body = soup.select_one('.release-body')
            return body.get_text(separator='\n', strip=True) if body else ''
        except Exception:
            return ''

    def extract_tickers(self, text):
        patterns = [
            r'\b(?:NASDAQ|NYSE):\s*([A-Z][A-Z0-9\.]{1,10})',
        ]
        found = []
        for pat in patterns:
            found += re.findall(pat, text)
        # dedupe + uppercase
        seen = set()
        tickers = []
        for t in found:
            t = t.upper().strip()
            if t not in seen:
                seen.add(t)
                tickers.append(t)
        return tickers