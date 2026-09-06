FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir discord.py python-dotenv

# Copy the bot
COPY app.py .

# Run the bot
CMD ["python", "app.py"]
