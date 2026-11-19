FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    HOME=/home/appuser

WORKDIR /srv

COPY requirements.txt .

RUN python -m pip install --no-cache-dir --upgrade pip
RUN python -m pip install --no-cache-dir --index-url https://pypi.org/simple -r requirements.txt

COPY . .

RUN python process_data.py

RUN useradd -m appuser && chown -R appuser /srv /home/appuser

USER appuser

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/')" || exit 1

CMD ["sh", "-c", "streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port ${PORT} --server.headless true"]