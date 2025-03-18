FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install -e .

EXPOSE 8080

CMD ["uvicorn", "orchestrator.main:app", "--host", "0.0.0.0", "--port", "8080"]