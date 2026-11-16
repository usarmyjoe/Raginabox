FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd -u 10001 -M app
COPY app/ /app/
USER 10001
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
