# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Copy the current directory contents into the container at /usr/src/app
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY bot.py ./
COPY .env ./

CMD ["python", "-u", "bot.py"]
