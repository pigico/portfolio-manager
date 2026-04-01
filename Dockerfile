FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create data directory
RUN mkdir -p /app/data

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
