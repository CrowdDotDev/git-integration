from fastapi import FastAPI
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
from crowdgit import LOCAL_DIR
import subprocess
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
auth_scheme = HTTPBearer()

DEFAULT_REPOS_DIR = os.path.join(LOCAL_DIR, "repos")
REPOS_DIR = os.environ.get("REPOS_DIR", DEFAULT_REPOS_DIR)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/stats/{owner}/{repo}")
def repo_stats(owner: str, repo: str, token: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    if token.credentials != os.environ["AUTH_TOKEN"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    dir_name = f"{owner}-{repo}"
    repo_dir = os.path.join(REPOS_DIR, dir_name)

    if not os.path.exists(repo_dir):
        raise HTTPException(status_code=404, detail="Repository not found")

    # using subprocess to run the git command and get number of commits in the repo

    cmd = f"git -C {repo_dir} rev-list --count HEAD"
    result = subprocess.run(cmd, shell=True, capture_output=True)
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail="Internal server error")

    return {"repo": repo, "owner": owner, "num_commits": int(result.stdout)}
