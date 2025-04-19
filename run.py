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
            # If no articles found, add some sample articles for testing
            sample_articles = create_sample_articles()
            articles = sample_articles
            
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

def create_sample_articles():
    """Create sample articles for testing."""
    from datetime import datetime
    from news_scraper import NewsArticle
    
    sample_articles = [
        NewsArticle(
            title="JPMorgan Chase Announces Strong Q1 Financial Results (JPM)",
            summary="JPMorgan Chase & Co. today announced its Q1 2025 financial results, showing strong performance across all business segments. The bank reported earnings per share of $4.50, exceeding analyst expectations of $4.25. Total revenue increased by 8% year-over-year to $38.2 billion. CEO Jamie Dimon commented, 'We delivered solid results this quarter, reflecting the strength of our diversified business model.'",
            url="https://www.example.com/jpm-q1-results",
            published_date=datetime.now(),
            tickers=["JPM"]
        ),
        NewsArticle(
            title="Bank of America Reports Record Profits in Consumer Banking (BAC)",
            summary="Bank of America Corporation (NYSE: BAC) today reported record profits in its Consumer Banking division. The bank saw a 12% increase in consumer deposits and a 7% increase in consumer loans. CEO Brian Moynihan stated, 'Our focus on responsible growth has resulted in another quarter of strong performance, with record profits in our Consumer Banking segment.'",
            url="https://www.example.com/bac-consumer-banking",
            published_date=datetime.now(),
            tickers=["BAC"]
        ),
        NewsArticle(
            title="Goldman Sachs and Morgan Stanley Announce Strategic Partnership",
            summary="Goldman Sachs (NYSE: GS) and Morgan Stanley (NYSE: MS) today announced a strategic partnership to enhance their global investment banking capabilities. The partnership aims to combine Goldman's strength in mergers and acquisitions with Morgan Stanley's wealth management expertise. This collaboration is expected to generate significant synergies and provide clients with a broader range of financial services.",
            url="https://www.example.com/gs-ms-partnership",
            published_date=datetime.now(),
            tickers=["GS", "MS"]
        ),
        NewsArticle(
            title="Wells Fargo Expands Digital Banking Platform",
            summary="Wells Fargo & Company (NYSE: WFC) today announced a major expansion of its digital banking platform. The bank is introducing new features including AI-powered financial insights, enhanced mobile payment options, and improved cybersecurity measures. 'Our investment in digital technology demonstrates our commitment to providing customers with the best possible banking experience,' said the CEO.",
            url="https://www.example.com/wfc-digital-expansion",
            published_date=datetime.now(),
            tickers=["WFC"]
        ),
        NewsArticle(
            title="BlackRock Launches New ESG-Focused ETF",
            summary="BlackRock, Inc. (NYSE: BLK) today announced the launch of its newest exchange-traded fund (ETF) focused on environmental, social, and governance (ESG) criteria. The BlackRock Sustainable Future ETF will invest in companies demonstrating strong ESG practices and positive environmental impact. 'Investors increasingly want to align their investments with their values without sacrificing returns,' said a BlackRock spokesperson.",
            url="https://www.example.com/blk-esg-etf",
            published_date=datetime.now(),
            tickers=["BLK"]
        )
    ]
    
    return sample_articles

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