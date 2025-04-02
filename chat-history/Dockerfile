# Use the official Python image from the Docker Hub
FROM python:3.13-slim
# Set the working directory in the container
WORKDIR /app
# Copy the requirements file into the container
COPY requirements.txt .
# Install dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
# Copy the rest of the application code into the container
COPY . .
 
# Install the application as a package in development mode
RUN pip install -e .
# Expose the port the app runs on
EXPOSE 8000
# Command to run the application
CMD ["uvicorn", "src.chat_history.main:app", "--host", "0.0.0.0", "--port", "8000"]