import requests

url = f"https://{CROWD_HOST}/api/tenant/{TENANT_ID}/git"

payload = {}
headers = {
  f'Authorization': 'Bearer {CROWD_API_KEY}'
}

response = requests.request("GET", url, headers=headers, data=payload)