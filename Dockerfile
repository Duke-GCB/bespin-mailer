FROM python:3.6
LABEL maintainer="dan.leehr@duke.edu"

ADD . /bespin-mailer
WORKDIR /bespin-mailer
RUN pip install -r requirements.txt
CMD python mailsender.py
