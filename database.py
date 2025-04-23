# #!/usr/bin/env python3
# """
# Module for database operations to store and retrieve news articles.
# """
# import os
# import sqlite3
# import logging
# from datetime import datetime
# import json
# import threading
#
# logger = logging.getLogger(__name__)
#
# class NewsDatabase:
#     """Class for database operations related to news articles."""
#
#     def __init__(self, db_path='stock_news.db'):
#         """Initialize the database."""
#         self.db_path = db_path
#         self.lock = threading.Lock()
#         self._init_db()
#
#     def _get_connection(self):
#         """Get a database connection."""
#         conn = sqlite3.connect(self.db_path)
#         conn.row_factory = sqlite3.Row  # Return rows as dictionaries
#         return conn
#
#     def _init_db(self):
#         """Initialize the database schema if it doesn't exist."""
#         with self.lock:
#             try:
#                 conn = self._get_connection()
#                 cursor = conn.cursor()
#
#                 # Execute the schema script
#                 with open('schema.sql', 'r') as f:
#                     schema_script = f.read()
#                     cursor.executescript(schema_script)
#
#                 conn.commit()
#                 logger.info("Database initialized successfully")
#
#             except Exception as e:
#                 logger.error(f"Error initializing database: {e}")
#
#             finally:
#                 if conn:
#                     conn.close()
#
#     def save_article(self, article):
#         """Save a news article to the database."""
#         with self.lock:
#             conn = None
#             try:
#                 conn = self._get_connection()
#                 cursor = conn.cursor()
#
#                 # Check if article already exists
#                 cursor.execute(
#                     "SELECT id FROM articles WHERE url = ?",
#                     (article.url,)
#                 )
#                 existing = cursor.fetchone()
#
#                 if existing:
#                     logger.debug(f"Article already exists: {article.url}")
#                     return existing['id']
#
#                 # Insert article
#                 cursor.execute(
#                     """
#                     INSERT INTO articles
#                     (title, summary, url, published_date, created_at)
#                     VALUES (?, ?, ?, ?, ?)
#                     """,
#                     (
#                         article.title,
#                         article.summary,
#                         article.url,
#                         article.published_date.isoformat() if isinstance(article.published_date, datetime) else article.published_date,
#                         datetime.now().isoformat()
#                     )
#                 )
#
#                 article_id = cursor.lastrowid
#
#                 # Insert tickers
#                 for ticker in article.tickers:
#                     cursor.execute(
#                         "INSERT OR IGNORE INTO tickers (symbol) VALUES (?)",
#                         (ticker,)
#                     )
#
#                     cursor.execute("SELECT id FROM tickers WHERE symbol = ?", (ticker,))
#                     ticker_id = cursor.fetchone()['id']
#
#                     cursor.execute(
#                         "INSERT INTO article_tickers (article_id, ticker_id) VALUES (?, ?)",
#                         (article_id, ticker_id)
#                     )
#
#                 # Insert float data
#                 if article.float_data:
#                     for ticker, data in article.float_data.items():
#                         cursor.execute(
#                             """
#                             INSERT INTO float_data
#                             (ticker_symbol, company_name, float_value, price, market_cap, updated_at)
#                             VALUES (?, ?, ?, ?, ?, ?)
#                             ON CONFLICT(ticker_symbol) DO UPDATE SET
#                             company_name = excluded.company_name,
#                             float_value = excluded.float_value,
#                             price = excluded.price,
#                             market_cap = excluded.market_cap,
#                             updated_at = excluded.updated_at
#                             """,
#                             (
#                                 ticker,
#                                 data.get('name', 'N/A'),
#                                 data.get('float', 'N/A'),
#                                 data.get('price', 'N/A'),
#                                 data.get('market_cap', 'N/A'),
#                                 datetime.now().isoformat()
#                             )
#                         )
#
#                 conn.commit()
#                 logger.info(f"Saved article with ID {article_id}")
#                 return article_id
#
#             except Exception as e:
#                 if conn:
#                     conn.rollback()
#                 logger.error(f"Error saving article: {e}")
#                 return None
#
#             finally:
#                 if conn:
#                     conn.close()
#
#     def get_recent_articles(self, limit=100):
#         """Get recent articles from the database."""
#         with self.lock:
#             conn = None
#             try:
#                 conn = self._get_connection()
#                 cursor = conn.cursor()
#
#                 cursor.execute(
#                     """
#                     SELECT a.id, a.title, a.summary, a.url, a.published_date, a.created_at,
#                            GROUP_CONCAT(t.symbol) as tickers
#                     FROM articles a
#                     LEFT JOIN article_tickers at ON a.id = at.article_id
#                     LEFT JOIN tickers t ON at.ticker_id = t.id
#                     GROUP BY a.id
#                     ORDER BY a.created_at DESC
#                     LIMIT ?
#                     """,
#                     (limit,)
#                 )
#
#                 articles = []
#                 for row in cursor.fetchall():
#                     article_dict = dict(row)
#
#                     # Parse tickers
#                     tickers = []
#                     if article_dict['tickers']:
#                         tickers = article_dict['tickers'].split(',')
#
#                     article_dict['tickers'] = tickers
#
#                     # Get float data for tickers
#                     float_data = {}
#                     if tickers:
#                         ticker_placeholders = ','.join(['?'] * len(tickers))
#                         cursor.execute(
#                             f"""
#                             SELECT ticker_symbol, company_name, float_value, price, market_cap
#                             FROM float_data
#                             WHERE ticker_symbol IN ({ticker_placeholders})
#                             """,
#                             tickers
#                         )
#
#                         for float_row in cursor.fetchall():
#                             float_dict = dict(float_row)
#                             float_data[float_dict['ticker_symbol']] = {
#                                 'name': float_dict['company_name'],
#                                 'float': float_dict['float_value'],
#                                 'price': float_dict['price'],
#                                 'market_cap': float_dict['market_cap']
#                             }
#
#                     article_dict['float_data'] = float_data
#                     articles.append(article_dict)
#
#                 return articles
#
#             except Exception as e:
#                 logger.error(f"Error getting recent articles: {e}")
#                 return []
#
#             finally:
#                 if conn:
#                     conn.close()
#
#     def get_article_by_id(self, article_id):
#         """Get a specific article by ID."""
#         with self.lock:
#             conn = None
#             try:
#                 conn = self._get_connection()
#                 cursor = conn.cursor()
#
#                 cursor.execute(
#                     """
#                     SELECT a.id, a.title, a.summary, a.url, a.published_date, a.created_at,
#                            GROUP_CONCAT(t.symbol) as tickers
#                     FROM articles a
#                     LEFT JOIN article_tickers at ON a.id = at.article_id
#                     LEFT JOIN tickers t ON at.ticker_id = t.id
#                     WHERE a.id = ?
#                     GROUP BY a.id
#                     """,
#                     (article_id,)
#                 )
#
#                 row = cursor.fetchone()
#                 if not row:
#                     return None
#
#                 article_dict = dict(row)
#
#                 # Parse tickers
#                 tickers = []
#                 if article_dict['tickers']:
#                     tickers = article_dict['tickers'].split(',')
#
#                 article_dict['tickers'] = tickers
#
#                 # Get float data for tickers
#                 float_data = {}
#                 if tickers:
#                     ticker_placeholders = ','.join(['?'] * len(tickers))
#                     cursor.execute(
#                         f"""
#                         SELECT ticker_symbol, company_name, float_value, price, market_cap
#                         FROM float_data
#                         WHERE ticker_symbol IN ({ticker_placeholders})
#                         """,
#                         tickers
#                     )
#
#                     for float_row in cursor.fetchall():
#                         float_dict = dict(float_row)
#                         float_data[float_dict['ticker_symbol']] = {
#                             'name': float_dict['company_name'],
#                             'float': float_dict['float_value'],
#                             'price': float_dict['price'],
#                             'market_cap': float_dict['market_cap']
#                         }
#
#                 article_dict['float_data'] = float_data
#                 return article_dict
#
#             except Exception as e:
#                 logger.error(f"Error getting article by ID: {e}")
#                 return None
#
#             finally:
#                 if conn:
#                     conn.close()
#
#     def update_float_data(self, ticker, float_data):
#         """Update float data for a ticker."""
#         with self.lock:
#             conn = None
#             try:
#                 conn = self._get_connection()
#                 cursor = conn.cursor()
#
#                 cursor.execute(
#                     """
#                     INSERT INTO float_data
#                     (ticker_symbol, company_name, float_value, price, market_cap, updated_at)
#                     VALUES (?, ?, ?, ?, ?, ?)
#                     ON CONFLICT(ticker_symbol) DO UPDATE SET
#                     company_name = excluded.company_name,
#                     float_value = excluded.float_value,
#                     price = excluded.price,
#                     market_cap = excluded.market_cap,
#                     updated_at = excluded.updated_at
#                     """,
#                     (
#                         ticker,
#                         float_data.get('name', 'N/A'),
#                         float_data.get('float', 'N/A'),
#                         float_data.get('price', 'N/A'),
#                         float_data.get('market_cap', 'N/A'),
#                         datetime.now().isoformat()
#                     )
#                 )
#
#                 conn.commit()
#                 logger.debug(f"Updated float data for {ticker}")
#                 return True
#
#             except Exception as e:
#                 if conn:
#                     conn.rollback()
#                 logger.error(f"Error updating float data: {e}")
#                 return False
#
#             finally:
#                 if conn:
#                     conn.close()
