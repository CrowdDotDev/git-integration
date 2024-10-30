from fastapi import FastAPI
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.background import BackgroundTasks
import os
from crowdgit import LOCAL_DIR
import asyncio
from dotenv import load_dotenv
from crowdgit.repo import get_repo_name
import logging
import secrets
from crowdgit.ingest import Queue
from crowdgit.get_remotes import get_remotes
import shutil

load_dotenv()

app = FastAPI()
auth_scheme = HTTPBearer()

DEFAULT_REPOS_DIR = os.path.join("..", "..", LOCAL_DIR, "repos")
BAD_COMMITS_DIR = os.path.join("..", "..", LOCAL_DIR, "bad_commits")
REPOS_DIR = os.environ.get("REPOS_DIR", DEFAULT_REPOS_DIR)


def get_local_repo(remote: str, repos_dir: str) -> str:
    return os.path.join(repos_dir, get_repo_name(remote))


def reonboard_repo(remote: str):
    """Reonboard a repository by deleting and re-ingesting it.

    :param remote: The remote URL of the repository to reonboard
    """
    queue = Queue()
    repo_path = get_local_repo(remote, REPOS_DIR)

    remotes = get_remotes(
        os.environ["CROWD_HOST"],
        os.environ["TENANT_ID"],
        os.environ["CROWD_API_KEY"],
    )

    # Find matching remote in tenant's remotes
    for segment_id in remotes:
        integration_id = remotes[segment_id]["integrationId"]
        for tenant_remote in remotes[segment_id]["remotes"]:
            if remote.rstrip(".git") == tenant_remote.rstrip(".git"):
                repo_path = get_local_repo(remote, REPOS_DIR)
                if os.path.exists(repo_path):
                    shutil.rmtree(repo_path)
                    logging.info("Deleted repo %s", remote)
                else:
                    logging.info("Repo %s not found", remote)

                bad_commits_path = get_local_repo(remote, BAD_COMMITS_DIR)
                if os.path.exists(bad_commits_path):
                    shutil.rmtree(bad_commits_path)
                    logging.info("Deleted bad commits for repo %s", remote)
                else:
                    logging.info("Bad commits for repo %s not found", remote)

                logging.info("Ingesting %s for segment %s", remote, segment_id)
                queue.ingest_remote(
                    segment_id=segment_id,
                    integration_id=integration_id,
                    remote=remote,
                )


@app.get("/")
async def root(token: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    if not secrets.compare_digest(token.credentials, os.environ["AUTH_TOKEN"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"message": "Hello World"}


@app.get("/stats")
async def repo_stats(remote: str, token: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    if not secrets.compare_digest(token.credentials, os.environ["AUTH_TOKEN"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    repo_dir = get_local_repo(remote, REPOS_DIR)

    if not os.path.exists(repo_dir):
        raise HTTPException(status_code=404, detail="Repository not found")

    cmd = f"git -C {repo_dir} rev-list --count HEAD"
    process = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        error_message = stderr.decode().strip()
        logging.error(f"Error while executing command: {cmd}. Error: {error_message}")
        raise HTTPException(status_code=500, detail=f"Internal server error")

    return {"remote": remote, "num_commits": int(stdout)}


@app.get("/user-by-email")
async def get_user_name(
    email: str, remote: str, token: HTTPAuthorizationCredentials = Depends(auth_scheme)
):
    if not secrets.compare_digest(token.credentials, os.environ["AUTH_TOKEN"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    repo_dir = get_local_repo(remote, REPOS_DIR)

    if not os.path.exists(repo_dir):
        raise HTTPException(status_code=404, detail="Repository not found")

    # Search in commit authors and various commit message fields
    cmd = f"""
    git -C {repo_dir} log --all --pretty=format:'%an <%ae>%n%b' | 
    awk -v email="{email}" '
    /<{email}>/ {{print $0; exit}}
    /([Ss]igned[-\\s][Oo]ff|[Rr]eviewed|[Aa]pproved|[Ii]nfluenced|[Rr]eported|[Rr]esolved)[-\\s][Bb]y:.*<{email}>/ {{print $0; exit}}
    '
    """
    process = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        error_message = stderr.decode().strip()
        logging.error(f"Error while executing command: {cmd}. Error: {error_message}")
        raise HTTPException(status_code=500, detail="Internal server error")

    log_output = stdout.decode().strip()
    if log_output:
        # Extract name from the matched line
        if ":" in log_output:
            name = log_output.split(":")[1].split("<")[0].strip()
        else:
            name = log_output.split(" <")[0]
        return {"email": email, "name": name}

    raise HTTPException(status_code=404, detail="User not found")


@app.get("/reonboard")
async def reonboard_remote(
    remote: str,
    bg_tasks: BackgroundTasks,
    token: HTTPAuthorizationCredentials = Depends(auth_scheme),
):
    if not secrets.compare_digest(token.credentials, os.environ["AUTH_TOKEN"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    repo_dir = get_local_repo(remote, REPOS_DIR)

    if not os.path.exists(repo_dir):
        raise HTTPException(status_code=404, detail="Repository not found")

    bg_tasks.add_task(reonboard_repo, remote)
    return {"message": "Reonboarding started"}
