#!/usr/bin/env python3
"""
Flask web application for the stock news monitoring tool.
"""
import os
import time
import threading
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, redirect, url_for

from news_scraper import PRNewswireScraper, NewsArticle
from stock_data import StockDataFetcher
from database import NewsDatabase

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Initialize database and services
db = NewsDatabase()
scraper = PRNewswireScraper()
stock_fetcher = StockDataFetcher()

# Background data fetcher
class BackgroundDataFetcher:
    def __init__(self):
        self.thread = None
        self.running = False
        self.last_update = None
        self.status = "Initializing"
        self.progress = 0
    
    def start(self):
        if self.thread is None or not self.thread.is_alive():
            self.running = True
            self.thread = threading.Thread(target=self.run)
            self.thread.daemon = True
            self.thread.start()
            logger.info("Background data fetcher started")
    
    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1)
            logger.info("Background data fetcher stopped")
    
    def run(self):
        while self.running:
            try:
                self.status = "Fetching news..."
                self.progress = 0
                
                # Fetch latest news
                articles = scraper.get_latest_news()
                self.progress = 30
                
                if not articles:
                    self.status = "No new articles found"
                    self.progress = 100
                    time.sleep(60)  # Wait for 1 minute before next fetch
                    continue
                
                self.status = f"Found {len(articles)} articles. Fetching stock data..."
                
                # Get unique tickers from all articles
                all_tickers = set()
                for article in articles:
                    all_tickers.update(article.tickers)
                
                # Fetch float data for all tickers
                if all_tickers:
                    float_data = stock_fetcher.get_batch_float_data(list(all_tickers))
                    self.progress = 60
                    
                    # Attach float data to articles
                    for article in articles:
                        article.float_data = {ticker: float_data.get(ticker, {}) for ticker in article.tickers}
                    
                    # Save articles to database
                    self.status = "Saving articles to database..."
                    for article in articles:
                        db.save_article(article)
                    
                    self.progress = 90
                
                self.progress = 100
                self.status = f"Updated {len(articles)} articles. Next update in 60 seconds."
                self.last_update = datetime.now()
                
                # Wait for 1 minute before the next fetch
                time.sleep(60)
            
            except Exception as e:
                logger.error(f"Error in data fetcher thread: {e}")
                self.status = f"Error: {str(e)}"
                time.sleep(60)  # Wait for 1 minute before retry

# Initialize the background fetcher
data_fetcher = BackgroundDataFetcher()

@app.route('/')
def index():
    """Render the home page with recent news articles."""
    # Get recent articles from database
    articles = db.get_recent_articles(limit=100)
    
    # Get status information
    status = {
        'message': data_fetcher.status,
        'progress': data_fetcher.progress,
        'last_update': data_fetcher.last_update.strftime('%Y-%m-%d %H:%M:%S') if data_fetcher.last_update else 'Never'
    }
    
    return render_template('index.html', articles=articles, status=status)

@app.route('/article/<int:article_id>')
def article_detail(article_id):
    """Render the article detail page."""
    article = db.get_article_by_id(article_id)
    if not article:
        return redirect(url_for('index'))
    
    return render_template('article_detail.html', article=article)

@app.route('/api/refresh', methods=['POST'])
def refresh_data():
    """Manually trigger a data refresh."""
    try:
        # Fetch latest news
        articles = scraper.get_latest_news()
        
        if not articles:
            return jsonify({'status': 'No new articles found'})
        
        # Get unique tickers from all articles
        all_tickers = set()
        for article in articles:
            all_tickers.update(article.tickers)
        
        # Fetch float data for all tickers
        if all_tickers:
            float_data = stock_fetcher.get_batch_float_data(list(all_tickers))
            
            # Attach float data to articles
            for article in articles:
                article.float_data = {ticker: float_data.get(ticker, {}) for ticker in article.tickers}
            
            # Save articles to database
            for article in articles:
                db.save_article(article)
        
        # Get updated articles from database
        db_articles = db.get_recent_articles()
        
        return jsonify({
            'status': f'Updated {len(articles)} articles',
            'success': True
        })
    
    except Exception as e:
        logger.error(f"Error refreshing data: {e}")
        return jsonify({
            'status': f'Error: {str(e)}',
            'success': False
        }), 500

@app.route('/api/status')
def get_status():
    """Get the current status of the data fetcher."""
    return jsonify({
        'message': data_fetcher.status,
        'progress': data_fetcher.progress,
        'last_update': data_fetcher.last_update.isoformat() if data_fetcher.last_update else None
    })

# Initialize the data fetcher before the app starts
with app.app_context():
    data_fetcher.start()

@app.teardown_appcontext
def cleanup(exception=None):
    """Clean up resources when the application context ends."""
    pass

if __name__ == '__main__':
    try:
        # Start the background fetcher
        data_fetcher.start()
        
        # Run the Flask app
        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    except (KeyboardInterrupt, SystemExit):
        # Stop the background fetcher on exit
        data_fetcher.stop()