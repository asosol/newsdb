-- SQLite schema for stock news monitoring database

-- News articles table
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    summary TEXT,
    url TEXT UNIQUE NOT NULL,
    published_date TEXT,
    published_time TIME,
    created_at TEXT NOT NULL
);

-- Stock tickers table
CREATE TABLE IF NOT EXISTS tickers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT UNIQUE NOT NULL
);

-- Join table for articles and tickers
CREATE TABLE IF NOT EXISTS article_tickers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    ticker_id INTEGER NOT NULL,
    FOREIGN KEY (article_id) REFERENCES articles (id) ON DELETE CASCADE,
    FOREIGN KEY (ticker_id) REFERENCES tickers (id) ON DELETE CASCADE,
    UNIQUE (article_id, ticker_id)
);

-- Float data for tickers
CREATE TABLE IF NOT EXISTS float_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker_symbol TEXT UNIQUE NOT NULL,
    company_name TEXT,
    float_value TEXT,
    price TEXT,
    market_cap TEXT,
    updated_at TEXT NOT NULL
);

-- User watchlists table for persistent alerts
CREATE TABLE IF NOT EXISTS user_watchlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker_symbol TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (ticker_symbol)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_articles_url ON articles (url);
CREATE INDEX IF NOT EXISTS idx_tickers_symbol ON tickers (symbol);
CREATE INDEX IF NOT EXISTS idx_article_tickers_article_id ON article_tickers (article_id);
CREATE INDEX IF NOT EXISTS idx_article_tickers_ticker_id ON article_tickers (ticker_id);
CREATE INDEX IF NOT EXISTS idx_float_data_ticker_symbol ON float_data (ticker_symbol);
CREATE INDEX IF NOT EXISTS idx_user_watchlists_ticker ON user_watchlists (ticker_symbol);
