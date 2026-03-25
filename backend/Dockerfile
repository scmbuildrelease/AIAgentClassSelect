FROM python:3.11-slim
WORKDIR /app

RUN pip install --no-cache-dir flask requests openai beautifulsoup4 flask-cors

COPY app.py .

RUN mkdir -p /data

EXPOSE 8000
CMD ["python", "app.py"]
