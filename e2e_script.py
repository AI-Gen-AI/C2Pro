import sys
import os
sys.path.append(os.path.abspath("apps/api"))

import asyncio
from uuid import uuid4
import jwt
from datetime import datetime, timedelta
import httpx

from src.config import settings

SECRET = "0d398bcf-8234-4609-b42e-bf18aa7f8fe9"
ALGO = "HS256"

async def main():
    # We will generate a UUID for user and tenant
    user_id = str(uuid4())
    tenant_id = str(uuid4())
    
    # Actually wait, if the backend uses Clerk, we might need a real Clerk token
    # Let's see if the backend allows custom JWT if it matches settings.jwt_secret_key
    print(f"User ID: {user_id}")
    print(f"Tenant ID: {tenant_id}")
