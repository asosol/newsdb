#!/usr/bin/env python3
"""
Module for retrieving stock float, price, and market-cap from Yahoo Finance using curl_cffi.
"""
import time
from curl_cffi import requests as curl_requests
from concurrent.futures import ThreadPoolExecutor, as_completed

class StockDataFetcher:
    """Fetch stock float, price & market-cap via Yahoo Finance APIs with curl_cffi."""

    def __init__(self, max_workers=5):
        self.max_workers = max_workers

    def get_float_data(self, ticker):
        """Return a dict with 'symbol', 'name', 'float', 'price', 'market_cap' or None."""
        max_retries = 3
        url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules=summaryDetail,price,defaultKeyStatistics"

        for attempt in range(max_retries):
            try:
                resp = curl_requests.get(url, impersonate="chrome110", timeout=10)
                data = resp.json()

                quoteSummary = data.get("quoteSummary", {}).get("result", [{}])[0]
                price_info = quoteSummary.get("price", {})
                summary_info = quoteSummary.get("summaryDetail", {})
                stats_info = quoteSummary.get("defaultKeyStatistics", {})

                # Get floatShares
                raw = stats_info.get('floatShares', {}).get('raw') or summary_info.get('sharesOutstanding', {}).get('raw')
                if not raw:
                    return None

                if raw >= 1_000_000_000:
                    float_str = f"{raw / 1_000_000_000:.2f}B"
                else:
                    float_str = f"{raw / 1_000_000:.2f}M"

                # Market cap
                mc = price_info.get('marketCap', {}).get('raw') or 0
                if mc >= 1_000_000_000:
                    mcap_str = f"${mc / 1_000_000_000:.2f}B"
                else:
                    mcap_str = f"${mc / 1_000_000:.2f}M"

                price = price_info.get('regularMarketPrice', {}).get('raw', 'N/A')
                name = price_info.get('shortName', 'N/A')

                return {
                    'symbol': ticker,
                    'name': name,
                    'float': float_str,
                    'float_raw': raw,
                    'price': price,
                    'market_cap': mcap_str
                }

            except Exception as e:
                print(f"Retrying {ticker} due to {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None

    def get_batch_float_data(self, tickers):
        """Fetch multiple tickers in parallel and omit any None results."""
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
