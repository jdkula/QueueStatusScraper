FROM python:3.10-alpine
WORKDIR /queuestatus-scraper
COPY main.py requirements.txt ./
COPY ./src ./src/
RUN pip3 install -r requirements.txt

CMD [ "python3", "main.py" ]