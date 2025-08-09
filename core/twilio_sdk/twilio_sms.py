from django.conf import settings
from twilio.rest import Client
from error_handling.error_list import CUSTOM_ERROR_LIST


def load_twilio_config():
    twilio_account_sid = settings.TWILIO_ACCOUNT_SID
    twilio_auth_token = settings.TWILIO_AUTH_TOKEN
    twilio_number = settings.TWILIO_PHONE_NUMBER

    return twilio_number, twilio_account_sid, twilio_auth_token


class MessageClient:
    def __init__(self):
        (
            twilio_number,
            twilio_account_sid,
            twilio_auth_token,
        ) = load_twilio_config()

        self.twilio_number = twilio_number
        self.twilio_client = Client(twilio_account_sid, twilio_auth_token)

    def send_message(self, body, to):
        validate_number = self.twilio_client.lookups.v2.phone_numbers(to).fetch()
        if hasattr(validate_number, 'valid') and not validate_number.valid:
            raise CUSTOM_ERROR_LIST.CUSTOM_VALIDATION_ERROR_4008("Invalid number detected! Failed to send sms!")

        return self.twilio_client.messages.create(
            body=body,
            to=to,
            from_=self.twilio_number,
        )
