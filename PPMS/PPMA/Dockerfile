# Use slim Python base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system libraries (WeasyPrint + MySQL dev headers + compiler)
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    default-libmysqlclient-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libcairo2-dev \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libgobject-2.0-0 \
    libglib2.0-0 \
    libgirepository-1.0-1 \
    libxml2 \
    libxslt1.1 \
    fonts-dejavu-core \
    shared-mime-info \
 && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose container port
EXPOSE 8080

# Enhanced startup with database connection testing and verbose output
CMD bash -c "\
    echo '=== Starting Django Application ===' && \
    echo 'Database Configuration:' && \
    echo 'Host: $MYSQLHOST' && \
    echo 'Database: $MYSQLDATABASE' && \
    echo 'User: $MYSQLUSER' && \
    echo 'Port: $MYSQLPORT' && \
    echo '=== Testing Database Connection ===' && \
    python manage.py check --database default && \
    echo '=== Database Connection: SUCCESS ===' && \
    echo '=== Cleaning Old Migrations ===' && \
    rm -f WebApp/migrations/0*.py && \
    echo '=== Creating Migrations ===' && \
    python manage.py makemigrations WebApp && \
    echo '=== Showing Migration Plan ===' && \
    python manage.py showmigrations && \
    echo '=== Applying Migrations ===' && \
    python manage.py migrate --verbosity=2 && \
    echo '=== Migration Complete - Checking Tables ===' && \
    python -c \"
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PPMA.settings')
django.setup()
from django.db import connection
cursor = connection.cursor()
cursor.execute('SHOW TABLES')
tables = cursor.fetchall()
print('Tables in database:', [table[0] for table in tables])
\" && \
    echo '=== Collecting Static Files ===' && \
    python manage.py collectstatic --noinput && \
    echo '=== Starting Gunicorn Server ===' && \
    gunicorn PPMA.wsgi:application --bind 0.0.0.0:8080 --workers 4"
