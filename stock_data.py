#!/usr/bin/env python3
"""
Module for retrieving stock float, price, and market-cap from Yahoo Finance.
"""
import time
import yfinance as yf
import requests



class StockDataFetcher:
    """Fetch stock float, price & market-cap via yfinance in parallel."""

    def __init__(self, max_workers=5):
        self.max_workers = max_workers

    def get_float_data(self, ticker):
        """Return a dict with 'symbol', 'name', 'float', 'price', 'market_cap' or None."""
        max_retries = 3
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        })
        for attempt in range(max_retries):
            try:
                stock = yf.Ticker(ticker)
                info = stock.info

                # raw share count
                raw = info.get('floatShares') or info.get('sharesOutstanding')
                if not raw:
                    return None

                # convert everything below 1B into millions (M)
                if raw >= 1_000_000_000:
                    float_str = f"{raw / 1_000_000_000:.2f}B"
                else:
                    float_str = f"{raw / 1_000_000:.2f}M"

                # market cap
                mc = info.get('marketCap') or 0
                if mc >= 1_000_000_000:
                    mcap_str = f"${mc / 1_000_000_000:.2f}B"
                else:
                    mcap_str = f"${mc / 1_000_000:.2f}M"

                price = info.get('currentPrice', 'N/A')
                name  = info.get('shortName', 'N/A')

                return {
                    'symbol':    ticker,
                    'name':      name,
                    'float':     float_str,
                    'float_raw': raw,
                    'price':     price,
                    'market_cap': mcap_str
                }

            except Exception:
                # retry once per second
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return None

    def get_batch_float_data(self, tickers):
        """Fetch multiple tickers in parallel and omit any None results."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = {}
        if not tickers:
            return results

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.get_float_data, t): t for t in tickers}
            for fut in as_completed(futures):
                sym = futures[fut]
                try:
                    data = fut.result()
                    if data:
                        results[sym] = data
                except:
                    pass

        return results


