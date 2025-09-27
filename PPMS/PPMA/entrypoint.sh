#!/bin/sh
# Fallback to port 8000 if $PORT not set
PORT=${PORT:-8000}

# Start Gunicorn as pid1 (avoids catatonit errors)
exec gunicorn PPMA.wsgi:application --bind 0.0.0.0:$PORT --workers 4
