FROM python:slim-bullseye

WORKDIR /srv/www

RUN apt update && \
    apt upgrade -y && \
    apt install -y curl gcc libffi-dev && \
    apt clean 

RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=/usr/local python3 - 

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false && poetry install 

COPY . .

CMD ["python", "app.py"]
