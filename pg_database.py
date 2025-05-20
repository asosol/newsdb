"""
Module for PostgreSQL database operations to store and retrieve news articles.
"""
import logging
from datetime import datetime
from models import db, Article, Ticker, FloatData
from news_scraper import NewsArticle

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class NewsDatabase:
    """Class to handle saving and loading news articles and float data."""

    def __init__(self):
        logger.info("NewsDatabase initialized")

    def get_articles_by_ticker(self, ticker, limit=1):
        articles = (
            Article.query.join(Article.tickers)
            .filter(Ticker.symbol == ticker)
            .order_by(Article.published_date.desc(), Article.published_time.desc())
            .limit(limit)
            .all()
        )
        return articles

    def save_article(self, article: NewsArticle):
        try:
            existing = Article.query.filter_by(url=article.url).first()
            if existing:
                logger.info(f"Article already exists: {article.url}")
                return existing.id

            new_article = Article(
                title=article.title,
                summary=article.summary,
                url=article.url,
                published_date=article.published_date,
                published_time=article.published_time
            )

            # Add tickers
            for sym in article.tickers:
                ticker = Ticker.query.filter_by(symbol=sym).first()
                if not ticker:
                    ticker = Ticker(symbol=sym)
                    db.session.add(ticker)
                    db.session.flush()
                new_article.tickers.append(ticker)

            db.session.add(new_article)
            db.session.flush()  # Flush before committing
            logger.info(f"✅ Article staged: {new_article.url}")

            # Save float data if available
            if article.float_data:
                for sym, data in article.float_data.items():
                    if data:  # Only if data is non-empty
                        self.update_float_data(sym, data)

            db.session.commit()
            logger.info(f"✅ Article saved with ID {new_article.id}")

            return new_article.id

        except Exception as e:
            logger.error(f"❌ Error saving article '{article.url}': {e}", exc_info=True)
            db.session.rollback()
            return None

    def get_recent_articles(self, page=1, page_size=100):
        try:
            offset = (page - 1) * page_size
            records = (
                db.session.query(Article)
                .order_by(
                    Article.published_date.desc(),
                    Article.published_time.desc()
                )
                .offset(offset)
                .limit(page_size)
                .all()
            )

            result = []
            for art in records:
                obj = ArticleObject(
                    title=art.title,
                    summary=art.summary,
                    url=art.url,
                    published_date=art.published_date,
                    published_time=art.published_time,
                    tickers=[t.symbol for t in art.tickers]
                )
                obj.id = art.id
                float_map = {}
                for sym in obj.tickers:
                    fd = FloatData.query.filter_by(ticker_symbol=sym).first()
                    if fd:
                        float_map[sym] = fd.to_dict()
                obj.float_data = float_map
                result.append(obj)

            return result
        except Exception as e:
            logger.error(f"Error getting recent articles: {e}")
            return []

    def get_article_by_id(self, article_id):
        try:
            art = Article.query.get(article_id)
            if not art:
                return None
            d = art.to_dict()
            float_map = {}
            for sym in d['tickers']:
                fd = FloatData.query.filter_by(ticker_symbol=sym).first()
                if fd:
                    float_map[sym] = fd.to_dict()
            d['float_data'] = float_map
            return d
        except Exception as e:
            logger.error(f"Error fetching article {article_id}: {e}")
            return None

    def update_float_data(self, ticker_symbol, float_data):
        try:
            ticker = Ticker.query.filter_by(symbol=ticker_symbol).first()
            if not ticker:
                ticker = Ticker(symbol=ticker_symbol)
                db.session.add(ticker)
                db.session.flush()

            fd = FloatData.query.filter_by(ticker_symbol=ticker_symbol).first()
            if not fd:
                fd = FloatData(
                    ticker_id=ticker.id,
                    ticker_symbol=ticker_symbol,
                    company_name=float_data.get('name'),
                    float_value=float_data.get('float'),
                    price=float_data.get('price'),
                    market_cap=float_data.get('market_cap')
                )
                db.session.add(fd)
            else:
                fd.company_name = float_data.get('name')
                fd.float_value = float_data.get('float')
                fd.price = float_data.get('price')
                fd.market_cap = float_data.get('market_cap')
                fd.updated_at = datetime.utcnow()

            db.session.commit()
            logger.debug(f"Float data updated for {ticker_symbol}")
            return True

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating float data for {ticker_symbol}: {e}")
            return False

    def clear_articles(self):
        try:
            db.session.query(Article).delete()
            db.session.query(Ticker).delete()
            db.session.query(FloatData).delete()
            db.session.commit()
            logger.info("All articles, tickers, and float data cleared.")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to clear articles: {e}")



class ArticleObject:
    def __init__(self, title, summary, url, published_date, published_time, tickers=None):
        self.title = title
        self.summary = summary
        self.url = url
        self.published_date = published_date
        self.published_time = published_time
        self.tickers = tickers or []
        self.float_data = {}
        self.id = None
