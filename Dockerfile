FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Expose local tailor & dashboard port
EXPOSE 8765

ENV TAILOR_HOST=0.0.0.0
ENV TAILOR_PORT=8765

CMD ["python", "scripts/resume_server.py"]
