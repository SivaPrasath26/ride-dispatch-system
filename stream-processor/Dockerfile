FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create __init__.py files for all packages
RUN touch consumers/__init__.py handlers/__init__.py state/__init__.py utils/__init__.py

CMD ["python", "main.py"]
