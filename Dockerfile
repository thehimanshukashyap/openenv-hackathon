FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire project so Python path resolution works correctly
COPY . .

# Expose port
EXPOSE 7860

# PYTHONPATH ensures `from server.X import Y` resolves from /app
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')"

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
