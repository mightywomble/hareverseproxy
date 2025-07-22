#!/bin/bash
# run_gunicorn.sh

# Path to your Flask application's directory
APP_DIR="/home/david/code/haproxy_web_app"

# Virtual environment path (if you're using one)
# VENV_PATH="/path/to/your/venv" # Uncomment and set if you are using a venv

# Gunicorn configuration
NUM_WORKERS=3
BIND_ADDRESS="0.0.0.0:5000"
LOG_LEVEL="info"

cd "$APP_DIR" # Quoting for safety

# If using a virtual environment, activate it
# If gunicorn is inside a virtual environment, activate it before running gunicorn
# source $VENV_PATH/bin/activate
# OR, better yet, use the full path to gunicorn directly from the venv if you don't need other venv commands

# Start Gunicorn using its full path
exec /home/david/.local/bin/gunicorn --workers "$NUM_WORKERS" --bind "$BIND_ADDRESS" --log-level "$LOG_LEVEL" app:app
