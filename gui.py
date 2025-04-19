#!/usr/bin/env python3
"""
GUI module for the stock news monitoring tool.
"""
import sys
import logging
import threading
import webbrowser
import time
from datetime import datetime
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
    QTableWidgetItem, QPushButton, QLabel, QTextEdit, QSplitter, 
    QHeaderView, QAbstractItemView, QStatusBar, QMenu, QAction, 
    QSystemTrayIcon, QStyle, QApplication, QMessageBox, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QIcon, QFont, QColor

from news_scraper import PRNewswireScraper, NewsArticle
from stock_data import StockDataFetcher
from database import NewsDatabase

logger = logging.getLogger(__name__)

class DataFetcherThread(QThread):
    """Thread for fetching news and stock data in the background."""
    
    update_signal = pyqtSignal(list)
    status_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scraper = PRNewswireScraper()
        self.stock_data = StockDataFetcher()
        self.db = NewsDatabase()
        self.running = True
    
    def run(self):
        """Main thread execution logic."""
        while self.running:
            try:
                self.status_signal.emit("Fetching news...")
                self.progress_signal.emit(0)
                
                # Fetch latest news
                articles = self.scraper.get_latest_news()
                self.progress_signal.emit(30)
                
                if not articles:
                    self.status_signal.emit("No new articles found")
                    self.progress_signal.emit(100)
                    time.sleep(60)  # Wait for 1 minute before next fetch
                    continue
                
                self.status_signal.emit(f"Found {len(articles)} articles. Fetching stock data...")
                
                # Get unique tickers from all articles
                all_tickers = set()
                for article in articles:
                    all_tickers.update(article.tickers)
                
                # Fetch float data for all tickers
                if all_tickers:
                    float_data = self.stock_data.get_batch_float_data(list(all_tickers))
                    self.progress_signal.emit(60)
                    
                    # Attach float data to articles
                    for article in articles:
                        article.float_data = {ticker: float_data.get(ticker, {}) for ticker in article.tickers}
                    
                    # Save articles to database
                    self.status_signal.emit("Saving articles to database...")
                    for article in articles:
                        self.db.save_article(article)
                    
                    self.progress_signal.emit(90)
                
                # Get recent articles from database including float data
                db_articles = self.db.get_recent_articles()
                self.progress_signal.emit(100)
                
                # Emit the signal with the articles
                self.update_signal.emit(db_articles)
                self.status_signal.emit(f"Updated {len(articles)} articles. Next update in 60 seconds.")
                
                # Wait for 1 minute before the next fetch
                time.sleep(60)
            
            except Exception as e:
                logger.error(f"Error in data fetcher thread: {e}")
                self.status_signal.emit(f"Error: {str(e)}")
                time.sleep(60)  # Wait for 1 minute before retry
    
    def stop(self):
        """Stop the thread execution."""
        self.running = False
        self.wait()


class MainWindow(QMainWindow):
    """Main window for the stock news monitoring application."""
    
    def __init__(self):
        super().__init__()
        
        self.db = NewsDatabase()
        
        self.init_ui()
        self.start_data_fetcher()
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Stock News Monitoring Tool")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Create splitter for resizable areas
        splitter = QSplitter(Qt.Vertical)
        
        # Top widget - News table
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        
        # News table
        self.news_table = QTableWidget()
        self.news_table.setColumnCount(4)
        self.news_table.setHorizontalHeaderLabels(["Ticker", "Float", "Price", "Headline"])
        self.news_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)  # Stretch headline column
        self.news_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.news_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.news_table.cellClicked.connect(self.show_article_details)
        
        top_layout.addWidget(self.news_table)
        
        # Bottom widget - Article details
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        
        self.article_title = QLabel("Select an article to view details")
        self.article_title.setFont(QFont("Arial", 12, QFont.Bold))
        self.article_title.setWordWrap(True)
        
        self.ticker_info = QLabel("")
        self.ticker_info.setFont(QFont("Arial", 10))
        
        self.article_summary = QTextEdit()
        self.article_summary.setReadOnly(True)
        
        # Create horizontal layout for buttons
        button_layout = QHBoxLayout()
        
        self.open_button = QPushButton("Open in Browser")
        self.open_button.clicked.connect(self.open_in_browser)
        self.open_button.setEnabled(False)
        
        self.refresh_button = QPushButton("Refresh Now")
        self.refresh_button.clicked.connect(self.refresh_data)
        
        button_layout.addWidget(self.open_button)
        button_layout.addStretch()
        button_layout.addWidget(self.refresh_button)
        
        # Add widgets to bottom layout
        bottom_layout.addWidget(self.article_title)
        bottom_layout.addWidget(self.ticker_info)
        bottom_layout.addWidget(self.article_summary)
        bottom_layout.addLayout(button_layout)
        
        # Add widgets to splitter
        splitter.addWidget(top_widget)
        splitter.addWidget(bottom_widget)
        
        # Set initial sizes for splitter areas (70% top, 30% bottom)
        splitter.setSizes([int(self.height() * 0.7), int(self.height() * 0.3)])
        
        # Add splitter to main layout
        main_layout.addWidget(splitter)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.status_label = QLabel("Starting...")
        self.status_bar.addWidget(self.status_label, 1)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # System tray icon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        
        # Create tray menu
        tray_menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close_application)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
        # Current article URL
        self.current_article_url = None
    
    def start_data_fetcher(self):
        """Start the background thread for fetching data."""
        self.data_fetcher = DataFetcherThread(self)
        self.data_fetcher.update_signal.connect(self.update_news_table)
        self.data_fetcher.status_signal.connect(self.update_status)
        self.data_fetcher.progress_signal.connect(self.update_progress)
        self.data_fetcher.start()
    
    def update_news_table(self, articles):
        """Update the news table with the fetched articles."""
        self.news_table.setRowCount(0)  # Clear current rows
        
        if not articles:
            self.status_label.setText("No articles found")
            return
        
        for article in articles:
            row = self.news_table.rowCount()
            self.news_table.insertRow(row)
            
            # Get the first ticker and its float data if available
            ticker_text = ', '.join(article['tickers']) if article['tickers'] else 'N/A'
            
            float_text = 'N/A'
            price_text = 'N/A'
            
            if article['tickers'] and article['float_data']:
                first_ticker = article['tickers'][0]
                if first_ticker in article['float_data']:
                    float_data = article['float_data'][first_ticker]
                    float_text = float_data.get('float', 'N/A')
                    price_text = float_data.get('price', 'N/A')
                    if isinstance(price_text, (int, float)):
                        price_text = f"${price_text:.2f}"
            
            # Set table items
            ticker_item = QTableWidgetItem(ticker_text)
            ticker_item.setData(Qt.UserRole, article['id'])  # Store article ID for later retrieval
            
            self.news_table.setItem(row, 0, ticker_item)
            self.news_table.setItem(row, 1, QTableWidgetItem(str(float_text)))
            self.news_table.setItem(row, 2, QTableWidgetItem(str(price_text)))
            self.news_table.setItem(row, 3, QTableWidgetItem(article['title']))
        
        self.news_table.resizeColumnsToContents()
        self.news_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)  # Ensure headline column stretches
    
    def show_article_details(self, row, column):
        """Show the details of the selected article."""
        article_id = self.news_table.item(row, 0).data(Qt.UserRole)
        article = self.db.get_article_by_id(article_id)
        
        if not article:
            return
        
        self.article_title.setText(article['title'])
        
        # Format ticker information
        ticker_info = ""
        if article['tickers']:
            ticker_info_parts = []
            for ticker in article['tickers']:
                if ticker in article['float_data']:
                    data = article['float_data'][ticker]
                    ticker_info_parts.append(
                        f"{ticker} - {data.get('name', 'N/A')} - "
                        f"Float: {data.get('float', 'N/A')} - "
                        f"Price: {data.get('price', 'N/A')} - "
                        f"Market Cap: {data.get('market_cap', 'N/A')}"
                    )
                else:
                    ticker_info_parts.append(f"{ticker} - No data available")
            
            ticker_info = "\n".join(ticker_info_parts)
        
        self.ticker_info.setText(ticker_info)
        
        # Set article summary
        self.article_summary.setText(article['summary'])
        
        # Enable open button and store URL
        self.open_button.setEnabled(True)
        self.current_article_url = article['url']
    
    def open_in_browser(self):
        """Open the current article in a web browser."""
        if self.current_article_url:
            try:
                webbrowser.open(self.current_article_url)
            except Exception as e:
                logger.error(f"Error opening URL: {e}")
                QMessageBox.warning(self, "Error", f"Could not open URL: {str(e)}")
    
    def refresh_data(self):
        """Manually trigger a data refresh."""
        self.status_label.setText("Manually refreshing data...")
        self.progress_bar.setValue(0)
        
        # Create a new thread to avoid blocking the UI
        refresh_thread = threading.Thread(target=self._refresh_data_thread)
        refresh_thread.daemon = True
        refresh_thread.start()
    
    def _refresh_data_thread(self):
        """Background thread for manual data refresh."""
        try:
            scraper = PRNewswireScraper()
            stock_data = StockDataFetcher()
            
            # Fetch latest news
            articles = scraper.get_latest_news()
            
            # Update progress in UI thread
            QApplication.instance().processEvents()
            self.progress_bar.setValue(30)
            
            if not articles:
                self.status_label.setText("No new articles found")
                self.progress_bar.setValue(100)
                return
            
            # Get unique tickers from all articles
            all_tickers = set()
            for article in articles:
                all_tickers.update(article.tickers)
            
            # Fetch float data for all tickers
            if all_tickers:
                float_data = stock_data.get_batch_float_data(list(all_tickers))
                self.progress_bar.setValue(60)
                
                # Attach float data to articles
                for article in articles:
                    article.float_data = {ticker: float_data.get(ticker, {}) for ticker in article.tickers}
                
                # Save articles to database
                for article in articles:
                    self.db.save_article(article)
                
                self.progress_bar.setValue(90)
            
            # Get recent articles from database including float data
            db_articles = self.db.get_recent_articles()
            self.progress_bar.setValue(100)
            
            # Update UI in main thread
            self.update_news_table(db_articles)
            self.status_label.setText(f"Updated {len(articles)} articles")
        
        except Exception as e:
            logger.error(f"Error in refresh thread: {e}")
            self.status_label.setText(f"Error: {str(e)}")
    
    def update_status(self, status):
        """Update the status bar message."""
        self.status_label.setText(status)
    
    def update_progress(self, value):
        """Update the progress bar value."""
        self.progress_bar.setValue(value)
    
    def closeEvent(self, event):
        """Handle the window close event."""
        reply = QMessageBox.question(
            self, 
            'Exit Confirmation',
            'Do you want to exit the application?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.close_application()
            event.accept()
        else:
            # Minimize to system tray instead of closing
            self.hide()
            event.ignore()
    
    def close_application(self):
        """Properly close the application, stopping background threads."""
        try:
            if hasattr(self, 'data_fetcher'):
                self.data_fetcher.stop()
            
            self.tray_icon.hide()
            QApplication.quit()
        except Exception as e:
            logger.error(f"Error closing application: {e}")
