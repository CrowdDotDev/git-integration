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

    def __init__(self, local_dir=None):
        """
        Initialise class to handle SQS requests.

        Args:
            local_dir (str): local directory in which repos are stored.  Defaults to
            ENV['REPO_DIR']
        """
        self.local_dir = local_dir or os.environ['REPO_DIR']
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

        def create_chunks(lst):
            MAX_PAYLOAD_SIZE = 255 * 1024  # 255 KiB in bytes
            chunk = []
            chunk_size = 0

            for record in lst:
                record_size = len(json.dumps(record, default=string_converter).encode('utf-8'))

                if chunk_size + record_size > MAX_PAYLOAD_SIZE:
                    yield chunk
                    chunk = [record]
                    chunk_size = record_size
                else:
                    chunk.append(record)
                    chunk_size += record_size

            if chunk:
                yield chunk

        operation = "upsert_activities_with_members"
        platform = "git"

        responses = []

        for chunk in create_chunks(records):
            deduplication_id = str(uuid())
            message_id = f"{os.environ['TENANT_ID']}-{operation}-{platform}-{deduplication_id}"

            body = json.dumps({'tenant_id': os.environ['TENANT_ID'],
                               'operation': operation,
                               'records': chunk}, default=string_converter)

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
        self.send_messages(prepare_crowd_activities(remote, local_dir=self.local_dir))

    @staticmethod
    def make_id():
        return str(uuid())


def main():
    import sys
    remote = sys.argv[1]
    SQS().ingress_remote(remote)


if __name__ == '__main__':
    main()
