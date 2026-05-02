"""
models.py — Struktur tabel database
"""

from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text
from database import Base


class License(Base):
    __tablename__ = "licenses"

    hwid          = Column(String(32), primary_key=True, index=True)
    license_key   = Column(String(32), nullable=False)
    is_active     = Column(Boolean, default=True)
    note          = Column(Text, default="")           # nama user / catatan
    created_at    = Column(DateTime, default=datetime.utcnow)
    last_check_at = Column(DateTime, nullable=True)    # terakhir kali app online check
    revoked_at    = Column(DateTime, nullable=True)
