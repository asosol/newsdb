#!/usr/bin/env python3
"""
Main entry point for the stock news monitoring tool.
"""
import os
import sys
import time
import logging
import threading
from datetime import datetime

from news_scraper import PRNewswireScraper
from stock_data import StockDataFetcher
from pg_database import NewsDatabase
import models
from models import db
from run import app

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
            # Try to create all tables in case they don't exist
            try:
                db.create_all()
                logger.info("Database tables created successfully")
            except Exception as e:
                logger.info(f"Database tables already exist or error: {e}")
            
            logger.info("Starting stock news monitor")
            while self.running:
                try:
                    self.status = "Fetching news..."
                    
                    # Fetch latest news
                    articles = self.scraper.get_latest_news()
                    
                    if not articles:
                        self.status = "No new articles found"
                        logger.info("No new articles found. Waiting 60 seconds.")
                        time.sleep(60)  # Wait for 1 minute before next fetch
                        continue
                    
                    logger.info(f"Found {len(articles)} articles")
                    self.status = f"Found {len(articles)} articles. Fetching stock data..."
                    
                    # Get unique tickers from all articles
                    all_tickers = set()
                    for article in articles:
                        all_tickers.update(article.tickers)
                    
                    # Fetch float data for all tickers
                    if all_tickers:
                        logger.info(f"Fetching data for {len(all_tickers)} tickers")
                        float_data = self.stock_fetcher.get_batch_float_data(list(all_tickers))
                        
                        # Attach float data to articles
                        for article in articles:
                            article.float_data = {ticker: float_data.get(ticker, {}) for ticker in article.tickers}
                        
                        # Save articles to database
                        self.status = "Saving articles to database..."
                        logger.info("Saving articles to database")
                        
                        for article in articles:
                            self.database.save_article(article)
                    
                    self.status = f"Updated {len(articles)} articles. Next update in 60 seconds."
                    logger.info(f"Updated {len(articles)} articles. Next update in 60 seconds.")
                    
                    # Wait for 1 minute before the next fetch
                    time.sleep(60)
                
                except Exception as e:
                    logger.error(f"Error in monitor loop: {e}")
                    self.status = f"Error: {str(e)}"
                    time.sleep(60)  # Wait for 1 minute before retry
    
    def stop(self):
        """Stop the monitor."""
        self.running = False
        logger.info("Stock news monitor stopped")

if __name__ == "__main__":
    try:
        # Create and run the data monitor
        monitor = DataMonitor()
        monitor.run()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Exiting stock news monitor")
        sys.exit(0)