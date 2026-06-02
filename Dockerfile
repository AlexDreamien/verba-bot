# Bot + result-collector backend. The Mini App (webapp/) is deployed
# separately to static hosting (GitHub Pages) and is not part of this image.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot
COPY main.py .

# aiohttp result-collector port (sits behind an HTTPS reverse proxy).
EXPOSE 8080

CMD ["python", "main.py"]
