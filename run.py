#!/usr/bin/env python3
"""
Flask web application for the stock news monitor.
Handles listing, detail view, manual refresh, and status.
"""
import os
import logging
from datetime import datetime
from urllib.parse import quote_plus
from flask import Flask, render_template, jsonify, redirect, url_for, request
from models import db
from pg_database import NewsDatabase
from news_scraper import PRNewswireScraper
from stock_data import StockDataFetcher

# -- App setup --------------------------------------------------------------
app = Flask(__name__)

# Convert Azure SQL connection string into SQLAlchemy URI
raw_conn_str = os.environ.get('SQLAZURECONNSTR_DB')
if not raw_conn_str:
    raise RuntimeError("Missing SQLAZURECONNSTR_DB environment variable.")

# Extract values manually (Azure provides in ADO.NET style, so we hardcode for now)
server = 'sqlsrv-araso-prod.database.windows.net'
database = 'sqldb-araso-prod'
user = 'sqlnewsusr'
password = 'DCV0zBmL1!'
driver = 'ODBC+Driver+17+for+SQL+Server'

# URL-encode the password
password = quote_plus(password)

# Final SQLAlchemy MSSQL URI
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"mssql+pyodbc://{user}:{password}@{server}:1433/{database}?driver={driver}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize DB
db.init_app(app)

news_db = NewsDatabase()
scraper = PRNewswireScraper()
stock_fetcher = StockDataFetcher()

STATUS = {
    'message': 'Ready',
    'progress': 0,
    'last_update': None
}

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Ensure tables exist
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    filter_val = request.args.get('float_val', type=float)
    filter_op = request.args.get('filter_op', default='lt')

    articles = news_db.get_recent_articles(page=page, page_size=50)

    def passes_filter(article):
        if not article.tickers or not article.float_data:
            return False
        first = article.tickers[0]
        val = article.float_data.get(first, {}).get('float')
        if val and isinstance(val, str) and val.endswith('M'):
            try:
                num = float(val[:-1])
                return (num < filter_val) if filter_op == 'lt' else (num > filter_val)
            except Exception:
                return False
        return True

    filtered = list(filter(passes_filter, articles)) if filter_val else articles

    return render_template(
        'index.html',
        articles=filtered,
        filter_val=filter_val or '',
        filter_op=filter_op or 'lt',
        page=page,
        status={
            'message': 'Ready',
            'progress': 100,
            'last_update': None
        }
    )

@app.route('/clear', methods=['POST'])
def clear_all_articles():
    try:
        news_db.clear_articles()
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Failed to clear DB: {e}")
        return "Error clearing database", 500

@app.route('/article/<int:article_id>')
def article_detail(article_id):
    article = news_db.get_article_by_id(article_id)
    if not article:
        return redirect(url_for('index'))
    return render_template(
        'article_detail.html',
        article=article,
        status={'message': 'Viewing details', 'progress': 100, 'last_update': None}
    )

@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    try:
        STATUS.update(message='Refreshing…', progress=0)
        raw = scraper.get_latest_news(max_pages=1)
        total = len(raw)
        saved = 0

        for i, art in enumerate(raw, start=1):
            STATUS['progress'] = int((i / total) * 100)
            if not art.tickers:
                continue
            fd = stock_fetcher.get_batch_float_data(art.tickers)
            art.float_data = fd
            if not any(item.get('float') != 'N/A' for item in fd.values()):
                continue
            news_db.save_article(art)
            saved += 1

        STATUS.update(
            message=f'Saved {saved}/{total}',
            last_update=datetime.utcnow().isoformat(),
            progress=100
        )
        return jsonify(status=STATUS['message'], success=True)

    except Exception as e:
        logger.exception('Refresh failed')
        STATUS['message'] = f'Error: {e}'
        return jsonify(status=STATUS['message'], success=False), 500

@app.route('/api/status')
def api_status():
    return jsonify(STATUS)
