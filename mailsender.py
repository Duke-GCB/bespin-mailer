#!/usr/bin/env python
import pika
from lando_messaging.workqueue import Config, WorkQueueConnection

EMAIL_EXCHANGE = "EmailExchange"
EMAIL_QUEUE = "EmailQueue"
RETRY_EXCHANGE = "RetryExchange"
RETRY_QUEUE = "RetryQueue"


class MailSender(object):
    def __init__(self, config):
        work_queue_connection = WorkQueueConnection(config)
        self.channel = work_queue_connection.connection.channel()

    def _declare_email_exchange_and_queue(self):


connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()


channel.exchange_declare(WORK_EXCHANGE, "direct")
channel.queue_declare(queue=WORK_QUEUE)
channel.queue_bind(queue=WORK_QUEUE, exchange=WORK_EXCHANGE, routing_key='')

channel.exchange_declare(RETRY_EXCHANGE, "direct")
redirect_args = {
    "x-dead-letter-exchange": WORK_EXCHANGE,
    "x-message-ttl": 10000 # in ms
}
channel.queue_declare(queue=RETRY_QUEUE, arguments=redirect_args)
channel.queue_bind(queue=RETRY_QUEUE, exchange=RETRY_EXCHANGE, routing_key='')


def callback(ch, method, properties, body):
    print(" [x] Got Message %r" % body)
    resp = channel.basic_publish(exchange=RETRY_EXCHANGE, routing_key='', body=body)


channel.basic_consume(callback,
                      queue=WORK_QUEUE,
                      no_ack=True)

print(' [*] Waiting for messages. To exit press CTRL+C')
channel.start_consuming()


config = Config('localhost', 'jpb', 'jpb')
mail_sender = MailSender(config)
