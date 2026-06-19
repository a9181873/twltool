FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt \
    && python -m playwright install --with-deps chromium \
    && groupadd --system monitor \
    && useradd --system --gid monitor --create-home --home-dir /home/monitor monitor

COPY taiwanlife_monitor ./taiwanlife_monitor
COPY config ./config
RUN mkdir -p /app/reports/results /app/reports/screenshots \
    && chown -R monitor:monitor /app/reports /home/monitor \
    && chmod -R a+rX /ms-playwright

VOLUME ["/app/reports"]

USER monitor

CMD ["python", "-m", "taiwanlife_monitor.monitor", "--config", "config/taiwanlife.json", "--output-dir", "reports", "--email-on-fail"]
