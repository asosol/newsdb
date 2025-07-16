"""
Database models for the stock news monitoring application.
"""
import os
from datetime import datetime, date, time
from flask_sqlalchemy import SQLAlchemy


# Initialize SQLAlchemy
db = SQLAlchemy()

# Association table for many-to-many between articles and tickers
article_tickers = db.Table(
    'article_tickers',
    db.Column('article_id', db.Integer, db.ForeignKey('articles.id', ondelete='CASCADE'), primary_key=True),
    db.Column('ticker_id', db.Integer, db.ForeignKey('tickers.id', ondelete='CASCADE'), primary_key=True)
)

class Article(db.Model):
    """Model for news articles."""
    __tablename__ = 'articles'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    summary = db.Column(db.Text)
    url = db.Column(db.String(1000), unique=True, nullable=False)

    # Separate date and time columns
    published_date = db.Column(db.Date, nullable=True)
    published_time = db.Column(db.Time, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to tickers
    tickers = db.relationship(
        'Ticker', secondary=article_tickers,
        backref=db.backref('articles', lazy='dynamic'),
        lazy='dynamic'
    )

    def __repr__(self):
        return f"<Article {self.id}: {self.title[:30]}...>"

    def to_dict(self):
        """Convert article to dictionary for JSON/template usage."""
        return {
            'id': self.id,
            'title': self.title,
            'summary': self.summary,
            'url': self.url,
            # isoformat date & HH:MM time
            'published_date': self.published_date.strftime('%Y-%m-%d') if self.published_date else '',
            'published_time': self.published_time.strftime('%H:%M') if self.published_time else '',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'tickers': [t.symbol for t in self.tickers.all()]
        }

class Ticker(db.Model):
    """Model for stock tickers."""
    __tablename__ = 'tickers'
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), unique=True, nullable=False)
    # one-to-one to float data
    float_data = db.relationship('FloatData', backref='ticker', uselist=False)

    def __repr__(self):
        return f"<Ticker {self.symbol}>"

class FloatData(db.Model):
    """Model for float data associated with tickers."""
    __tablename__ = 'float_data'
    id = db.Column(db.Integer, primary_key=True)
    ticker_symbol = db.Column(db.String(20), db.ForeignKey('tickers.symbol'), unique=True, nullable=False)
    company_name = db.Column(db.String(200))
    float_value = db.Column(db.String(50))
    price = db.Column(db.String(50))
    market_cap = db.Column(db.String(50))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        """Convert float data to dictionary."""
        return {
            'symbol': self.ticker_symbol,
            'name': self.company_name,
            'float': self.float_value,
            'price': self.price,
            'market_cap': self.market_cap
        }

    def __repr__(self):
        return f"<FloatData {self.ticker_symbol}: {self.float_value}>"

class UserWatchlist(db.Model):
    """Model for user watchlists (persistent alerts)."""
    __tablename__ = 'user_watchlists'
    id = db.Column(db.Integer, primary_key=True)
    ticker_symbol = db.Column(db.String(20), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<UserWatchlist {self.ticker_symbol}>"

    def to_dict(self):
        """Convert watchlist item to dictionary."""
        return {
            'id': self.id,
            'ticker_symbol': self.ticker_symbol,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
