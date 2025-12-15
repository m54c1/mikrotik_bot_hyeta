FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

RUN useradd -m -u 1000 bot && chown -R bot:bot /app
USER bot
ENV HOME=/home/bot

CMD ["python", "bot.py"]

