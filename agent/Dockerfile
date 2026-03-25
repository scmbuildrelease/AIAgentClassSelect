# Use Python slim image
FROM python:3.11-slim

WORKDIR /app

# Copy only requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Set environment variable for OpenAI key
ENV OPENAI_API_KEY=${OPENAI_API_KEY}

# Default command
CMD ["python", "scrape_courses.py"]
