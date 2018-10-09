from unittest import TestCase
import pickle
import requests
from mailsender import EnvConfig, RETRY_WAIT_MS_DEFAULT, RETRY_COUNT_DEFAULT, BespinApi, \
    SendEmailMessage, EMAIL_EXCHANGE, ROUTING_KEY, MailSender
from unittest.mock import patch, Mock, call


class EnvConfigTests(TestCase):
    @patch('mailsender.os')
    def test_constructor_defaults(self, mock_os):
        mock_os.environ = {
            "BESPIN_API_TOKEN": "123",
            "BESPIN_API_URL": "http://someurl/api",
        }
        config = EnvConfig()
        self.assertEqual(config.work_queue_config.host, "127.0.0.1")
        self.assertEqual(config.work_queue_config.username, "guest")
        self.assertEqual(config.work_queue_config.password, "guest")
        self.assertEqual(config.email_retry_count, int(RETRY_COUNT_DEFAULT))
        self.assertEqual(config.retry_wait_ms, RETRY_WAIT_MS_DEFAULT)
        self.assertEqual(config.bespin_api_token, "123")
        self.assertEqual(config.bespin_api_url, "http://someurl/api")

    @patch('mailsender.os')
    def test_constructor_all_values(self, mock_os):
        mock_os.environ = {
            "MESSAGE_QUEUE_HOST":"somehost",
            "MESSAGE_QUEUE_USERNAME":"myuser",
            "MESSAGE_QUEUE_PASSWORD":"mypass",
            "BESPIN_API_TOKEN": "123",
            "BESPIN_API_URL": "http://someurl/api",
            "RETRY_COUNT": '100',
            "RETRY_WAIT_MS": '2000',
        }
        config = EnvConfig()
        self.assertEqual(config.work_queue_config.host, "somehost")
        self.assertEqual(config.work_queue_config.username, "myuser")
        self.assertEqual(config.work_queue_config.password, "mypass")
        self.assertEqual(config.bespin_api_token, "123")
        self.assertEqual(config.bespin_api_url, "http://someurl/api")
        self.assertEqual(config.email_retry_count, 100)
        self.assertEqual(config.retry_wait_ms, '2000')


class BespinApiTests(TestCase):
    def setUp(self):
        self.bespin_api = BespinApi(Mock(bespin_api_token='123', bespin_api_url='http://someurl/api'))

    def test_headers(self):
        headers = self.bespin_api.headers()
        self.assertEqual(headers['Authorization'], 'Token 123')
        self.assertEqual(headers['Content-type'], 'application/json')

    @patch('mailsender.requests')
    def test_email_message_send(self, mock_requests):
        self.bespin_api.email_message_send(475)
        expected_url = 'http://someurl/api/admin/email-messages/475/send/'
        mock_requests.post.assert_called_with(expected_url, headers=self.bespin_api.headers(), json={})


class SendEmailMessageTests(TestCase):
    def setUp(self):
        self.config = Mock(email_retry_count=12345)

    def test_constructor(self):
        send_email_message = SendEmailMessage(send_email_id=1, retry_count=2)
        self.assertEqual(send_email_message.send_email_id, 1)
        self.assertEqual(send_email_message.retry_count, 2)
        self.assertEqual(send_email_message.exchange, EMAIL_EXCHANGE)
        self.assertEqual(send_email_message.routing_key, ROUTING_KEY)

    def test_build_body(self):
        picked_body = SendEmailMessage(send_email_id=1, retry_count=2).build_body()
        body = pickle.loads(picked_body)
        self.assertEqual(body["send_email"], 1)
        self.assertEqual(body["retry_count"], 2)

    def test_try_create_from_body_with_bad_data(self):
        send_email_message = SendEmailMessage.try_create_from_body(pickle.dumps({}), self.config)
        self.assertEqual(None, send_email_message)
        send_email_message = SendEmailMessage.try_create_from_body(pickle.dumps("blah"), self.config)
        self.assertEqual(None, send_email_message)
        send_email_message = SendEmailMessage.try_create_from_body(pickle.dumps({"send": 2}), self.config)
        self.assertEqual(None, send_email_message)

    def test_try_create_from_body_with_good_data(self):
        data = {"send_email": '123'}
        send_email_message = SendEmailMessage.try_create_from_body(pickle.dumps(data), self.config)
        self.assertEqual(send_email_message.send_email_id, '123')
        self.assertEqual(send_email_message.retry_count, 12345)
        data = {"send_email": "123", "retry_count": 10}
        send_email_message = SendEmailMessage.try_create_from_body(pickle.dumps(data), self.config)
        self.assertEqual(send_email_message.send_email_id, '123')
        self.assertEqual(send_email_message.retry_count, 10)


class MailSenderTests(TestCase):
    @patch('mailsender.WorkQueueConnection')
    def test_constructor(self, mock_work_queue_connection):
        mail_sender = MailSender(config=Mock())
        mock_channel = mail_sender.channel
        # Declare and bind email and retry exchanges/queues
        mock_channel.exchange_declare.assert_has_calls([
            call('EmailExchange', 'direct'),
            call('RetryExchange', 'direct'),
        ])
        mock_channel.queue_declare.assert_has_calls([
            call(queue='EmailQueue'),
            call(queue='RetryQueue', arguments={'x-dead-letter-exchange': 'EmailExchange'},),
        ])
        mock_channel.queue_bind.assert_has_calls([
            call(exchange='EmailExchange', queue='EmailQueue', routing_key='SendEmail'),
            call(exchange='RetryExchange', queue='RetryQueue', routing_key='SendEmail')
        ])
        # call email_call when a message shows up in EmailQueue
        mock_channel.basic_consume.assert_called_with(
            mail_sender.email_callback,
            queue='EmailQueue',
            no_ack=True
        )

    @patch('mailsender.WorkQueueConnection')
    @patch('mailsender.BespinApi')
    def test_email_callback_works_first_time(self, mock_bespin_api, mock_work_queue_connection):
        mail_sender = MailSender(config=Mock())
        mail_sender.email_callback(None, None, None, pickle.dumps({
            'send_email': '5'
        }))
        mock_bespin_api.return_value.email_message_send.assert_called_with('5')

    @patch('mailsender.WorkQueueConnection')
    @patch('mailsender.BespinApi')
    def test_email_callback_with_one_retry(self, mock_bespin_api, mock_work_queue_connection):
        mock_bespin_api.return_value.email_message_send.side_effect = [
            requests.HTTPError()
        ]
        mail_sender = MailSender(config=Mock(email_retry_count=1, retry_wait_ms=2000))
        mail_sender.email_callback(None, None, None, pickle.dumps({
            'send_email': '5'
        }))
        mock_bespin_api.return_value.email_message_send.assert_has_calls([
            call('5')
        ])
        args, kwargs = mail_sender.channel.basic_publish.call_args
        sent_body = pickle.loads(kwargs['body'])
        self.assertEqual(sent_body['send_email'], '5')
        self.assertEqual(sent_body['retry_count'], 0)  # retry count should be decremented
        self.assertEqual(kwargs['properties'].expiration, 2000)
        self.assertEqual(kwargs['routing_key'], 'SendEmail')
