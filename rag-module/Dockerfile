FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code to the container
COPY . .

#EXPOSE 8000
ENV PORT=8080

# Default command to start the service
CMD ["python", "-m", "src.rag_module.rag_module"]