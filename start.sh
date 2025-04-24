#!/bin/bash
source venv/bin/activate
export $(cat .env | xargs)

# Start the Flask background thread (scraper)
python3 main.py &

# Start Gunicorn server
exec gunicorn -w 4 -b 0.0.0.0:8000 run:app


