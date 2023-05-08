# -*- coding: utf-8 -*-
"""get_remotes endpoint.

Defines the get_remotes function, which return a dictionary of remotes of the form:

{
  "kubernetes": [
    "remote_0_0",
    "remote_0_1",
    "remote_0_2"
  ],
  "linux": [
    "remote_1_0",
    "remote_1_1",
    "remote_1_2",
    "remote_1_3"
  ]
}

If called in the command line with the --ingress flag it will go
through all of them and ingress them.
"""
import os
import requests

from crowdgit.ingress import SQS
from crowdgit.logger import get_logger

logger = get_logger(__name__)


def get_remotes():
    url = f"https://{os.environ['CROWD_HOST']}/api/tenant/{os.environ['TENANT_ID']}/git"

    payload = {}
    crowd_api_key = os.environ['CROWD_API_KEY']
    headers = {
      'Authorization': f'Bearer {crowd_api_key}'
    }

    response = requests.request("GET", url, headers=headers, data=payload, timeout=10)

    if response.status_code == 200:
        return response.json()

    logger.error("Request to get remotes failed with status code %s", response.status_code)
    return {}


def ingress_remotes():
    remotes_dict = get_remotes()
    sqs = SQS()

    for remotes in remotes_dict.values():
        for remote in remotes:
            sqs.ingress_remote(remote)


def main():
    import argparse
    from pprint import pprint

    parser = argparse.ArgumentParser(description='Process remotes from a GitHub repository')

    # Add the flag for calling ingress_remotes
    parser.add_argument('--ingress', action='store_true', help='Ingress remotes into the system')

    args = parser.parse_args()

    if args.ingress:
        ingress_remotes()
    else:
        pprint(get_remotes())


if __name__ == '__main__':
    main()
