from fastapi import FastAPI
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
from crowdgit import LOCAL_DIR
import asyncio
from dotenv import load_dotenv
from crowdgit.repo import get_repo_name
import logging

load_dotenv()

app = FastAPI()
auth_scheme = HTTPBearer()

DEFAULT_REPOS_DIR = os.path.join("..", "..", LOCAL_DIR, "repos")
REPOS_DIR = os.environ.get("REPOS_DIR", DEFAULT_REPOS_DIR)


@app.get("/")
async def root(token: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    if token.credentials != os.environ["AUTH_TOKEN"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"message": "Hello World"}


@app.get("/stats")
async def repo_stats(remote: str, token: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    if token.credentials != os.environ["AUTH_TOKEN"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    dir_name = get_repo_name(remote)
    repo_dir = os.path.join(REPOS_DIR, dir_name)

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
