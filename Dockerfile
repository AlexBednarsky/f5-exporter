FROM fnndsc/python-poetry
WORKDIR /srv/www
COPY . .
RUN poetry install 
CMD ["python", "app.py"]