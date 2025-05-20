#!/usr/bin/env python3
"""
Flask web application for the stock news monitor.
Handles listing, detail view, manual refresh, and status.
"""

import os
import logging
from datetime import datetime
from flask import Flask, render_template, jsonify, redirect, url_for, request
from concurrent.futures import ThreadPoolExecutor
import threading

# Thread-safe scraper status tracker
class ScraperStatus:
    def __init__(self):
        self.lock = threading.Lock()
        self.status = {
            "message": "Ready",
            "progress": 0,
            "last_update": None
        }

    def update(self, **kwargs):
        with self.lock:
            self.status.update(kwargs)

    def get(self):
        with self.lock:
            return self.status.copy()

scraper_status = ScraperStatus()

from models import db
from pg_database import NewsDatabase
from AccesswireScrapper import AccesswireScraper
from GlobalnewswireScrapper import GlobalNewswireScraper
from news_scraper import PRNewswireScraper
from stock_data import StockDataFetcher
from dotenv import load_dotenv

# -- App setup --------------------------------------------------------------
app = Flask(__name__)
load_dotenv()

# PostgreSQL DB Config
PG_USER     = os.getenv("PG_USER")
PG_PASSWORD = os.getenv("PG_PASS")
PG_HOST     = os.getenv("PG_HOST")
PG_PORT     = os.getenv("PG_PORT")
PG_DB       = os.getenv("PG_DB")

app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Core instances
news_db = NewsDatabase()
stock_fetcher = StockDataFetcher()
pr_scraper = PRNewswireScraper()
access_scraper = AccesswireScraper()
global_scraper = GlobalNewswireScraper()


# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

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
        if val and val.endswith('M'):
            try:
                num = float(val[:-1])
                return (num < filter_val) if filter_op == 'lt' else (num > filter_val)
            except Exception:
                return False
        return False

    filtered = list(filter(passes_filter, articles)) if filter_val else articles

    return render_template(
        'index.html',
        articles=filtered,
        filter_val=filter_val or '',
        filter_op=filter_op or 'lt',
        page=page,
        status=scraper_status.get()
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
        status=scraper_status.get()
    )

@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    try:
        scraper_status.update(message='Refreshing…', progress=0)

        # 1) fetch from all sources
        articles = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(pr_scraper.get_latest_news, 1),
                executor.submit(access_scraper.get_latest_news, 5),
                executor.submit(global_scraper.get_latest_news, 1),
            ]
            for i, future in enumerate(futures, start=1):
                try:
                    result = future.result()
                    articles.extend(result)
                except Exception as e:
                    pass

        logger.info(f"Total fetched articles: {len(articles)}")
        scraper_status.update(progress=20)

        articles = [a for a in articles if a.tickers]
        logger.info(f"Articles with tickers: {len(articles)}")

        total = len(articles)
        saved = 0

        # 2) process + save
        for idx, art in enumerate(articles, start=1):
            scraper_status.update(progress=int((idx / total) * 100))

            logger.info(f"[Refresh] Processing [{idx}/{total}] URL: {art.url}")
            logger.info(f"[Refresh] Tickers: {art.tickers}")
            if not art.tickers:
                logger.info("Skipping article — no tickers")
                continue

            fd = stock_fetcher.get_batch_float_data(art.tickers)
            logger.info(f"[FloatData DEBUG] Article URL: {art.url}")
            logger.info(f"[FloatData DEBUG] Retrieved float data: {fd}")

            art.float_data = fd
            logger.info(f"[Refresh] Float data: {fd}")
            if not any(item.get('float') != 'N/A' for item in fd.values()):
                logger.info("Skipping article — no valid float data")
                continue

            logger.info(f"Saving article: {art.url} with tickers {art.tickers}")
            logger.info("Saved to DB")
            news_db.save_article(art)
            saved += 1

        scraper_status.update(
            message=f'Saved {saved}/{total}',
            last_update=datetime.utcnow().isoformat(),
            progress=100
        )
        return jsonify(status=scraper_status.get()['message'], success=True)

    except Exception as e:
        scraper_status.update(message=f'Error: {e}')
        return jsonify(status=scraper_status.get()['message'], success=False), 500
@app.route("/api/check_ticker")
def check_ticker():
    from pg_database import NewsDatabase
    ticker = request.args.get("ticker", "").upper()
    if not ticker:
        return jsonify({}), 400

    db = NewsDatabase()
    articles = db.get_articles_by_ticker(ticker, limit=1)
    if not articles:
        return jsonify({})
    latest = articles[0]
    return jsonify({
        "id": latest.id,
        "title": latest.title,
        "published": f"{latest.published_date} {latest.published_time}"
    })
@app.route('/api/status')
def api_status():
    return jsonify(scraper_status.get())
