FROM python:3.11-slim

# Install system dependencies for Selenium + Chrome
RUN apt-get update && apt-get install -y \
    wget gnupg unzip curl chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Expose FastAPI port
EXPOSE 5000

# Run server with Uvicorn
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "5000"]
