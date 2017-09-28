import pika
from lando_messaging.workqueue import

EMAIL_EXCHANGE = "EmailExchange"


class EmailClient(object):
    def __init__(self, config, exchange_name=EMAIL_EXCHANGE):
        self.exchange_name = exchange_name
        self.host = config.host
        self.username = config.username
        self.password = config.password

    def send(self, send_email_id):

        connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        channel = connection.channel()

        channel.basic_publish(exchange=EMAIL_EXCHANGE,
                              routing_key='',
                              body='Hello World!')
        print(" [x] Sent 'Hello World!'")
        connection.close()
