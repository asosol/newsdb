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
            response = requests.get(self.BASE_URL, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            news_items = soup.select('.card-list-item')
            
            articles = []
            for item in news_items:
                try:
                    # Extract article info
                    title_elem = item.select_one('.card-title')
                    if not title_elem:
                        continue
                    
                    title = title_elem.text.strip()
                    
                    link_elem = title_elem.find('a')
                    if not link_elem or not link_elem.get('href'):
                        continue
                    
                    url = link_elem['href']
                    if not url.startswith('http'):
                        url = f"https://www.prnewswire.com{url}"
                    
                    date_elem = item.select_one('.card-date')
                    published_date = datetime.now()
                    if date_elem:
                        date_str = date_elem.text.strip()
                        try:
                            published_date = datetime.strptime(date_str, '%b %d, %Y')
                        except ValueError:
                            logger.warning(f"Could not parse date: {date_str}")
                    
                    # Get article content
                    summary = self.get_article_content(url)
                    
                    # Extract tickers
                    tickers = self.extract_tickers(title + " " + summary)
                    
                    # Only include articles with tickers
                    if tickers:
                        article = NewsArticle(title, summary, url, published_date, tickers)
                        articles.append(article)
                
                except Exception as e:
                    logger.error(f"Error processing news item: {e}")
                    continue
            
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
