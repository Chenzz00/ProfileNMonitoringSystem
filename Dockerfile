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
# Install system libraries
# =======================
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    libpq-dev \
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
EXPOSE ${PORT}

# =======================
# Start the app
# =======================
CMD bash -c "\
    python manage.py migrate --noinput && \
    python manage.py collectstatic --noinput && \
    gunicorn PPMA.wsgi:application --bind 0.0.0.0:${PORT} --workers 4\
"
