# Lightweight Python 3.11 Base Image
FROM python:3.11-slim

# Set Working Directory
WORKDIR /app

# Copy Source Files
COPY . /app

# Expose Port 8000
EXPOSE 8000

# Run Server (Zero External Dependencies Required!)
CMD ["python3", "main.py"]
