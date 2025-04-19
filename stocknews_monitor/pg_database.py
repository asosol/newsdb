"""
Module for PostgreSQL database operations to store and retrieve news articles.
"""
import os
import logging
from datetime import datetime
import json

from models import db, Article, Ticker, FloatData
from news_scraper import NewsArticle

logger = logging.getLogger(__name__)

class NewsDatabase:
    """Class for database operations related to news articles."""
    
    def __init__(self):
        """Initialize the database."""
        logger.info("Database initialized")
    
    def save_article(self, article):
        """Save a news article to the database."""
        try:
            # Check if article already exists
            existing_article = Article.query.filter_by(url=article.url).first()
            if existing_article:
                logger.debug(f"Article already exists: {article.url}")
                return existing_article.id
            
            # Create new article
            new_article = Article(
                title=article.title,
                summary=article.summary,
                url=article.url,
                published_date=article.published_date if isinstance(article.published_date, datetime) else None
            )
            
            # Process tickers
            for ticker_symbol in article.tickers:
                # Check if ticker exists
                ticker = Ticker.query.filter_by(symbol=ticker_symbol).first()
                if not ticker:
                    ticker = Ticker(symbol=ticker_symbol)
                    db.session.add(ticker)
                    db.session.flush()  # Flush to get the ticker ID
                
                new_article.tickers.append(ticker)
            
            db.session.add(new_article)
            db.session.commit()
            
            # Process float data
            if article.float_data:
                for ticker_symbol, data in article.float_data.items():
                    self.update_float_data(ticker_symbol, data)
            
            logger.info(f"Saved article with ID {new_article.id}")
            return new_article.id
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving article: {e}")
            return None
    
    def get_recent_articles(self, limit=100):
        """Get recent articles from the database."""
        try:
            # Get articles with tickers
            articles = db.session.query(Article).order_by(Article.created_at.desc()).limit(limit).all()
            
            result = []
            for article in articles:
                article_dict = article.to_dict()
                
                # Get float data for tickers
                float_data = {}
                for ticker_symbol in article_dict['tickers']:
                    ticker_float = FloatData.query.filter_by(ticker_symbol=ticker_symbol).first()
                    if ticker_float:
                        float_data[ticker_symbol] = ticker_float.to_dict()
                
                article_dict['float_data'] = float_data
                result.append(article_dict)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting recent articles: {e}")
            return []
    
    def get_article_by_id(self, article_id):
        """Get a specific article by ID."""
        try:
            article = Article.query.get(article_id)
            if not article:
                return None
            
            article_dict = article.to_dict()
            
            # Get float data for tickers
            float_data = {}
            for ticker_symbol in article_dict['tickers']:
                ticker_float = FloatData.query.filter_by(ticker_symbol=ticker_symbol).first()
                if ticker_float:
                    float_data[ticker_symbol] = ticker_float.to_dict()
            
            article_dict['float_data'] = float_data
            return article_dict
            
        except Exception as e:
            logger.error(f"Error getting article by ID: {e}")
            return None
    
    def update_float_data(self, ticker_symbol, float_data):
        """Update float data for a ticker."""
        try:
            # Find ticker
            ticker = Ticker.query.filter_by(symbol=ticker_symbol).first()
            if not ticker:
                ticker = Ticker(symbol=ticker_symbol)
                db.session.add(ticker)
                db.session.flush()
            
            # Update or create float data
            ticker_float = FloatData.query.filter_by(ticker_symbol=ticker_symbol).first()
            if not ticker_float:
                ticker_float = FloatData(
                    ticker_id=ticker.id,
                    ticker_symbol=ticker_symbol,
                    company_name=float_data.get('name', 'N/A'),
                    float_value=float_data.get('float', 'N/A'),
                    price=float_data.get('price', 'N/A'),
                    market_cap=float_data.get('market_cap', 'N/A')
                )
                db.session.add(ticker_float)
            else:
                ticker_float.company_name = float_data.get('name', 'N/A')
                ticker_float.float_value = float_data.get('float', 'N/A')
                ticker_float.price = float_data.get('price', 'N/A')
                ticker_float.market_cap = float_data.get('market_cap', 'N/A')
                ticker_float.updated_at = datetime.utcnow()
            
            db.session.commit()
            logger.debug(f"Updated float data for {ticker_symbol}")
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating float data: {e}")
            return False