import base64
import hashlib
import os
import json

def generate_pkce_pair():
    # 生成一个随机的 code_verifier
    code_verifier = base64.urlsafe_b64encode(os.urandom(64)).rstrip(b"=").decode("utf-8")
    
    # 根据 verifier 生成 code_challenge
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode("utf-8")).digest()
    ).rstrip(b"=").decode("utf-8")
    
    return code_verifier, code_challenge

client_id = "OHB2RGpCanU0aGgwOEwtWVFCUDQ6MTpjaQ"
redirect_uri = "https://183.172.202.97:8000/callback"
code_verifier = "Q0qSlsXa4CSPhv90VIEkFA583_iVQ0Fhv4YoXmag89z1tMx8U_iqKNdR3RWNr1PrdzCam4jc9okEn4GNiBvw4g"
code_challenge = "kyGYZc87rmL18L1korbqbQ1YaNaWCB4EYdxi9XAfwq8"

# authorize_url = (
#     "https://twitter.com/i/oauth2/authorize"
#     f"?response_type=code"
#     f"&client_id={client_id}"
#     f"&redirect_uri={redirect_uri}"
#     f"&scope=tweet.read users.read offline.access"
#     f"&state=state123"
#     f"&code_challenge={code_challenge}"
#     f"&code_challenge_method=S256"
# )

# print("Open this URL in your browser to authorize:\n", authorize_url)

import requests

def exchange_code_for_token(client_id, code, code_verifier, redirect_uri):
    token_url = "https://api.x.com/2/oauth2/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
        "code": code,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    print("=== Debug: Request Info ===")
    print("POST", token_url)
    print("Headers:", headers)
    print("Data:", data)
    print("===========================\n")

    response = requests.post(token_url, data=data, headers=headers)

    if not response.ok:
        print("=== Debug: Response Info ===")
        print("Status Code:", response.status_code)
        print("Headers:", response.headers)
        try:
            print("Body:", json.dumps(response.json(), indent=2))
        except Exception:
            print("Body (raw):", response.text)
        print("============================\n")

    response.raise_for_status()
    return response.json()


# 使用示例
code = "TXhDR0tjZ0R1WHllTEw1WmFnQ2xEOFNiUHJjdUM5bmNqaG50cVJwYlZBM0lrOjE3NTg4OTcxNDcxNTA6MToxOmFjOjE"
token_data = exchange_code_for_token(client_id, code, code_verifier, redirect_uri)
print(token_data)
