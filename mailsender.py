import os
import pika
import requests
import pickle
from lando_messaging.workqueue import WorkQueueConfig, WorkQueueConnection

# Environment variable names
MESSAGE_QUEUE_HOST = "MESSAGE_QUEUE_HOST"
MESSAGE_QUEUE_USERNAME = "MESSAGE_QUEUE_USERNAME"
MESSAGE_QUEUE_PASSWORD = "MESSAGE_QUEUE_PASSWORD"
BESPIN_API_TOKEN = "BESPIN_API_TOKEN"
BESPIN_API_URL = "BESPIN_API_URL"
RETRY_COUNT = "RETRY_COUNT"
RETRY_WAIT_MS = "RETRY_WAIT_MS"

# Global settings
EMAIL_EXCHANGE = "EmailExchange"
EMAIL_QUEUE = "EmailQueue"
ROUTING_KEY = "SendEmail"
RETRY_EXCHANGE = "RetryExchange"
RETRY_QUEUE = "RetryQueue"
RETRY_WAIT_MS_DEFAULT = '10000'  # 10 seconds
RETRY_COUNT_DEFAULT = '10'


class EnvConfig(object):
    """
    Environment variable based configuration.
    """
    def __init__(self):
        host = os.environ.get(MESSAGE_QUEUE_HOST, "127.0.0.1")
        username = os.environ.get(MESSAGE_QUEUE_USERNAME, "guest")
        password = os.environ.get(MESSAGE_QUEUE_PASSWORD, "guest")
        self.email_retry_count = int(os.environ.get(RETRY_COUNT, RETRY_COUNT_DEFAULT))
        self.retry_wait_ms = os.environ.get(RETRY_WAIT_MS, RETRY_WAIT_MS_DEFAULT)
        self.bespin_api_token = os.environ[BESPIN_API_TOKEN]
        self.bespin_api_url = os.environ[BESPIN_API_URL]
        self.work_queue_config = WorkQueueConfig(host, username, password)


class BespinApi(object):
    def __init__(self, config):
        self.token = config.bespin_api_token
        self.url = config.bespin_api_url

    def headers(self):
        """
        Create HTTP header containing auth info.
        :return: dict: request headers
        """
        return {
            'Authorization': 'Token {}'.format(self.token),
            'Content-type': 'application/json'
        }

    def _make_url(self, suffix):
        return '{}/admin/{}'.format(self.url, suffix)

    def email_message_send(self, send_email_id):
        path = 'email-messages/{}/send/'.format(send_email_id)
        url = self._make_url(path)
        resp = requests.post(url, headers=self.headers(), json={})
        resp.raise_for_status()
        return resp.json()


class SendEmailMessage(object):
    def __init__(self, send_email_id, retry_count):
        self.send_email_id = send_email_id
        self.retry_count = retry_count
        self.exchange = EMAIL_EXCHANGE
        self.routing_key = ROUTING_KEY

    def build_body(self):
        return pickle.dumps(
            {
                "send_email": self.send_email_id,
                "retry_count": self.retry_count
            }
        )

    @staticmethod
    def try_create_from_body(body, config):
        email_message_dict = pickle.loads(body)
        if isinstance(email_message_dict, dict):
            send_email_id = email_message_dict.get("send_email")
            retry_count = email_message_dict.get("retry_count", config.email_retry_count)
            if send_email_id:
                return SendEmailMessage(send_email_id, retry_count)
        return None

    def publish(self, work_queue_connection):
        work_queue_connection.connect()
        channel = work_queue_connection.connection.channel()
        channel.basic_publish(exchange=EMAIL_EXCHANGE,
                              routing_key=ROUTING_KEY,
                              body=self.build_body())
        work_queue_connection.close()


class MailSender(object):
    def __init__(self, config, routing_key=ROUTING_KEY):
        work_queue_connection = WorkQueueConnection(config)
        work_queue_connection.connect()
        self.config = config
        self.channel = work_queue_connection.connection.channel()
        self.routing_key = routing_key
        self._declare_email_exchange_and_queue()
        self._declare_retry_exchange_and_queue()
        self._setup_callback()
        self.bespin_api = BespinApi(config)

    def start_consuming(self):
        print("Listening for email messages...")
        self.channel.start_consuming()

    def _declare_email_exchange_and_queue(self):
        self.channel.exchange_declare(EMAIL_EXCHANGE, "direct")
        self.channel.queue_declare(queue=EMAIL_QUEUE)
        self.channel.queue_bind(queue=EMAIL_QUEUE, exchange=EMAIL_EXCHANGE, routing_key=self.routing_key)

    def _declare_retry_exchange_and_queue(self):
        self.channel.exchange_declare(RETRY_EXCHANGE, "direct")
        redirect_args = {
            "x-dead-letter-exchange": EMAIL_EXCHANGE,
        }
        self.channel.queue_declare(queue=RETRY_QUEUE, arguments=redirect_args)
        self.channel.queue_bind(queue=RETRY_QUEUE, exchange=RETRY_EXCHANGE, routing_key=self.routing_key)

    def _setup_callback(self):
        self.channel.basic_consume(self.email_callback,
                              queue=EMAIL_QUEUE,
                              no_ack=True)

    def email_callback(self, ch, method, properties, body):
        send_email_message = SendEmailMessage.try_create_from_body(body, self.config)
        if send_email_message:
            email_send_id = send_email_message.send_email_id
            try:
                print("Sending email {} to bespin.".format(email_send_id))
                self.bespin_api.email_message_send(email_send_id)
                print("Done sending email {} to bespin.".format(email_send_id))
            except requests.HTTPError as err:
                print("Bespin API sending email {} failed with {}".format(email_send_id, err))
                self.send_email_retry(send_email_message)
        else:
            print(" [x] Received invalid SendEmail request {}".format(pickle.loads(body)))

    def send_email_retry(self, send_email_message):
        send_email_id = send_email_message.send_email_id
        if send_email_message.retry_count:
            send_email_message.retry_count -= 1
            print("Retrying SendEmail {} in {} ms (retries remaining: {}).".format(
                send_email_id, self.config.retry_wait_ms, send_email_message.retry_count))
            self.retry_message(send_email_message.build_body())
        else:
            print("Giving up on SendEmail {} - out of retries.".format(send_email_id))

    def retry_message(self, body):
        basic_properties = pika.BasicProperties(expiration=self.config.retry_wait_ms)
        self.channel.basic_publish(exchange=RETRY_EXCHANGE,
                                   routing_key=self.routing_key,
                                   body=body,
                                   properties=basic_properties)


def main():
    config = EnvConfig()
    mail_sender = MailSender(config)
    mail_sender.start_consuming()

if __name__ == '__main__':
    main()
