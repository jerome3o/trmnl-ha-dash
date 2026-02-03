FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (including CJK fonts for Chinese character support)
RUN apt-get update && apt-get install -y \
    imagemagick \
    fonts-dejavu-core \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY static/ ./static/

# Create directories for runtime data
RUN mkdir -p data static/images

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["python", "-m", "app.main"]
