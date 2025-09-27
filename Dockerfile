# Use slim Python base image
FROM python:3.11-slim

# Install system libraries required for WeasyPrint
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
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

# Set working directory inside container
WORKDIR /app

# Copy Python dependencies and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your entire project into the container
COPY . .

# Command for running Django with Gunicorn on Railway
CMD ["gunicorn", "PPMA.wsgi:application", "--bind", "0.0.0.0:$PORT", "--workers", "4"]
