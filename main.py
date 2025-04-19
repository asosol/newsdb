#!/usr/bin/env python3
"""
Main entry point for the stock news monitoring tool.
"""
import sys
import logging
from PyQt5.QtWidgets import QApplication
from gui import MainWindow

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Initialize and run the application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Stock News Monitor")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
