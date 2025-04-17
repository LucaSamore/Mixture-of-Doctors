FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . .
 
RUN pip install -e .

EXPOSE 7000

CMD ["python", "-m", "src.synthesizer.main"]