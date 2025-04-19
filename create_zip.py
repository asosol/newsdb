import os
import zipfile
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def zip_directory(path, zip_file):
    for root, dirs, files in os.walk(path):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, os.path.dirname(path))
            logger.info(f"Adding {rel_path} to zip")
            zip_file.write(file_path, rel_path)

try:
    with zipfile.ZipFile('stocknews_monitor.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add main project files
        for filename in ['app.py', 'main.py', 'models.py', 'news_scraper.py', 
                        'pg_database.py', 'run.py', 'stock_data.py']:
            if os.path.exists(filename):
                logger.info(f"Adding {filename} to zip")
                zipf.write(filename, os.path.join('stocknews_monitor', filename))
        
        # Add template files
        zip_directory('templates', zipf)
        
        # Add static files if they exist
        if os.path.exists('static'):
            zip_directory('static', zipf)
    
    logger.info("Zip file created successfully!")
except Exception as e:
    logger.error(f"Error creating zip file: {e}")