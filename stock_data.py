#!/usr/bin/env python3
"""
Module for retrieving stock data from Yahoo Finance.
"""
import logging
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class StockDataFetcher:
    """Class for fetching stock data from Yahoo Finance."""

    def __init__(self, max_workers=5):
        """Initialize with the maximum number of concurrent workers."""
        self.max_workers = max_workers

    def get_float_data(self, ticker):
        """Get float data for a single ticker symbol, or return None if unavailable."""
        try:
            logger.debug(f"Fetching data for ticker: {ticker}")
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    stock = yf.Ticker(ticker)
                    info = stock.info
                    # Retrieve floatShares or sharesOutstanding
                    raw_float = info.get('floatShares') or info.get('sharesOutstanding')
                    if not raw_float:
                        logger.warning(f"No float data for {ticker}, skipping")
                        return None
                    # Format the float value
                    if raw_float >= 1_000_000_000:
                        float_str = f"{raw_float / 1_000_000_000:.2f}B"
                    elif raw_float >= 1_000_000:
                        float_str = f"{raw_float / 1_000_000:.2f}M"
                    else:
                        float_str = f"{raw_float:,}"

                    # Market cap
                    market_cap = info.get('marketCap')
                    if isinstance(market_cap, (int, float)):
                        if market_cap >= 1_000_000_000:
                            mcap_str = f"${market_cap / 1_000_000_000:.2f}B"
                        elif market_cap >= 1_000_000:
                            mcap_str = f"${market_cap / 1_000_000:.2f}M"
                        else:
                            mcap_str = f"${market_cap:,}"
                    else:
                        mcap_str = 'N/A'

                    price = info.get('currentPrice', 'N/A')

                    return {
                        'symbol': ticker,
                        'name': info.get('shortName', 'N/A'),
                        'float': float_str,
                        'float_raw': raw_float,
                        'price': price,
                        'market_cap': mcap_str
                    }
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1}/{max_retries} failed for {ticker}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(1)
                    else:
                        raise
        except Exception as e:
            logger.error(f"Error fetching float data for {ticker}: {e}")
        return None

    def get_batch_float_data(self, tickers):
        """Get float data for multiple ticker symbols in parallel, omitting failures."""
        if not tickers:
            return {}
        results = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {executor.submit(self.get_float_data, t): t for t in tickers}
            for fut in as_completed(future_map):
                t = future_map[fut]
                try:
                    data = fut.result()
                    if data is not None:
                        results[t] = data
                except Exception as e:
                    logger.error(f"Error processing result for {t}: {e}")
        return results
