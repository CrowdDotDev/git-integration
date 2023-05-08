import boto3
import os
from uuid import uuid1 as uuid
import json
from crowd.backend.infrastructure.logging import get_logger

logger = get_logger(__name__)


def string_converter(o):
    """
    Function that converts object to string
    This will be used when converting to Json, to convert non serializable attributes
    """
    return o.__str__()

# TODO: Change caps variables to get from environment

class SQS:
    """
    Class to handle SQS requests. Can send and recieve messages.
    """

    def __init__(self):
        """
        Initialise class to handle SQS requests.

        Args:
            sqs_url (str): SQS url.
        """
        self.sqs_url = SQS_ENDPOINT_URL

        self.sqs = boto3.client("sqs",
                                endpoint_url=SQS_ENDPOINT_URL,
                                region_name=SQS_REGION,
                                aws_secret_access_key=SQS_SECRET_ACCESS_KEY,
                                aws_access_key_id=SQS_ACCESS_KEY_ID)

    def send_message(self, records):
        """
        Sent a message to the queue

        Args:
            records (dict): message to be sent to the queue

        Returns:
            [type]: [description]
        """

        operation = "upsert_activities_with_members"
        platform = "git"
        deduplication_id = str(uuid())
        message_id = f"{TENANT_ID}-{operation}-{platform}-{deduplication_id}"

        # TODO: Check max size and iterate this
        body = dict(tenant_id=TENANT_ID, operation=operation, records=records)
        body = json.dumps(body, default=string_converter)


        return self.sqs.send_message(
            QueueUrl=self.sqs_url,
            MessageAttributes={},
            MessageBody=body,
            MessageGroupId=message_id,
            MessageDeduplicationId=deduplication_id,
        )

    @staticmethod
    def make_id():
        return str(uuid())
