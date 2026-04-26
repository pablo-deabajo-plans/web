FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
COPY requirements.local.txt ./requirements.local.txt
COPY backend/requirements.txt ./backend/requirements.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.local.txt

COPY . .

EXPOSE 8000

CMD ["python", "-m", "backend.tools.local_runner", "api", "--host", "0.0.0.0", "--port", "8000"]
