# -*- coding: utf-8 -*-

import re
import requests
import hashlib
import time
from typing import List, Dict
from datetime import datetime
import os
import json

import tqdm
from fuzzywuzzy import process

import dotenv
dotenv.load_dotenv('.env')
TOKEN = os.environ['GITHUB_TOKEN']

print(TOKEN)

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

import re
import requests
from typing import List

# Other required imports here

import re
import requests


def get_github_usernames(commit_sha: str, remote: str) -> list:
    """
    Gets the GitHub contributors (author and committer) for a given commit SHA using the GitHub GraphQL API.
    
    Args:
        commit_sha: Commit SHA to query for the corresponding GitHub contributors.
        remote: Remote GitHub repository URL.
        
    Returns:
        list: List of GitHub contributors.
    """
    repo_owner, repo_name = re.split('[:/]', remote)[-2:]
    query = f"""
    {{
      repository(owner:"{repo_owner}" name:"{repo_name}") {{
        object(oid:"{commit_sha}") {{
          ... on Commit {{
            authors(first: 100) {{
                nodes {{
                    name
                    email
                    user {{
                    login
                    }}
                }}
            }}
          }}
        }}
      }}
    }}
    """
    headers = {'Authorization': f"Bearer {TOKEN}"}
    url = "https://api.github.com/graphql"

    response = requests.post(url, json={"query": query}, headers=headers)
    print(response)
    result = response.json()
    commit_object = result.get('data', {}).get('repository', {}).get('object', {})
    contribs = commit_object.get('authors', {}).get('nodes', [])
    out = []
    for contrib in contribs:
        formatted_member = {}
        if 'name' in contrib:
            formatted_member['displayName'] = contrib['name']
        if 'email' in contrib:
            formatted_member['emails'] = [contrib['email']]
        formatted_member['username'] = contrib['user']['login']
        out.append(formatted_member)
    return out

def save_members_info(remote: str, github_members: List[Dict], git_members: List[Dict]) -> None:
    """
    Save member information to a JSON file in the ./members directory.

    Args:
        remote: Remote GitHub repository URL.
        member: Member information to save.
    """
    remote_name = remote.split('/')[-1].replace('.git', '')
    members_directory = './members'
    if not os.path.exists(members_directory):
        os.makedirs(members_directory)
    file_path = os.path.join(members_directory, f'{remote_name}.json')
    
    saved_members = load_saved_members(remote)
    for git_member in git_members:
        if get_saved_member(saved_members, git_member): continue

        matched = False
        for github_member in github_members:
            if git_member['emails'][0] == github_member['emails'][0] or git_member['displayName'] == github_member['displayName'] or git_member['username'] == github_member['username']:
                github_member['matched'] = True
                saved_members.update({git_member['emails'][0]: github_member})
                matched = True
                break
        if not matched:
            git_member['matched'] = False
            saved_members.update({git_member['emails'][0]: git_member})

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(saved_members, f, indent=2, ensure_ascii=False)

def load_saved_members(remote: str) -> Dict:
    """
    Load member information from a JSON file in the ./members directory.

    Args:
        remote: Remote GitHub repository URL.
        git_email: Git email to look for in the existing member information (Optional).

    Returns:
        dict: Loaded member information or a specific member if git_email is provided.
    """
    remote_name = remote.split('/')[-1].replace('.git', '')
    file_path = os.path.join('./members', f'{remote_name}.json')
    
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            all_members = json.load(f)
        return all_members
    return {}

def get_saved_member(loaded_members: List[Dict], member):
    if member['emails'][0] not in loaded_members:
        return False
    return loaded_members[member['emails'][0]]

def prepare_crowd_activities(remote: str,
                             commits: List[Dict] = None,
                             verbose: bool = False) -> List[Dict]:

    def create_activity(commit: Dict,
                        activity_type: str,
                        member: Dict,
                        source_id: str,
                        source_parent_id: str = '') -> Dict:

        dt = datetime.fromisoformat(commit['datetime'])

        return {
            'type': activity_type,
            'timestamp': commit['datetime'],
            'sourceId': source_id,
            'sourceParentId': source_parent_id,
            'platform': 'git',
            'channel': remote,
            'body': '\n'.join(commit['message']),
            'attributes': {
                'insertions': commit.get('insertions', 0),
                'timezone': dt.tzname(),
                'deletions': commit.get('deletions', 0),
                'lines': commit.get('insertions', 0) - commit.get('deletions', 0),
                'isMerge': commit['is_merge_commit'],
                'isMainBranch': True,
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
                                          commit['committer_email']).encode('utf-8')).hexdigest(), commit['hash']))

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
        
        platform = 'github' if 'github' in remote else 'git'
        if platform == 'github':
            loaded_members = load_saved_members(remote)
            # Get all activity members and remove repetition based on email
            git_members = [act['member'] for act in activities]
            all_exist = True
            for git_member in git_members:
                if not get_saved_member(loaded_members, git_member):
                    all_exist = False
                    break
            if not all_exist:
                github_members = get_github_usernames(commit['hash'], remote)
                save_members_info(remote, github_members, git_members)

            loaded_members = load_saved_members(remote)

            for activity in activities:
                member_info = get_saved_member(loaded_members, activity['member'])
                if member_info['matched']:
                    activity['platform'] = 'github'
                    activity['member']['username'] = member_info['username']
                    activity['member']['displayName'] = member_info['displayName']
                    activity['member']['emails'] = list(set(member_info['emails'] + activity['member']['emails']))
                
                if 'matched' in activity['member']:
                    del activity['member']['matched']

                if activity['member']['username'] == 'GitHub' or '[bot]' in activity['member']['username']:
                    activity['platform'] = 'github'
                    activity['member']['attributes'] = {
                        "isBot": True,
                    }

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
        json.dump(output_data, output_file, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main()
