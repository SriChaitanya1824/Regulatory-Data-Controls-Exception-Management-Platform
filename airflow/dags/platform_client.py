import os
from urllib import request
import json

BASE=os.getenv("PLATFORM_API_URL","http://backend:8000/api")
def call(path,payload=None,token=None):
    body=json.dumps(payload).encode() if payload is not None else None
    headers={"Content-Type":"application/json"}
    if token: headers["Authorization"]=f"Bearer {token}"
    req=request.Request(BASE+path,data=body,headers=headers,method="POST" if body else "GET")
    with request.urlopen(req,timeout=60) as response: return json.loads(response.read())
def token():
    return call("/auth/login",{"username":os.getenv("PLATFORM_USER","analyst@example.com"),"password":os.getenv("PLATFORM_PASSWORD","Governance2026!")})["access_token"]
def execute_controls(): return call("/controls/run",{},token())
def snapshot_dashboard(): return call("/dashboard",token=token())
def overdue(): return call("/exceptions?overdue=true&page_size=100",token=token())
