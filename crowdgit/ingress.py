# -*- coding: utf-8 -*-
"""ingress endpoint.

If called from the command line it expects one argument, the address of a remote.
It will prepare the activites (which will include either cloning it to ENV[REPO_DIR]
if it has not been cloned yet) and send them to SQS.
"""
import os
import json
from uuid import uuid1 as uuid
import boto3

from crowdgit.activity import prepare_crowd_activities
from crowdgit.logger import get_logger

logger = get_logger(__name__)


def string_converter(o):
    """
    Function that converts object to string
    This will be used when converting to Json, to convert non serializable attributes
    """
    return str(o)


class SQS:
    """
    Class to handle SQS requests. Can send and receive messages.
    """

    def __init__(self):
        """
        Initialise class to handle SQS requests.
        """
        self.sqs_url = os.environ['SQS_ENDPOINT_URL']

        self.sqs = boto3.client("sqs",
                                endpoint_url=os.environ['SQS_ENDPOINT_URL'],
                                region_name=os.environ['SQS_REGION'],
                                aws_secret_access_key=os.environ['SQS_SECRET_ACCESS_KEY'],
                                aws_access_key_id=os.environ['SQS_ACCESS_KEY_ID'])

    def send_messages(self, records):
        """
        Send a message to the queue

        Args:
            records (dict): message to be sent to the queue

        Returns:
            list: List of SQS send message responses
        """

        operation = "upsert_activities_with_members"

        def get_body_json(chunk):
            return json.dumps({'tenant_id': os.environ['TENANT_ID'],
                               'operation': operation,
                               'records': chunk}, default=string_converter)

        def get_body_size(chunk):
            return len(get_body_json(chunk).encode('utf-8'))

        def create_chunks(lst):
            MAX_PAYLOAD_SIZE = 255 * 1024  # 256 KiB in bytes, -1 KiB for margin
            chunk = []

            for record in lst:
                if get_body_size(chunk + [record]) >= MAX_PAYLOAD_SIZE:
                    yield chunk
                    chunk = [record]
                else:
                    chunk.append(record)

            if chunk:
                yield chunk

        platform = "git"

        responses = []

        for chunk in create_chunks(records):
            deduplication_id = str(uuid())
            message_id = f"{os.environ['TENANT_ID']}-{operation}-{platform}-{deduplication_id}"

            body = get_body_json(chunk)

            response = self.sqs.send_message(
                QueueUrl=self.sqs_url,
                MessageAttributes={},
                MessageBody=body,
                MessageGroupId=message_id,
                MessageDeduplicationId=deduplication_id,
            )
            responses.append(response)

        return responses

    def ingress_remote(self, remote):
        self.send_messages(prepare_crowd_activities(remote))

    @staticmethod
    def make_id():
        return str(uuid())


def main():
    import sys
    remote = sys.argv[1]
    SQS().ingress_remote(remote)


if __name__ == '__main__':
    main()
