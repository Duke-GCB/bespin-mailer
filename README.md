# bespin-mailer 
Bespin mail delivery service ![Build Status](https://circleci.com/gh/Duke-GCB/bespin-mailer.svg?style=shield&circle-token=:circle-token)

### Requirements
- python/pip - python 2 or 3

### External requirements
- Rabbitmq - a queue were messages are placed for lando and lando_worker to consume.
- bespin-api - a REST API that `mailsender.py` will ask to send email

### Installing
```
pip install -r requirements
```

### Setup
Export environment variables as outlined in TODO's in `setup.sh`.


### Run
```
python mailsender.py
```
