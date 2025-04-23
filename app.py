import streamlit as st
from datetime import datetime
import time

from pg_database import NewsDatabase
from news_scraper import PRNewswireScraper
from stock_data import StockDataFetcher

# Init
news_db = NewsDatabase()
scraper = PRNewswireScraper()
stock_fetcher = StockDataFetcher()

# --- State
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = 0
if "auto_refresh_interval" not in st.session_state:
    st.session_state.auto_refresh_interval = 60  # seconds

# --- Layout
st.set_page_config(page_title="Stock News Monitor", layout="wide")
st.title("📈 Stock News Monitor")

# --- Sidebar Filters
st.sidebar.header("Filters")
float_filter_mode = st.sidebar.selectbox("Float Filter Type", ["None", "Less Than", "Greater Than"])
float_threshold = st.sidebar.slider("Float Threshold (Millions)", 0, 300, 20)
show_refresh_button = st.sidebar.button("🔄 Manual Refresh")
clear_articles = st.sidebar.button("🗑️ Clear All Articles")

# --- Delete All Articles
if clear_articles:
    if st.sidebar.checkbox("Are you sure?"):
        news_db.clear_articles()
        st.sidebar.success("All articles deleted!")

# --- Auto Refresh
if time.time() - st.session_state.last_refresh > st.session_state.auto_refresh_interval or show_refresh_button:
    with st.spinner("Refreshing articles..."):
        raw_articles = scraper.get_latest_news(max_pages=1)
        for art in raw_articles:
            if not art.tickers:
                continue
            float_data = stock_fetcher.get_batch_float_data(art.tickers)
            if float_data:
                art.float_data = float_data
                news_db.save_article(art)
    st.session_state.last_refresh = time.time()

# --- Fetch from DB
articles = news_db.get_recent_articles(limit=500)

# --- Apply float filter
def parse_float_string(s):
    try:
        if s.endswith("M"):
            return float(s.replace("M", "")) * 1_000_000
        elif s.endswith("B"):
            return float(s.replace("B", "")) * 1_000_000_000
        else:
            return float(s.replace(",", ""))
    except:
        return None

if float_filter_mode != "None":
    filtered_articles = []
    for article in articles:
        tick = article.tickers[0] if article.tickers else None
        fd = article.float_data.get(tick) if tick else None
        raw_float = parse_float_string(fd.get("float", "N/A")) if fd else None
        if raw_float is not None:
            if float_filter_mode == "Less Than" and raw_float < float_threshold * 1_000_000:
                filtered_articles.append(article)
            elif float_filter_mode == "Greater Than" and raw_float > float_threshold * 1_000_000:
                filtered_articles.append(article)
    articles = filtered_articles

# --- Pagination
per_page = 25
total_pages = max(1, len(articles) // per_page + (1 if len(articles) % per_page else 0))
page = st.number_input("Page", min_value=1, max_value=total_pages, step=1)

# --- Render Table
start = (page - 1) * per_page
end = start + per_page
for article in articles[start:end]:
    with st.container():
        col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 4, 2])
        tick = article.tickers[0] if article.tickers else None
        fd = article.float_data.get(tick) if tick else {}

        col1.markdown(f"**{tick or 'N/A'}**")
        col2.markdown(f"{fd.get('float', 'N/A')}")
        col3.markdown(f"{fd.get('price', 'N/A')}")
        col4.markdown(f"[{article.title}]({article.url})")
        col5.markdown(f"{article.published_date} {article.published_time.strftime('%H:%M') if article.published_time else ''}")

st.caption(f"Last updated: {datetime.utcfromtimestamp(st.session_state.last_refresh).strftime('%Y-%m-%d %H:%M:%S')} UTC")
