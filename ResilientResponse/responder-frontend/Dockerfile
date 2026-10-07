FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Port is dynamically assigned via main.py depending on RESPONDER_TYPE
CMD ["python", "main.py"]
