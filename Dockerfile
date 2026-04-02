FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
# gcc/default-libmysqlclient-dev required for building some python packages if no binaries are available
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire app folder into /app/app
# We run as python -m app.main
COPY app/ ./app/

ENV PYTHONPATH="/"

CMD ["python", "-m", "app.main"]
