# -*- coding: utf-8 -*-
"""ingest endpoint.

If called from the command line it expects one argument, the address of a remote.
It will prepare the activites (which will include either cloning it to ENV[REPO_DIR]
if it has not been cloned yet) and send them to SQS.
"""
import os
import json
from datetime import datetime
from typing import List, Dict

from uuid import uuid1 as uuid
import boto3

import dotenv

from crowdgit.get_remotes import get_remotes
from crowdgit.activity import prepare_crowd_activities
from crowdgit.logger import get_logger
from crowdgit.repo import REPO_DIR, get_repo_name

dotenv.load_dotenv(".env")

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

    def send_messages(self, records: List[Dict]) -> List[Dict]:
        """
        Send a message to the queue

        Args:
            records (List[Dict]): messages to be sent to the queue

        Returns:
            list: List of SQS message responses
        """

        operation = "upsert_activities_with_members"

        def get_body_json(chunk):
            return json.dumps({'tenant_id': os.environ['TENANT_ID'],
                               'operation': operation,
                               'type': 'db_operations',
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

            # A response should be something like this:
            #
            # {'MD5OfMessageBody': '31d3385e45172c0b830b83b4cb8cd6e9',
            #  'MessageId': '6506bf53-60aa-4f4b-bd88-c9065170d030',
            #  'ResponseMetadata': {'HTTPHeaders': {'content-length': '431',
            #                                       'content-type': 'text/xml',
            #                                       'date': 'Wed, 10 May 2023 17:07:41 GMT',
            #                                       'x-amzn-requestid':
            #                                          'fbee9fd0-8041-5289-8ba3-c30551dc5ad3'},
            #                       'HTTPStatusCode': 200,
            #                       'RequestId': 'fbee9fd0-8041-5289-8ba3-c30551dc5ad3',
            #                       'RetryAttempts': 0},
            #  'SequenceNumber': '18877781119960559616'}
            status_code = response['ResponseMetadata']['HTTPStatusCode']
            if status_code != 200:
                logger.error('Received a %d status code from SQS with %s',
                             status_code, body)
                return responses

            responses.append(response)

        return responses

    def ingest_remote(self, remote: str):
        repo_name = get_repo_name(remote)
        semaphore = os.path.join(REPO_DIR, 'running', repo_name)
        if not os.path.exists(os.path.dirname(semaphore)):
            os.makedirs(os.path.dirname(semaphore))

        if os.path.exists(semaphore):
            with open(semaphore, 'r', encoding='utf-8') as fin:
                timestamp = fin.read().strip()
            logger.info('Skipping %s, already running since %s', repo_name, timestamp)
            return

        with open(semaphore, 'w', encoding='utf-8') as fout:
            logger.info('Setting semaphore in %s', semaphore)
            fout.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


        try:
            activities = prepare_crowd_activities(remote)
        except:
            logger.error('Failed trying to prepare activities for %s', remote)
            os.remove(semaphore)
            return

        try:
            self.send_messages(activities)
        except:
            logger.error('Failed trying to send messages for %s', remote)
        finally:
            if os.path.exists(semaphore):
                os.remove(semaphore)

    @staticmethod
    def make_id() -> str:
        return str(uuid())


def main():
    import sys

    sqs = SQS()

    if len(sys.argv) == 2:
        remote = sys.argv[1]
        logger.info('Ingesting %s', remote)
        sqs.ingest_remote(remote)
    else:
        remotes = get_remotes(os.environ['CROWD_HOST'],
                              os.environ['TENANT_ID'],
                              os.environ['CROWD_API_KEY'])

        for remotes in remotes.values():
            for remote in remotes:
                logger.info('Ingesting %s', remote)
                sqs.ingest_remote(remote)


if __name__ == '__main__':
    main()