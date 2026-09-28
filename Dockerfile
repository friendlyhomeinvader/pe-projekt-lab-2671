FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install -r requirements.txt

COPY ./app /app

EXPOSE 5000

CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
