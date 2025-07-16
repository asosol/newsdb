import asyncio
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup
import pandas as pd
import time
from typing import List, Dict
import re
from datetime import datetime

# --- DB imports ---
import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values
from dateutil import parser


class FinvizScraper:
    def __init__(self):
        self.base_url = "https://finviz.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

        # --- DB config ---
        # load_dotenv()
        self.db_config = {
            'host': os.getenv('PG_HOST', 'localhost'),
            'port': os.getenv('PG_PORT', '5432'),
            'database': os.getenv('PG_DB', 'searchdb'),
            'user': os.getenv('PG_USER', 'hiteshjuneja'),
            'password': os.getenv('PG_PASS', '')
        }

    async def get_page(self, session: AsyncSession, url: str) -> str:
        """Fetch a single page with curl_cffi"""
        try:
            response = await session.get(
                url,
                headers=self.headers,
                impersonate="chrome110",
                timeout=30
            )
            return response.text
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return ""

    async def extract_tickers_from_page(self, html: str, page_num: int) -> List[str]:
        """Extract ticker symbols from screener page"""
        soup = BeautifulSoup(html, 'html.parser')
        tickers = []

        # Debug: Save HTML to file for inspection
        with open(f'debug_page_{page_num}.html', 'w', encoding='utf-8') as f:
            f.write(html[:5000])  # Save first 5000 chars for debugging

        # Method 1: Look for ticker links with various possible classes
        ticker_patterns = [
            {'tag': 'a', 'class': 'screener-link-primary'},
            {'tag': 'a', 'class': 'screener-link'},
            {'tag': 'a', 'attrs': {'href': re.compile(r'/quote\.ashx\?t=')}},
        ]

        for pattern in ticker_patterns:
            if 'attrs' in pattern:
                elements = soup.find_all(pattern['tag'], attrs=pattern['attrs'])
            else:
                elements = soup.find_all(pattern['tag'], class_=pattern.get('class'))

            for elem in elements:
                ticker = elem.text.strip()
                if ticker and len(ticker) <= 5 and ticker.isalpha():  # Basic ticker validation
                    tickers.append(ticker)

        # Method 2: Look for table with id "screener-views-table"
        table = soup.find('table', {'id': 'screener-views-table'})
        if table:
            print(f"Found screener table on page {page_num}")
            rows = table.find_all('tr')[1:]  # Skip header
            for row in rows:
                cells = row.find_all('td')
                if len(cells) > 1:  # Usually ticker is in second column
                    ticker_cell = cells[1].find('a')
                    if ticker_cell:
                        ticker = ticker_cell.text.strip()
                        if ticker:
                            tickers.append(ticker)

        # Method 3: Look for any table and try to find tickers
        if not tickers:
            all_tables = soup.find_all('table')
            print(f"Found {len(all_tables)} tables on page {page_num}")

            for table in all_tables:
                # Check if table has screener data
                table_text = table.text
                if 'Ticker' in table_text or 'Symbol' in table_text:
                    rows = table.find_all('tr')
                    for row in rows:
                        links = row.find_all('a', href=re.compile(r'/quote\.ashx\?t='))
                        for link in links:
                            ticker = link.text.strip()
                            if ticker and len(ticker) <= 5:
                                tickers.append(ticker)

        # Remove duplicates and return
        unique_tickers = list(set(tickers))
        print(f"Page {page_num}: Found {len(unique_tickers)} unique tickers")
        return unique_tickers

    async def get_all_tickers(self) -> List[str]:
        """Get all tickers from screener pages"""
        all_tickers = []

        async with AsyncSession() as session:
            # First, let's test with just the first page
            base_url = "https://finviz.com/screener.ashx?v=111&f=sh_float_u10"

            print(f"Fetching first page: {base_url}")
            html = await self.get_page(session, base_url)

            if html:
                print(f"Page loaded, length: {len(html)}")
                tickers = await self.extract_tickers_from_page(html, 1)
                all_tickers.extend(tickers)

                # If we found tickers on first page, continue with others
                if tickers:
                    tasks = []
                    page_nums = []

                    for page in [21, 41, 61, 81]:
                        url = f"{base_url}&r={page}"
                        tasks.append(self.get_page(session, url))
                        page_nums.append(page)

                    print(f"Fetching remaining {len(tasks)} pages...")
                    pages_html = await asyncio.gather(*tasks)

                    for page_num, html in zip(page_nums, pages_html):
                        if html:
                            page_tickers = await self.extract_tickers_from_page(html, page_num)
                            all_tickers.extend(page_tickers)
                else:
                    print("No tickers found on first page. Checking HTML structure...")
                    # Save full HTML for debugging
                    with open('debug_full_page.html', 'w', encoding='utf-8') as f:
                        f.write(html)
                    print("Full HTML saved to debug_full_page.html for inspection")

        return list(set(all_tickers))  # Remove duplicates

    async def extract_news_from_quote_page(self, ticker: str, html: str) -> List[Dict]:
        """Extract news articles from quote page"""
        soup = BeautifulSoup(html, 'html.parser')
        news_items = []

        try:
            # Find the news table - Finviz usually has news in a table
            news_table = soup.find('table', {'id': 'news-table'})

            if news_table:
                rows = news_table.find_all('tr')

                current_date = None
                for row in rows:
                    # Get date/time info
                    date_cell = row.find('td', {'align': 'right', 'width': '130'})
                    if date_cell:
                        date_text = date_cell.text.strip()
                        # If it's a full date (e.g., "Nov-15-24")
                        if '-' in date_text and len(date_text) > 7:
                            current_date = date_text
                        # If it's just a time (e.g., "06:45AM"), use current date
                        elif current_date:
                            date_text = f"{current_date} {date_text}"

                    # Get news link and title
                    news_cell = row.find('td', {'align': 'left'})
                    if news_cell:
                        link_elem = news_cell.find('a', {'class': 'tab-link-news'})
                        if link_elem:
                            news_title = link_elem.text.strip()
                            news_url = link_elem.get('href', '')

                            # Get source (usually in same cell, after the link)
                            source = ''
                            source_span = news_cell.find('span')
                            if source_span:
                                source = source_span.text.strip()

                            news_items.append({
                                'ticker': ticker,
                                'title': news_title,
                                'url': news_url,
                                'source': source,
                                'date': date_text if date_cell else ''
                            })

            print(f"  Found {len(news_items)} news articles for {ticker}")

        except Exception as e:
            print(f"Error extracting news for {ticker}: {e}")

        return news_items

    async def extract_quote_data(self, ticker: str, html: str) -> Dict:
        """Extract float, price, and volume from quote page"""
        soup = BeautifulSoup(html, 'html.parser')
        data = {'ticker': ticker, 'shares_float': None, 'shares_float_m': None, 'price': None, 'volume': None}

        try:
            # Find the snapshot table - try multiple selectors
            snapshot_table = None
            table_selectors = [
                {'class': 'snapshot-table2'},
                {'class': 'snapshot-table'},
                {'class': 'table-dark-row'}
            ]

            for selector in table_selectors:
                snapshot_table = soup.find('table', selector)
                if snapshot_table:
                    break

            if not snapshot_table:
                # Try to find any table with financial data
                all_tables = soup.find_all('table')
                for table in all_tables:
                    if 'Shs Float' in table.text or 'Price' in table.text:
                        snapshot_table = table
                        break

            if snapshot_table:
                # Get all cells
                cells = snapshot_table.find_all('td')

                for i in range(0, len(cells), 2):  # Data usually in pairs (label, value)
                    if i + 1 < len(cells):
                        label = cells[i].text.strip()
                        value = cells[i + 1].text.strip()

                        # Look for Shs Float
                        if 'Shs Float' in label:
                            if 'M' in value:
                                data['shares_float'] = float(value.replace('M', '')) * 1_000_000
                                data['shares_float_m'] = float(value.replace('M', ''))
                            elif 'B' in value:
                                data['shares_float'] = float(value.replace('B', '')) * 1_000_000_000
                                data['shares_float_m'] = float(value.replace('B', '')) * 1000  # Convert B to M
                            elif value != '-':
                                try:
                                    data['shares_float'] = float(value.replace(',', ''))
                                    data['shares_float_m'] = data['shares_float'] / 1_000_000
                                except:
                                    pass

                        # Look for Price
                        elif label == 'Price':
                            price_match = re.search(r'([\d.]+)', value)
                            if price_match:
                                data['price'] = float(price_match.group(1))

                        # Look for Volume
                        elif label == 'Volume':
                            try:
                                data['volume'] = int(value.replace(',', ''))
                            except:
                                pass

            # Alternative method to find price
            if data['price'] is None:
                # Look for price in various possible locations
                price_selectors = [
                    {'class': 'quote-price'},
                    {'class': 'quote-last'},
                    {'id': 'quote-price'}
                ]

                for selector in price_selectors:
                    price_elem = soup.find('div', selector) or soup.find('span', selector)
                    if price_elem:
                        price_match = re.search(r'([\d.]+)', price_elem.text)
                        if price_match:
                            data['price'] = float(price_match.group(1))
                            break

        except Exception as e:
            print(f"Error extracting data for {ticker}: {e}")

        return data

    async def get_quotes_and_news_batch(self, tickers: List[str], batch_size: int = 5) -> tuple[List[Dict], List[Dict]]:
        """Get quote data and news for multiple tickers in batches"""
        all_quotes = []
        all_news = []

        async with AsyncSession() as session:
            for i in range(0, len(tickers), batch_size):
                batch = tickers[i:i + batch_size]
                tasks = []

                for ticker in batch:
                    url = f"{self.base_url}/quote.ashx?t={ticker}"
                    tasks.append(self.get_page(session, url))

                print(f"Fetching quotes and news for batch {i // batch_size + 1} ({len(batch)} tickers)...")
                pages_html = await asyncio.gather(*tasks)

                # Extract data from each page
                for ticker, html in zip(batch, pages_html):
                    if html:
                        # Extract quote data
                        quote_data = await self.extract_quote_data(ticker, html)
                        all_quotes.append(quote_data)

                        # Extract news data
                        news_data = await self.extract_news_from_quote_page(ticker, html)
                        all_news.extend(news_data)

                        print(
                            f"  {ticker}: Price=${quote_data['price']}, Float={quote_data['shares_float_m']}M, Volume={quote_data['volume']}, News={len(news_data)}")

                # Small delay between batches
                await asyncio.sleep(1)

        return all_quotes, all_news

    def save_to_db(self, quotes_df: pd.DataFrame, news_df: pd.DataFrame) -> None:
        """
        Write quotes and news into Postgres.
        * volume stored in millions
        * article_summary left NULL
        """
        if quotes_df.empty and news_df.empty:
            print("Nothing to save.")
            return

        # --- transform quotes ---
        # Convert numeric volume → millions
        if 'volume' in quotes_df.columns:
            quotes_df['volume'] = pd.to_numeric(quotes_df['volume'], errors='coerce')
            quotes_df.loc[quotes_df['volume'].notna(), 'volume'] = (
                quotes_df.loc[quotes_df['volume'].notna(), 'volume'] / 1_000_000
            ).round(3)

        # Standard column names for DB
        quotes_df = quotes_df.rename(columns={
            'price': 'current_price',
            'shares_float': 'float_shares',
        })

        # Ensure expected columns exist
        for col in ['company_name', 'market_cap', 'current_price', 'volume', 'float_shares']:
            if col not in quotes_df.columns:
                quotes_df[col] = None

        # --- filter out rows with incomplete data (skip bogus tickers) ---
        quotes_df = quotes_df[
            quotes_df['current_price'].notna() &
            quotes_df['float_shares'].notna()
        ]
        valid_tickers = set(quotes_df['ticker'])
        news_df = news_df[news_df['ticker'].isin(valid_tickers)]

        if quotes_df.empty and news_df.empty:
            print("No valid data after filtering. Nothing saved.")
            return

        quote_cols = ['ticker', 'company_name', 'current_price',
                      'market_cap', 'volume', 'float_shares']
        quote_vals = (
            quotes_df[quote_cols]
            .where(pd.notna(quotes_df[quote_cols]), None)
            .values
            .tolist()
        )

        # --- news transform ---
        news_rows = []
        for _, row in news_df.iterrows():
            try:
                art_date = parser.parse(row['date']) if row['date'] else None
            except Exception:
                art_date = None
            news_rows.append((
                row['ticker'],
                row['title'],
                None,           # summary NULL
                row['url'],
                art_date
            ))

        # --- connect & truncate tables ---
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()

        execute_values(
            cur,
            """
            INSERT INTO stocks (ticker, company_name, current_price, market_cap, volume, float_shares)
            VALUES %s;
            """,
            quote_vals
        )

        execute_values(
            cur,
            """
            INSERT INTO stock_articles (ticker, article_title, article_summary,
                                        article_url, article_date)
            VALUES %s;
            """,
            news_rows
        )

        conn.commit()
        cur.close()
        conn.close()
        print("✔ Data saved to DB")

    async def scrape_all(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Main method to scrape all data"""
        # Step 1: Get all tickers
        print("Step 1: Getting all tickers from screener...")
        tickers = await self.get_all_tickers()
        print(f"Found {len(tickers)} unique tickers")

        if not tickers:
            print("\nNo tickers found. Please check:")
            print("1. The URL is correct")
            print("2. You have internet connection")
            print("3. Check debug_full_page.html for the actual page content")
            return pd.DataFrame(), pd.DataFrame()

        # Step 2: Get quotes and news for all tickers
        print("\nStep 2: Getting quote data and news for all tickers...")
        quotes_data, news_data = await self.get_quotes_and_news_batch(tickers)

        # Convert to DataFrames
        quotes_df = pd.DataFrame(quotes_data)
        news_df = pd.DataFrame(news_data)

        # Save to DB
        self.save_to_db(quotes_df, news_df)

        return quotes_df, news_df


# Example usage
async def main():
    scraper = FinvizScraper()

    # Scrape all data
    quotes_df, news_df = await scraper.scrape_all()

    if len(quotes_df) > 0:
        # Display results
        print("\nScraping completed!")
        print(f"Total tickers scraped: {len(quotes_df)}")
        print(f"Total news articles: {len(news_df)}")

        print("\nFirst 10 quotes:")
        print(quotes_df[['ticker', 'shares_float_m', 'price', 'volume']].head(10))

        # Show sample news articles
        if len(news_df) > 0:
            print("\nSample news articles (first 5):")
            for _, article in news_df.head(5).iterrows():
                print(f"\n{article['ticker']} - {article['date']}")
                print(f"Title: {article['title']}")
                print(f"Source: {article['source']}")
                print(f"URL: {article['url']}")

        # Show summary statistics
        print("\nSummary:")
        print(f"Tickers with valid float data: {quotes_df['shares_float'].notna().sum()}")
        print(f"Tickers with valid price data: {quotes_df['price'].notna().sum()}")
        print(f"Tickers with valid volume data: {quotes_df['volume'].notna().sum()}")

        # Show float statistics in millions
        if quotes_df['shares_float_m'].notna().any():
            print(f"\nFloat statistics (in millions):")
            print(f"  Min: {quotes_df['shares_float_m'].min():.2f}M")
            print(f"  Max: {quotes_df['shares_float_m'].max():.2f}M")
            print(f"  Average: {quotes_df['shares_float_m'].mean():.2f}M")

        # Show news statistics by ticker
        if len(news_df) > 0:
            news_counts = news_df.groupby('ticker').size().sort_values(ascending=False)
            print(f"\nTop 10 tickers by news count:")
            print(news_counts.head(10))
    else:
        print("\nNo data scraped. Please check the debug files for more information.")


if __name__ == "__main__":
    asyncio.run(main())