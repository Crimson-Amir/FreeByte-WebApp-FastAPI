import hashlib
from datetime import datetime, timedelta
import jwt
from fastapi import HTTPException
from . import private

SECRET_KEY = "c21022c524d7c042ce8d34a0bf798d9e06dafb748ff84725f62566172c785832ebfe1f8a9ef2b113ace974e0c5ad732e149a05"
REFRESH_SECRET_KEY = "afshfj8o2374tp12fbrpi27ge020pskdpqwojfd983fbe9pfci0q8w7dgv09qd87g08wdq98wdb09qw"
ALGORITHM = "HS256"

def create_access_token(data: dict, expires_delta: timedelta = timedelta(minutes=15)):
    to_encode = data.copy()
    expire = datetime.now() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")

def create_refresh_token(data: dict, expires_delta: timedelta = timedelta(days=30)):
    to_encode = data.copy()
    expire = datetime.now() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm="HS256")

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def verify_api_token(hashed_token):
    hash_token = hashlib.sha256(private.private_token.encode()).hexdigest()
    return hash_token == hashed_token