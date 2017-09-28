import sys
from lando_messaging.workqueue import WorkQueueConnection
from mailsender import EnvConfig, SendEmailMessage


def request_email_send(config, send_email_id):
    work_queue_connection = WorkQueueConnection(config)
    send_email_message = SendEmailMessage(send_email_id, retry_count=3)
    send_email_message.publish(work_queue_connection)
    print("Sent email request for id {}.".format(send_email_id))


if __name__ == '__main__':
    if len(sys.argv) == 2:
        send_email_id = sys.argv[1]
        request_email_send(EnvConfig(), send_email_id)
    else:
        print("Usage: python requestmailsend.py <send_email_id>")
