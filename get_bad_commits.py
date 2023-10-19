from git import Repo, Git
from pprint import pprint as pp
import os
import requests
import json
from tqdm import tqdm
from dotenv import load_dotenv
import time


def send_post_api_call(endpoint, body):
    load_dotenv()

    CROWD_API_KEY = os.getenv("CROWD_API_KEY")
    CROWD_HOST = os.getenv("CROWD_HOST")
    TENANT_ID = os.getenv("TENANT_ID")
    protocol = "http" if "localhost" in CROWD_HOST else "https"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {CROWD_API_KEY}"}

    url = f"{protocol}://{CROWD_HOST}/api/tenant/{TENANT_ID}/{endpoint}"

    response = requests.request("POST", url, headers=headers, data=json.dumps(body))
    time.sleep(0.25)
    if response.status_code != 200:
        pp(body)
        raise Exception(
            f"Request failed with status code {response.status_code}, error: {response.text}"
        )
    return response.json()


def get_commit_info(commit_id, repo_path="."):
    repo = Repo(repo_path)
    commit = repo.commit(commit_id)

    remote = repo.remotes.origin.url

    endpoint = "activity/query"
    body = {
        "filter": {"channel": remote},
        "limit": 1,
        "offset": 0,
    }

    response_data = send_post_api_call(endpoint, body)
    if len(response_data["rows"]):
        segment_id = response_data["rows"][0]["segmentId"]
    else:
        segment_id = ""

    # Author's name
    author_name = commit.author.name

    # Author's email
    author_email = commit.author.email

    # Title of the commit
    title = commit.message.split("\n")[0]

    # Body of the commit
    body = "\n".join(commit.message.split("\n")[1:])

    # datetime of the commit in UTC
    datetime_utc = commit.authored_datetime

    # timezone of the commit
    timezone = str(commit.authored_datetime.astimezone().tzinfo)

    # extract insertions and deletions
    g = Git(repo_path)
    stats = g.execute(["git", "diff", "--numstat", commit_id + "^", commit_id]).split("\n")[:-1]
    insertions, deletions = 0, 0
    for stat in stats:
        ins, del_, _ = stat.split("\t")
        insertions += int(ins)
        deletions += int(del_)

    activity = {
        "sourceId": commit_id,
        "timestamp": datetime_utc.isoformat(),  # Convert datetime to ISO 8601 format
        "body": body,
        "title": title,
        "type": "authored-commit",
        "channel": remote,
        "platform": "git",
        "attributes": {
            "insertions": insertions,
            "deletions": deletions,
            "lines": insertions + deletions,
            "isMerge": len(commit.parents)
            > 1,  # Determines if the commit is a merge by checking the number of parents
            "api": True,
            "isMainBranch": True,
            "timezone": timezone,
        },
        "member": {
            "username": author_name if author_name else author_email,
            "emails": [author_email],
        },
        "segments": [segment_id],
    }

    send_post_api_call("activity/with-member", activity)


def parse_commit_file(commit_file_path, repo_path):
    with open(commit_file_path, "r") as f:
        commit_data = f.read()

    commits = commit_data.split("-------------\n")
    commits = [commit.strip() for commit in commits if commit.strip()]

    commit_infos = []
    for commit in tqdm(commits):
        commit_id = commit.split("\n")[0]
        get_commit_info(commit_id, repo_path)

    return commit_infos


if __name__ == "__main__":
    import glob

    commit_files = glob.glob("../local/bad-commits/[!DONE]*.txt")
    for commit_file_path in commit_files:
        print(f"Processing {commit_file_path}")
        repo_path = "../local/repos/" + os.path.basename(commit_file_path).replace(".txt", "")
        parse_commit_file(commit_file_path, repo_path)
        os.rename(
            commit_file_path,
            "../local/bad-commits/DONE_"
            + time.strftime("%Y%m%d")
            + "_"
            + os.path.basename(commit_file_path),
        )
