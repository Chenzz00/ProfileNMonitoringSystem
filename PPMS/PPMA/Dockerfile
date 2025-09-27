# Use slim Python base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system libraries required for WeasyPrint + compiler for pycairo
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
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
# Create working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose port (Railway uses $PORT automatically)
EXPOSE 8000

# Start with Gunicorn
CMD ["sh", "-c", "gunicorn PPMA.wsgi:application --bind 0.0.0.0:${PORT}"]
