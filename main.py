"""
main.py — WCHF License Server (FastAPI)
"""

import os
import hmac
import hashlib
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import License
from auth import verify_admin

# ─────────────────────────────────────────────────────────
# Harus SAMA dengan SECRET_KEY di hwid_license.py
SECRET_KEY = os.environ.get("LICENSE_SECRET_KEY", "").encode("utf-8")
# ─────────────────────────────────────────────────────────

# Buat tabel otomatis saat server start
Base.metadata.create_all(bind=engine)

app = FastAPI(title="YZ License Server", docs_url=None, redoc_url=None)

# CORS — izinkan dari dashboard Vercel kamu
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────

def compute_expected_key(hwid: str) -> str:
    h = hmac.new(SECRET_KEY, hwid.encode("utf-8"), hashlib.sha256)
    digest = h.hexdigest()[:24].upper()
    return "-".join(digest[i:i+6] for i in range(0, 24, 6))


# ── Schemas ───────────────────────────────────────────────

class ValidateRequest(BaseModel):
    hwid: str
    license_key: str

class AddLicenseRequest(BaseModel):
    hwid: str
    license_key: str
    note: str = ""

class RevokeRequest(BaseModel):
    hwid: str

class UpdateNoteRequest(BaseModel):
    hwid: str
    note: str


# ── Public Endpoints (dipanggil dari aplikasi user) ───────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/validate")
def validate_license(req: ValidateRequest, db: Session = Depends(get_db)):
    """
    Dipanggil aplikasi saat startup untuk validasi online.
    Cek: (1) license key benar secara kriptografi, (2) HWID terdaftar & aktif di DB.
    """
    hwid = req.hwid.strip().upper()
    key  = req.license_key.strip().upper()

    # 1. Verifikasi kriptografi
    expected = compute_expected_key(hwid)
    if not hmac.compare_digest(key, expected):
        raise HTTPException(status_code=403, detail="Invalid license key")

    # 2. Cek database
    record = db.query(License).filter(License.hwid == hwid).first()
    if not record:
        raise HTTPException(status_code=404, detail="HWID not registered")
    if not record.is_active:
        raise HTTPException(status_code=403, detail="License revoked")

    # Update last_check_at
    record.last_check_at = datetime.utcnow()
    db.commit()

    return {"valid": True, "note": record.note}


# ── Admin Endpoints (dipanggil dari dashboard Vercel) ─────

@app.get("/admin/licenses", dependencies=[Depends(verify_admin)])
def list_licenses(db: Session = Depends(get_db)):
    """List semua license."""
    licenses = db.query(License).order_by(License.created_at.desc()).all()
    return [
        {
            "hwid":          l.hwid,
            "license_key":   l.license_key,
            "is_active":     l.is_active,
            "note":          l.note,
            "created_at":    l.created_at.isoformat() if l.created_at else None,
            "last_check_at": l.last_check_at.isoformat() if l.last_check_at else None,
            "revoked_at":    l.revoked_at.isoformat() if l.revoked_at else None,
        }
        for l in licenses
    ]


@app.post("/admin/licenses", dependencies=[Depends(verify_admin)])
def add_license(req: AddLicenseRequest, db: Session = Depends(get_db)):
    """Tambah license baru (setelah kamu generate key untuk user)."""
    hwid = req.hwid.strip().upper()
    key  = req.license_key.strip().upper()

    # Validasi key benar dulu
    expected = compute_expected_key(hwid)
    if not hmac.compare_digest(key, expected):
        raise HTTPException(status_code=400, detail="License key tidak valid untuk HWID ini")

    existing = db.query(License).filter(License.hwid == hwid).first()
    if existing:
        # Re-aktivasi kalau pernah di-revoke
        existing.is_active   = True
        existing.license_key = key
        existing.note        = req.note or existing.note
        existing.revoked_at  = None
        db.commit()
        return {"message": "License re-activated", "hwid": hwid}

    record = License(hwid=hwid, license_key=key, note=req.note)
    db.add(record)
    db.commit()
    return {"message": "License added", "hwid": hwid}


@app.post("/admin/revoke", dependencies=[Depends(verify_admin)])
def revoke_license(req: RevokeRequest, db: Session = Depends(get_db)):
    """Revoke license — user tidak bisa pakai app lagi."""
    hwid   = req.hwid.strip().upper()
    record = db.query(License).filter(License.hwid == hwid).first()
    if not record:
        raise HTTPException(status_code=404, detail="HWID tidak ditemukan")

    record.is_active  = False
    record.revoked_at = datetime.utcnow()
    db.commit()
    return {"message": "License revoked", "hwid": hwid}


@app.post("/admin/note", dependencies=[Depends(verify_admin)])
def update_note(req: UpdateNoteRequest, db: Session = Depends(get_db)):
    """Update catatan untuk license (nama user, dll)."""
    hwid   = req.hwid.strip().upper()
    record = db.query(License).filter(License.hwid == hwid).first()
    if not record:
        raise HTTPException(status_code=404, detail="HWID tidak ditemukan")

    record.note = req.note
    db.commit()
    return {"message": "Note updated"}
