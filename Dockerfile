FROM python:slim-bullseye

RUN apt update && \
    apt upgrade -y && \
    apt install -y curl && \
    apt clean 

RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=/usr/local python3 - 

WORKDIR /srv/www

COPY . .

RUN poetry config virtualenvs.create false && poetry install 

CMD ["python", "app.py"]
