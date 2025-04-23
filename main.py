#!/usr/bin/env python3
"""
Main entry point for the stock news monitoring tool.
"""
import os
import sys
import time
import logging
from datetime import datetime

from news_scraper import PRNewswireScraper, NewsArticle
from stock_data import StockDataFetcher
from pg_database import NewsDatabase# assumes this accepts date+time fields
import models
from models import db
from run import app
import threading


# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataMonitor:
    """Class to monitor and fetch stock news data."""

    def __init__(self):
        """Initialize with services."""
        self.scraper = PRNewswireScraper()
        self.stock_fetcher = StockDataFetcher()
        self.database = NewsDatabase()
        self.running = True
        self.status = "Initializing"

    def run(self):
        """Main execution loop."""
        with app.app_context():
            # Ensure tables exist
            try:
                db.create_all()
                logger.info("Database tables created successfully")
            except Exception as e:
                logger.info(f"Database initialization error (might already exist): {e}")

            logger.info("Starting stock news monitor")
            while self.running:
                try:
                    self.status = "Fetching news..."
                    # only page 1 for now
                    raw_articles = self.scraper.get_latest_news(max_pages=1)

                    # filter out any with no tickers
                    articles = [a for a in raw_articles if a.tickers]
                    if not articles:
                        self.status = "No articles with tickers found"
                        logger.info(self.status + ". Waiting 60 seconds.")
                        time.sleep(60)
                        continue

                    # sort newest first (requires scraper to set published_date/time)
                    articles.sort(
                        key=lambda a: (a.published_date, a.published_time),
                        reverse=True
                    )
                    logger.info(f"Found {len(articles)} ticker‑tagged articles")
                    self.status = f"Found {len(articles)} articles. Fetching stock data..."

                    # collect all tickers
                    all_tickers = {t for art in articles for t in art.tickers}
                    float_data = {}
                    if all_tickers:
                        logger.info(f"Fetching float data for {len(all_tickers)} tickers")
                        float_data = self.stock_fetcher.get_batch_float_data(list(all_tickers))

                    # attach float_data and save
                    saved_count = 0
                    for art in articles:
                        # only keep if all tickers returned data
                        art.float_data = {
                            t: float_data.get(t, {})
                            for t in art.tickers
                        }
                        # skip if float_data is empty for **all** tickers
                        if not any(art.float_data.values()):
                            logger.info(f"Skipping '{art.title}' — no float data")
                            continue

                        # save to DB; your save_article should accept date+time
                        logger.info(
                            f"Saving article: {art.published_date} "
                            f"{art.published_time.strftime('%H:%M')} - {art.title}"
                        )
                        article = NewsArticle(
                            title=art.title,
                            summary=art.summary,
                            url=art.url,
                            published_date=art.published_date,
                            published_time=art.published_time,
                            tickers=art.tickers
                        )
                        article.float_data = art.float_data  # attach float data

                        self.database.save_article(article)
                        saved_count += 1

                    self.status = (
                        f"Updated {saved_count}/{len(articles)} articles. "
                        "Next update in 60 seconds."
                    )
                    logger.info(self.status)
                    time.sleep(60)

                except Exception as e:
                    logger.error(f"Error in monitor loop: {e}", exc_info=True)
                    self.status = f"Error: {e}"
                    time.sleep(60)

    def stop(self):
        """Stop the monitor."""
        self.running = False
        logger.info("Stock news monitor stopped")


if __name__ == "__main__":
    try:
        monitor = DataMonitor()

        thread = threading.Thread(target=monitor.run, daemon=True)
        thread.start()

        logger.info("Background thread started for auto-refresh. Flask app is live.")

        from run import app

        app.run(host="0.0.0.0", port=8080, debug=True)

    except (KeyboardInterrupt, SystemExit):
        logger.info("Exiting stock news monitor")
        monitor.stop()
        sys.exit(0)