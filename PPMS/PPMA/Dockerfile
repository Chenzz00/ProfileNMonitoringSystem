# =======================
# Use slim Python base image
# =======================
FROM python:3.11-slim

# =======================
# Set environment variables
# =======================
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=PPMA.settings

# =======================
# Install system libraries (WeasyPrint + MySQL dev headers + compiler)
# =======================
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

# =======================
# Set working directory
# =======================
WORKDIR /app

# =======================
# Copy and install dependencies
# =======================
COPY requirements.txt ./
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# =======================
# Copy project files
# =======================
COPY . .

# =======================
# Expose container port
# =======================
EXPOSE 8080

# =======================
# Start the app
# Runs migrations, collects static files, checks tables, then starts Gunicorn
# =======================
CMD bash -c "\
    python manage.py migrate --verbosity=2 && \
    python manage.py collectstatic --noinput && \
    python -c \"import os,django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','PPMA.settings'); django.setup(); print('=== Migration Complete - Checking Tables ===')\" && \
    gunicorn PPMA.wsgi:application --bind 0.0.0.0:8080 --workers 4\
"
