"""
auth.py — Admin authentication untuk endpoint management
"""

import os
from fastapi import Header, HTTPException

# Set ADMIN_SECRET di environment variable Render
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")


def verify_admin(x_admin_secret: str = Header(...)):
    if not ADMIN_SECRET:
        raise HTTPException(status_code=500, detail="Server misconfigured")
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")
