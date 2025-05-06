#!/usr/bin/env python3
"""
Main entry point for the stock news monitoring tool.
Runs concurrent scraping in background and launches Flask app.
"""

import os
import sys
import time
import logging
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from GlobalnewswireScrapper import GlobalNewswireScraper
from models import db
from pg_database import NewsDatabase
from news_scraper import PRNewswireScraper, NewsArticle
from AccesswireScrapper import AccesswireScraper
from stock_data import StockDataFetcher
from run import app
from run import scraper_status

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DataMonitor:
    def __init__(self):
        self.pr_scraper = PRNewswireScraper()
        self.access_scraper = AccesswireScraper()
        self.stock_fetcher = StockDataFetcher()
        self.global_scraper = GlobalNewswireScraper()
        self.database = NewsDatabase()
        self.running = True
        self.status = "Initializing"

    def run(self):
        with app.app_context():
            try:
                db.create_all()
                logger.info("Database tables initialized.")
            except Exception as e:
                logger.warning(f"DB setup error: {e}")

            while self.running:
                try:
                    self.status = "Fetching latest articles..."
                    scraper_status.update(message="Fetching latest articles...", progress=5)
                    articles = []

                    # Run both scrapers concurrently
                    with ThreadPoolExecutor(max_workers=3) as executor:
                        futures = [
                            executor.submit(self.pr_scraper.get_latest_news, 1),
                            executor.submit(self.access_scraper.get_latest_news, 5),
                            executor.submit(self.global_scraper.get_latest_news, 2),
                        ]
                        for idx, future in enumerate(futures, 1):
                            try:
                                result = future.result()
                                articles.extend(result)
                                logger.info(f"[Source {idx}] Retrieved {len(result)} articles.")
                            except Exception as e:
                                logger.error(f"[Source {idx}] Scraper failed: {e}")
                    logger.info(f"Total fetched articles: {len(articles)}")
                    scraper_status.update(progress=20)

                    # Filter valid articles with tickers
                    articles = [a for a in articles if a.tickers]
                    logger.info(f"Articles with tickers: {len(articles)}")
                    if not articles:
                        logger.info("No articles with tickers found. Sleeping...")
                        time.sleep(30)
                        continue

                    articles.sort(key=lambda a: (a.published_date, a.published_time), reverse=True)

                    # Fetch float data
                    all_tickers = {t for art in articles for t in art.tickers}
                    float_data = self.stock_fetcher.get_batch_float_data(list(all_tickers))

                    saved_count = 0
                    for art in articles:
                        art.float_data = {t: float_data.get(t, {}) for t in art.tickers}
                        if not any(art.float_data.values()):
                            logger.info(f"Skipping '{art.title}' — no float data")
                            continue

                        logger.info(f"Saving article: {art.url} with tickers {art.tickers}")
                        self.database.save_article(art)
                        saved_count += 1
                        scraper_status.update(progress=int((saved_count / len(articles)) * 70) + 20)

                    self.status = f"Saved {saved_count}/{len(articles)} articles. Sleeping 60s."
                    scraper_status.update(
                        message=f"Saved {saved_count}/{len(articles)} articles.",
                        progress=100,
                        last_update=datetime.utcnow().isoformat()
                    )
                    logger.info(self.status)
                    time.sleep(30)

                except Exception as e:
                    logger.error(f"[Monitor Error] {e}", exc_info=True)
                    self.status = f"Error: {e}"
                    scraper_status.update(message=f"Error: {e}", progress=0)
                    time.sleep(30)

    def stop(self):
        self.running = False
        logger.info("Stopping DataMonitor.")


if __name__ == "__main__":
    try:
        monitor = DataMonitor()
        threading.Thread(target=monitor.run, daemon=True).start()

        logger.info("Background monitor started. Launching Flask server.")
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown requested. Cleaning up...")
        monitor.stop()
        sys.exit(0)
