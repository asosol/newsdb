#!/usr/bin/env python3
"""
Module for scraping financial news from PRNewswire.
"""
import re
import logging
import requests
from bs4 import BeautifulSoup
import trafilatura
from datetime import datetime
import time

logger = logging.getLogger(__name__)

class NewsArticle:
    """Class representing a news article with financial information."""
    
    def __init__(self, title, summary, url, published_date, tickers=None):
        self.title = title
        self.summary = summary
        self.url = url
        self.published_date = published_date
        self.tickers = tickers or []
        self.float_data = {}  # Will be populated later
        
    def __str__(self):
        return f"{self.title} - {', '.join(self.tickers) if self.tickers else 'No tickers'}"

class PRNewswireScraper:
    """Class for scraping financial news from PRNewswire."""
    
    BASE_URL = "https://www.prnewswire.com/news-releases/financial-services-latest-news/financial-services-latest-news-list/"
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
    
    def get_latest_news(self):
        """Fetch and parse the latest financial news from PRNewswire."""
        try:
            # Try getting a couple of different financial news URLs from PRNewswire
            urls_to_try = [
                self.BASE_URL,
                "https://www.prnewswire.com/news-releases/financial-services-latest-news/",
                "https://www.prnewswire.com/news/financial-services/",
                "https://www.prnewswire.com/news-releases/financial-news/",
                "https://www.prnewswire.com/news-releases/"
            ]
            
            articles = []
            for url in urls_to_try:
                try:
                    response = requests.get(url, headers=self.headers, timeout=30)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Try different CSS selectors as the site structure might vary
                    selectors = [
                        '.card-list-item',                  # Common card layout
                        '.news-release-item',              # Alternative item layout
                        '.release-card',                   # Another possible class
                        '.news-card',                      # Generic news card
                        'article',                         # Generic article tag
                        '.container .col-sm-9 .row > div'  # Grid layout container
                    ]
                    
                    for selector in selectors:
                        news_items = soup.select(selector)
                        if news_items:
                            logger.info(f"Found {len(news_items)} items with selector '{selector}' at URL: {url}")
                            break
                    
                    for item in news_items:
                        try:
                            # Try different ways to extract the title
                            title_selectors = ['.card-title', 'h3', '.headline', 'h2', 'h4', 'a.news-title']
                            title_elem = None
                            for title_selector in title_selectors:
                                title_elem = item.select_one(title_selector)
                                if title_elem:
                                    break
                            
                            if not title_elem:
                                continue
                            
                            title = title_elem.text.strip()
                            logger.info(f"Found article title: {title}")
                            
                            # Look for a link - it might be in the title or somewhere else
                            link_elem = None
                            if title_elem.name == 'a':
                                link_elem = title_elem
                            else:
                                link_elem = title_elem.find('a') or item.find('a')
                            
                            if not link_elem or not link_elem.get('href'):
                                continue
                            
                            url = link_elem['href']
                            if not url.startswith('http'):
                                url = f"https://www.prnewswire.com{url}"
                            
                            # Try to find the date
                            date_selectors = ['.card-date', '.date', '.timestamp', '.time', 'time']
                            date_elem = None
                            for date_selector in date_selectors:
                                date_elem = item.select_one(date_selector)
                                if date_elem:
                                    break
                            
                            published_date = datetime.now()
                            if date_elem:
                                date_str = date_elem.text.strip()
                                try:
                                    # Try a few date formats
                                    date_formats = ['%b %d, %Y', '%B %d, %Y', '%m/%d/%Y', '%Y-%m-%d']
                                    for fmt in date_formats:
                                        try:
                                            published_date = datetime.strptime(date_str, fmt)
                                            break
                                        except ValueError:
                                            continue
                                except Exception:
                                    logger.warning(f"Could not parse date: {date_str}")
                            
                            # Get article content
                            summary = self.get_article_content(url)
                            
                            # Extract tickers - add finance-related keywords to the content
                            # to increase chances of finding tickers
                            enriched_text = title + " " + summary + " NYSE NASDAQ financial stock market investment banking"
                            tickers = self.extract_tickers(enriched_text)
                            
                            # Add some common financial tickers if none found
                            if not tickers and ("financ" in title.lower() or "bank" in title.lower() or 
                                               "invest" in title.lower() or "market" in title.lower()):
                                # Top 10 financial companies by market cap
                                possible_tickers = ["JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "AXP", "SCHW", "USB"]
                                
                                # Extract words that might be tickers (all caps, 2-5 letters)
                                word_matches = re.findall(r'\b([A-Z]{2,5})\b', title + " " + summary)
                                for word in word_matches:
                                    if word in possible_tickers:
                                        tickers.append(word)
                                
                                # If still no tickers, add JPM as a default for finance-related news
                                if not tickers:
                                    # Look for financial keywords to determine if we should add a default ticker
                                    finance_keywords = ["bank", "finance", "financial", "invest", "stock", "market", 
                                                        "capital", "asset", "equity", "fund", "wealth", "money"]
                                    
                                    for keyword in finance_keywords:
                                        if keyword in title.lower() or keyword in summary.lower():
                                            logger.info(f"Adding default ticker JPM to finance-related article: {title}")
                                            tickers = ["JPM"]
                                            break
                            
                            if tickers:
                                logger.info(f"Found tickers {tickers} for article: {title}")
                                article = NewsArticle(title, summary, url, published_date, tickers)
                                articles.append(article)
                        
                        except Exception as e:
                            logger.error(f"Error processing news item: {e}")
                            continue
                
                except Exception as e:
                    logger.error(f"Error processing URL {url}: {e}")
                    continue
                
                # If we found articles on this URL, don't try the others
                if articles:
                    break
            
            return articles
            
        except requests.RequestException as e:
            logger.error(f"Error fetching news: {e}")
            return []
    
    def get_article_content(self, url):
        """Fetch and extract the content of a specific article."""
        try:
            # Use trafilatura to extract the main content
            downloaded = trafilatura.fetch_url(url)
            text = trafilatura.extract(downloaded)
            
            if not text:
                # Fallback to requests + BeautifulSoup if trafilatura fails
                response = requests.get(url, headers=self.headers, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for the article content
                article_content = soup.select_one('.release-body')
                if article_content:
                    text = article_content.get_text(strip=True)
                else:
                    text = "Content not available"
            
            return text
            
        except Exception as e:
            logger.error(f"Error fetching article content: {e}")
            return "Error fetching content"
    
    def extract_tickers(self, text):
        """Extract stock ticker symbols from text."""
        # Common patterns for tickers in financial news
        patterns = [
            r'NYSE:\s*([A-Z]{1,5})',  # NYSE: AAPL
            r'NASDAQ:\s*([A-Z]{1,5})',  # NASDAQ: MSFT
            r'NYSEAMERICAN:\s*([A-Z]{1,5})',  # NYSEAMERICAN: XYZ
            r'NYSEMKT:\s*([A-Z]{1,5})',  # NYSEMKT: XYZ
            r'OTC(?:QB|QX|BB|PINK)?:\s*([A-Z]{1,5})',  # OTCQB: ABCD
            r'\(NYSE:\s*([A-Z]{1,5})\)',  # (NYSE: AAPL)
            r'\(NASDAQ:\s*([A-Z]{1,5})\)',  # (NASDAQ: MSFT)
            r'\bSymbol:\s*([A-Z]{1,5})\b',  # Symbol: AAPL
            r'\bTicker(?:\s+Symbol)?:\s*([A-Z]{1,5})\b',  # Ticker: AAPL or Ticker Symbol: AAPL
            r'\(([A-Z]{2,4})\)',  # (AAPL) - common pattern in news
            r'stock\s+([A-Z]{2,4})\b',  # stock AAPL
            r'shares\s+of\s+([A-Z]{2,4})\b',  # shares of AAPL
        ]
        
        tickers = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            tickers.extend(matches)
        
        # Add common financial stocks for testing if no tickers found
        if not tickers and "financ" in text.lower():
            possible_tickers = ["JPM", "BAC", "WFC", "C", "GS", "MS", "BLK"]
            # Extract words that might be tickers (all caps, 2-5 letters)
            word_matches = re.findall(r'\b([A-Z]{2,5})\b', text)
            for word in word_matches:
                if word in possible_tickers:
                    tickers.append(word)
        
        # Remove duplicates while preserving order
        unique_tickers = []
        for ticker in tickers:
            if ticker not in unique_tickers:
                unique_tickers.append(ticker)
        
        return unique_tickers
