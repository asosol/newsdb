"""
Database models for the stock news monitoring application.
"""
import os
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Association table for articles and tickers (many-to-many relationship)
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
    published_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with tickers
    tickers = db.relationship('Ticker', secondary=article_tickers, 
                             backref=db.backref('articles', lazy='dynamic'))
    
    def __repr__(self):
        return f"<Article {self.id}: {self.title[:30]}...>"
    
    def to_dict(self):
        """Convert article to dictionary."""
        return {
            'id': self.id,
            'title': self.title,
            'summary': self.summary,
            'url': self.url,
            'published_date': self.published_date.isoformat() if self.published_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'tickers': [ticker.symbol for ticker in self.tickers]
        }

class Ticker(db.Model):
    """Model for stock tickers."""
    __tablename__ = 'tickers'
    
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), unique=True, nullable=False)
    
    # Relationship with float data
    float_data = db.relationship('FloatData', backref='ticker', uselist=False)
    
    def __repr__(self):
        return f"<Ticker {self.symbol}>"

class FloatData(db.Model):
    """Model for stock float data."""
    __tablename__ = 'float_data'
    
    id = db.Column(db.Integer, primary_key=True)
    ticker_id = db.Column(db.Integer, db.ForeignKey('tickers.id', ondelete='CASCADE'), unique=True)
    ticker_symbol = db.Column(db.String(20), unique=True, nullable=False)
    company_name = db.Column(db.String(200))
    float_value = db.Column(db.String(50))
    price = db.Column(db.String(50))
    market_cap = db.Column(db.String(50))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<FloatData {self.ticker_symbol}>"
    
    def to_dict(self):
        """Convert float data to dictionary."""
        return {
            'name': self.company_name,
            'float': self.float_value,
            'price': self.price,
            'market_cap': self.market_cap
        }