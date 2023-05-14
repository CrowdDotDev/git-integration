# -*- coding: utf-8 -*-

import re
import hashlib
import time
from typing import List, Dict

import tqdm
from fuzzywuzzy import process

from crowdgit.repo import get_repo_name, get_new_commits
from crowdgit.activitymap import ActivityMap

from crowdgit.logger import get_logger
logger = get_logger(__name__)


def match_activity_name(activity_name: str) -> str:
    best_match = process.extractOne(activity_name, ActivityMap.keys(), score_cutoff=80)
    return best_match[0] if best_match else None


def extract_activities_fuzzy(commit_message: List[str]) -> List[Dict[str, Dict[str, str]]]:
    activities = []
    activity_pattern = re.compile(r'([^:]*):\s*(.*)\s*<(.*)>')

    for line in commit_message:
        match = activity_pattern.match(line)
        if match:
            activity_name, name, email = match.groups()
            matched_key = match_activity_name(activity_name.lower())
            if matched_key:
                for activity in ActivityMap[matched_key]:
                    activities.append({
                        activity: {
                            'name': name.strip(),
                            'email': email.strip()
                        }
                    })
    return activities


# :prompt:extract-activities
def extract_activities(commit_message: List[str]) -> List[Dict[str, Dict[str, str]]]:
    """
    Extract activities from the commit message and return a list of activities.
    Each activity in the list includes the activity and the person who made it,
    which in turn includes the name and the email.

    :param commit_message: A list of strings, where each string is a line of the commit message.
    :return: A list of dictionaries containing activities and the person who made them.

    >>> extract_activities([
    ...     "Signed-off-by: Arnd Bergmann <arnd@arndb.de>",
    ...     "reported-by: Guenter Roeck <linux@roeck-us.net>"
    ... ]) == [{'Co-authored-by': {'email': 'arnd@arndb.de', 'name': 'Arnd Bergmann'}},
    ...        {'Signed-off-by': {'email': 'arnd@arndb.de', 'name': 'Arnd Bergmann'}},
    ...        {'Reported-by': {'email': 'linux@roeck-us.net', 'name': 'Guenter Roeck'}}]
    True
    """
    activities = []
    activity_pattern = re.compile(r"([^:]*):\s*(.*)\s*<(.*)>")

    for line in commit_message:
        match = activity_pattern.match(line)
        if match:
            activity_name, name, email = match.groups()
            activity_name = activity_name.lower()
            if activity_name in ActivityMap:
                for activity in ActivityMap[activity_name]:
                    activities.append({
                        activity: {
                            "name": name.strip(),
                            "email": email.strip()
                        }
                    })
    return activities
# :/prompt:extract-activities


def prepare_crowd_activities(remote: str,
                             commits: List[Dict] = None,
                             verbose: bool = False) -> List[Dict]:

    def create_activity(commit: Dict,
                        activity_type: str,
                        member: Dict,
                        source_id: str,
                        source_parent_id: str = '') -> Dict:
        return {
            'type': activity_type,
            'timestamp': commit['datetime'],
            'sourceId': source_id,
            'sourceParentId': source_parent_id,
            'platform': 'git',
            'channel': get_repo_name(remote),
            'body': '\n'.join(commit['message']),
            'attributes': {
                'insertions': commit['insertions'],
                'deletions': commit['deletions'],
                'lines': commit['insertions'] - commit['deletions'],
                'isMerge': commit['is_merge_commit'],
                'isMainBranch': commit['is_main_branch']
                # 'branches': commit['branches']
            },
            'url': remote,
            'member': member
        }

    activities = []

    if commits is None:
        commits = get_new_commits(remote)

    if verbose:
        commits_iter = tqdm.tqdm(commits, desc="Processing commits")
    else:
        commits_iter = commits

    for commit in commits_iter:
        author = {
            'username': commit['author_name'],
            'displayName': commit['author_name'],
            'emails': [commit['author_email']]
        }
        committer = {
            'username': commit['committer_name'],
            'displayName': commit['committer_name'],
            'emails': [commit['committer_email']]
        }

        # Add authored-commit activity
        activities.append(create_activity(commit, 'authored-commit', author, commit['hash']))

        # Add committed-commit activity if the committer is different from the author
        activities.append(
            create_activity(commit,
                            'committed-commit',
                            committer,
                            hashlib.sha1((commit['hash'] +
                                          'commited-commit' +
                                          commit['committer_email']).encode('utf-8')).hexdigest()))

        # Extract and add other activities
        extracted_activities = extract_activities(commit['message'])
        for extracted_activity in extracted_activities:
            activity_type, member_data = list(extracted_activity.items())[0]
            activity_type = activity_type.lower().replace('-by', '') + '-commit'

            member = {
                'username': member_data['name'],
                'displayName': member_data['name'],
                'emails': [member_data['email']]
            }

            source_id = hashlib.sha1((commit['hash'] +
                                      activity_type +
                                      member_data['email']).encode('utf-8')).hexdigest()
            activities.append(create_activity(commit,
                                              activity_type,
                                              member,
                                              source_id,
                                              commit['hash']))

    return activities


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Extract activities from commit messages.')
    parser.add_argument('input_file',
                        help='Input JSON file containing the list of commit dictionaries.')
    parser.add_argument('output_file',
                        help='Output JSON file containing the extracted activities.')
    parser.add_argument('--crowd-activities', action='store_true',
                        help='Enable extraction of crowd activities from commit messages.')
    parser.add_argument('--remote', default='',
                        help='Remote repository URL for the extracted crowd activities.')
    args = parser.parse_args()

    with open(args.input_file, 'r', encoding='utf-8') as input_file:
        commits = json.load(input_file)

    output_data = None
    start_time = time.time()

    if args.crowd_activities:
        if not args.remote:
            print("Error: The --remote argument is required when using --crowd-activities.")
            return

        output_data = prepare_crowd_activities(args.remote, commits, verbose=True)
    else:
        activities_by_commit = {}
        for commit in tqdm.tqdm(commits, desc="Processing commits"):
            commit_hash = commit['hash']
            commit_message = commit['message']
            activities = extract_activities(commit_message)
            activities_by_commit[commit_hash] = activities
        output_data = activities_by_commit

    end_time = time.time()
    logger.info('%d activities extracted in %d s (%.1f min)',
                 len(output_data),
                 int(end_time - start_time),
                 (end_time - start_time) / 60)

    with open(args.output_file, 'w', encoding='utf-8') as output_file:
        json.dump(output_data, output_file, indent=2)


if __name__ == '__main__':
    main()
