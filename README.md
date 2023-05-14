# git-integration

Expected environment variables:

```
CROWD_HOST
TENANT_ID
CROWD_API_KEY
SQS_ENDPOINT_URL
SQS_REGION
SQS_SECRET_ACCESS_KEY
SQS_ACCESS_KEY_ID
CROWD_LOCAL_DIR
```

## Develop

```
mkdir ~/venv/cgit && python -m venv ~/venv/cgit
source ~/venv/cgit/bin/activate
pip install --upgrade pip
pip install -e .
pip install ".[dev]"
```
