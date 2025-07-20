FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . .
 
RUN pip install -e .

EXPOSE 8000

CMD ["uvicorn", "src.chat_history.main:app", "--host", "0.0.0.0", "--port", "8000"]