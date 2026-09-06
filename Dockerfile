FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install all dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot code
COPY app.py .

# Expose port
EXPOSE 8080

# Run the bot
CMD ["python", "app.py"]
