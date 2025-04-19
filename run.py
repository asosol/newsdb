"""
Flask web application for the stock news monitoring tool.
"""
import os
import logging
from flask import Flask, render_template, jsonify, request, redirect, url_for

from models import db
from news_scraper import PRNewswireScraper
from stock_data import StockDataFetcher
from pg_database import NewsDatabase

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask application
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Configure PostgreSQL database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize the app with SQLAlchemy
db.init_app(app)

# Initialize services
scraper = PRNewswireScraper()
stock_fetcher = StockDataFetcher()
database = NewsDatabase()

@app.route('/')
def index():
    """Render the home page with recent news articles."""
    # Get recent articles from database
    articles = database.get_recent_articles(limit=100)
    
    # Get status information (since we don't have background fetcher in this version)
    status = {
        'message': 'Data fetching managed by separate process',
        'progress': 100,
        'last_update': 'See logs for details'
    }
    
    return render_template('index.html', articles=articles, status=status)

@app.route('/article/<int:article_id>')
def article_detail(article_id):
    """Render the article detail page."""
    article = database.get_article_by_id(article_id)
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
                database.save_article(article)
        
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
    """Get the current status."""
    return jsonify({
        'message': 'Data fetching managed by separate process',
        'progress': 100,
        'last_update': None
    })

# Ensure tables exist
with app.app_context():
    try:
        db.create_all()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.info(f"Tables already exist: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True)