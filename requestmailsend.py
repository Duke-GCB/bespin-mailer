# Minimal example client for mailsender that only requires lando_messaging
import sys
import pickle
from lando_messaging.workqueue import WorkQueueConnection, WorkQueueConfig

EMAIL_EXCHANGE = "EmailExchange"
ROUTING_KEY = "SendEmail"


class Config(object):
    """
    Example configuration that expects on localhost and
    """
    def __init__(self, host, username, password):
        self.work_queue_config = WorkQueueConfig(host, username, password)


def request_email_send(config, send_email_id):
    work_queue_connection = WorkQueueConnection(config)
    body = pickle.dumps({"send_email": send_email_id })
    work_queue_connection.connect()
    channel = work_queue_connection.connection.channel()
    channel.basic_publish(exchange=EMAIL_EXCHANGE,
                          routing_key=ROUTING_KEY,
                          body=body)
    work_queue_connection.close()
    print(("Sent email request for id {}.".format(send_email_id)))


def main():
    config = Config(
        host=sys.argv[1],
        username=sys.argv[2],
        password=sys.argv[3]
    )
    request_email_send(config, sys.argv[4])


def usage():
    print("Usage: python requestmailsend.py <host> <username> <password> <send_email_id>")


if __name__ == '__main__':
    if len(sys.argv) == 5:
        main()
    else:
        usage()
