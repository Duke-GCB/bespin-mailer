# bespin-mailer ![Build Status](https://circleci.com/gh/Duke-GCB/bespin-mailer.svg?style=shield&circle-token=:circle-token)
Bespin mail delivery service. Monitors a message queue for a particular `send_email` message and posts a message to the appropriate [bespin-api](https://github.com/Duke-GCB/bespin-api) REST endpoint. If the POST fails it will retry after waiting some time.

### Requirements
- python/pip - python 2 or 3

### External requirements
- Rabbitmq - a queue were messages are placed for lando and lando_worker to consume.
- bespin-api - a REST API that `mailsender.py` will ask to send email

### Installing
```
pip install -r requirements.txt
```

### Setup
Fill in environment variables in `setup.sh` replacing __TODO__ with actual values.

### Run
```
source setup.sh
python mailsender.py
```
