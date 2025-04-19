#!/usr/bin/env python3
"""
Module for retrieving stock data from Yahoo Finance.
"""
import logging
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

logger = logging.getLogger(__name__)

class StockDataFetcher:
    """Class for fetching stock data from Yahoo Finance."""
    
    def __init__(self, max_workers=5):
        """Initialize with the maximum number of concurrent workers."""
        self.max_workers = max_workers
    
    def get_float_data(self, ticker):
        """Get float data for a single ticker symbol."""
        try:
            logger.debug(f"Fetching data for ticker: {ticker}")
            
            # Add retry mechanism
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Get stock info from Yahoo Finance
                    stock = yf.Ticker(ticker)
                    
                    # Try to get the float data from different possible fields
                    info = stock.info
                    
                    float_data = {}
                    float_data['symbol'] = ticker
                    float_data['name'] = info.get('shortName', 'N/A')
                    
                    # Try different fields that might contain float information
                    float_value = info.get('floatShares')
                    if float_value is None:
                        float_value = info.get('sharesOutstanding')
                    
                    if float_value:
                        # Format the float value for display
                        if float_value >= 1_000_000_000:
                            float_data['float'] = f"{float_value / 1_000_000_000:.2f}B"
                        elif float_value >= 1_000_000:
                            float_data['float'] = f"{float_value / 1_000_000:.2f}M"
                        else:
                            float_data['float'] = f"{float_value:,}"
                    else:
                        float_data['float'] = 'N/A'
                    
                    # Add other useful info
                    float_data['price'] = info.get('currentPrice', 'N/A')
                    float_data['market_cap'] = info.get('marketCap', 'N/A')
                    
                    # Format market cap for display
                    if isinstance(float_data['market_cap'], (int, float)) and float_data['market_cap'] != 'N/A':
                        if float_data['market_cap'] >= 1_000_000_000:
                            float_data['market_cap'] = f"${float_data['market_cap'] / 1_000_000_000:.2f}B"
                        elif float_data['market_cap'] >= 1_000_000:
                            float_data['market_cap'] = f"${float_data['market_cap'] / 1_000_000:.2f}M"
                        else:
                            float_data['market_cap'] = f"${float_data['market_cap']:,}"
                    
                    return float_data
                
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1}/{max_retries} failed for {ticker}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(1)  # Wait before retrying
                    else:
                        raise
            
        except Exception as e:
            logger.error(f"Error fetching float data for {ticker}: {e}")
            return {
                'symbol': ticker,
                'name': 'Error',
                'float': 'N/A', 
                'price': 'N/A',
                'market_cap': 'N/A'
            }
    
    def get_batch_float_data(self, tickers):
        """Get float data for multiple ticker symbols in parallel."""
        if not tickers:
            return {}
        
        results = {}
        
        # Use ThreadPoolExecutor to fetch data in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_ticker = {executor.submit(self.get_float_data, ticker): ticker for ticker in tickers}
            
            # Process results as they complete
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    data = future.result()
                    results[ticker] = data
                except Exception as e:
                    logger.error(f"Error processing result for {ticker}: {e}")
                    results[ticker] = {
                        'symbol': ticker,
                        'name': 'Error',
                        'float': 'N/A',
                        'price': 'N/A',
                        'market_cap': 'N/A'
                    }
        
        return results
