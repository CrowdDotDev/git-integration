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
import tqdm

from crowdgit import LOCAL_DIR
from crowdgit.get_remotes import get_remotes
from crowdgit.activity import prepare_crowd_activities
from crowdgit.repo import get_repo_name

from crowdgit.logger import get_logger

logger = get_logger(__name__)


SQS_MAX_MESSAGE_SIZE_IN_BYTES = 262144


def string_converter(o):
    """
    Function that converts object to string
    This will be used when converting to Json, to convert non serializable attributes
    """
    return str(o)


def baseline_message_size() -> int:
    """
    Calculate the size of baseline (with empty activityData) json object in bytes
    """
    body = json.dumps(
        {
            "type": "create_and_process_activity_result",
            "tenantId": os.environ["TENANT_ID"],
            "segmentId": os.environ["TENANT_ID"],
            "integrationId": os.environ["TENANT_ID"],
            "activityData": "",
        },
        default=string_converter,
    )

    return len(body.encode("utf-8")) + 2


def truncate_to_bytes(s: str, max_bytes: int, encoding="utf-8"):
    """
    Truncate the string `s` so that its byte size is strictly less than `max_bytes`.

    Parameters:
    s (str): The string to truncate.
    max_bytes (int): The maximum allowed size in bytes.
    encoding (str): The encoding to use for the byte representation.

    Returns:
    str: The truncated string.
    """
    encoded_string = s.encode(encoding)

    if len(encoded_string) < max_bytes:
        return s

    truncated_string = s
    while len(truncated_string.encode(encoding)) >= max_bytes:
        truncated_string = truncated_string[:-1]

    return truncated_string


class SQS:
    """
    Class to handle SQS requests. Can send and receive messages.
    """

    def __init__(self):
        """
        Initialise class to handle SQS requests.
        """
        self.sqs_url = os.environ["SQS_ENDPOINT_URL"]

        self.sqs = boto3.client(
            "sqs",
            endpoint_url=os.environ["SQS_ENDPOINT_URL"],
            region_name=os.environ["SQS_REGION"],
            aws_secret_access_key=os.environ["SQS_SECRET_ACCESS_KEY"],
            aws_access_key_id=os.environ["SQS_ACCESS_KEY_ID"],
        )

    def send_messages(
        self,
        segment_id: str,
        integration_id: str,
        records: List[Dict],
        verbose: bool = False,
    ) -> List[Dict]:
        """
        Send a message to the queue

        Args:
            records (List[Dict]): messages to be sent to the queue

        Returns:
            list: List of SQS message responses
        """

        operation = "upsert_activities_with_members"

        def get_body_json(record):
            body = json.dumps(
                {
                    "type": "create_and_process_activity_result",
                    "tenantId": os.environ["TENANT_ID"],
                    "segmentId": segment_id,
                    "integrationId": integration_id,
                    "activityData": record,
                },
                default=string_converter,
            )

            if len(body.encode("utf-8")) > SQS_MAX_MESSAGE_SIZE_IN_BYTES:
                logger.warning(
                    "The activity body is too big (%d bytes). Truncating the body.",
                    len(body.encode("utf-8")),
                )
                record["body"] = truncate_to_bytes(
                    record["body"], SQS_MAX_MESSAGE_SIZE_IN_BYTES - baseline_message_size()
                )
                body = json.dumps(
                    {
                        "type": "create_and_process_activity_result",
                        "tenantId": os.environ["TENANT_ID"],
                        "segmentId": segment_id,
                        "integrationId": integration_id,
                        "activityData": record,
                    },
                    default=string_converter,
                )

                logger.info("Truncated body size: %d bytes", len(body.encode("utf-8")))

            return body

        platform = "git"
        responses = []

        if verbose:
            commits_iter = tqdm.tqdm(records, desc="Processing records")
        else:
            commits_iter = records

        for record in commits_iter:
            deduplication_id = str(uuid())
            message_id = f"{os.environ['TENANT_ID']}-{operation}-{platform}-{deduplication_id}"

            body = get_body_json(record)

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

            status_code = response["ResponseMetadata"]["HTTPStatusCode"]
            if status_code == 200:
                responses.append(response)
            else:
                logger.error("Received a %d status code from SQS with %s", status_code, body)

        return responses

    def ingest_remote(
        self, segment_id: str, integration_id: str, remote: str, verbose: bool = False
    ):
        repo_name = get_repo_name(remote)
        semaphore = os.path.join(LOCAL_DIR, "running", repo_name)
        if not os.path.exists(os.path.dirname(semaphore)):
            os.makedirs(os.path.dirname(semaphore))

        if os.path.exists(semaphore):
            with open(semaphore, "r", encoding="utf-8") as fin:
                timestamp = fin.read().strip()
            logger.info("Skipping %s, already running since %s", repo_name, timestamp)
            return

        with open(semaphore, "w", encoding="utf-8") as fout:
            logger.info("Setting semaphore in %s", semaphore)
            fout.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        try:
            activities = prepare_crowd_activities(remote, verbose=verbose)

        except Exception as e:
            logger.error("Failed trying to prepare activities for %s. Error:\n%s", remote, str(e))
            if os.path.exists(semaphore):
                os.remove(semaphore)
            return

        try:
            # print("Skipping messages")
            self.send_messages(segment_id, integration_id, activities, verbose=verbose)
        except Exception as e:
            logger.error("Failed trying to send messages for %s", remote, str(e))
        finally:
            if os.path.exists(semaphore):
                os.remove(semaphore)

    @staticmethod
    def make_id() -> str:
        return str(uuid())


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Ingest remote.")
    parser.add_argument(
        "--remote",
        type=str,
        default="",
        help="Remote url. Will only ingest a remote comming from the tenant that matches it.",
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose output.")
    args = parser.parse_args()

    sqs = SQS()

    remotes = get_remotes(
        os.environ["CROWD_HOST"],
        os.environ["TENANT_ID"],
        os.environ["CROWD_API_KEY"],
    )

    for i, segment_id in enumerate(remotes):
        integration_id = remotes[segment_id]["integrationId"]
        for j, remote in enumerate(remotes[segment_id]["remotes"]):
            if args.verbose:
                print(
                    f"\n\n{i + 1} / {len(remotes)} segments.\n{j + 1} / {len(remotes[segment_id]['remotes'])} repos."
                )
            if not args.remote or (args.remote.rstrip(".git") == remote.rstrip(".git")):
                logger.info(f"Ingesting {remote} for segment {segment_id}")
                sqs.ingest_remote(segment_id, integration_id, remote, verbose=args.verbose)


if __name__ == "__main__":
    main()
