FROM python:3.12-slim
WORKDIR /app
COPY bot_service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY bot_service ./bot_service
RUN useradd --create-home bot && mkdir /data && chown bot:bot /data
USER bot
CMD ["python", "-m", "bot_service.main"]
