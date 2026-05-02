"""
hwid_license.py — HWID + Activation System (Online Validation)
"""

import os
import sys
import uuid
import hmac
import json
import hashlib
import platform
import subprocess

try:
    import urllib.request
    import urllib.error
    URLLIB_AVAILABLE = True
except ImportError:
    URLLIB_AVAILABLE = False

# ─────────────────────────────────────────────────────────
# ⚠️  Harus sama dengan LICENSE_SECRET_KEY di Render
SECRET_KEY = b"ZhI_YAo_G0NG_FU_ZAI_BU_PA_MEI_CHAI_SH@O_2026"

# URL server Render kamu — ganti setelah deploy
LICENSE_SERVER_URL = "https://yz-license-server.onrender.com"
# ─────────────────────────────────────────────────────────

LICENSE_FILE = os.path.join(os.path.expanduser("~"), ".wchf_license.json")

# Cache online check — hanya cek ke server max 1x per jam
_ONLINE_CHECK_INTERVAL_SECONDS = 3600


def _get_mac_address() -> str:
    mac = uuid.getnode()
    if (mac >> 40) % 2:
        return ""
    return ":".join(("%012X" % mac)[i:i+2] for i in range(0, 12, 2))


def _get_cpu_id() -> str:
    try:
        if sys.platform == "win32":
            result = subprocess.check_output(
                "wmic cpu get ProcessorId", shell=True,
                stderr=subprocess.DEVNULL
            ).decode().strip().split()[-1]
            return result
        elif sys.platform == "darwin":
            result = subprocess.check_output(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                stderr=subprocess.DEVNULL
            ).decode()
            for line in result.split("\n"):
                if "IOPlatformUUID" in line:
                    return line.split('"')[-2]
        else:
            with open("/etc/machine-id", "r") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


def _get_motherboard_serial() -> str:
    try:
        if sys.platform == "win32":
            result = subprocess.check_output(
                "wmic baseboard get SerialNumber", shell=True,
                stderr=subprocess.DEVNULL
            ).decode().strip().split()[-1]
            if result.lower() not in ("serialnumber", "to be filled by o.e.m.", ""):
                return result
    except Exception:
        pass
    return ""


def get_hwid() -> str:
    components = [
        _get_mac_address(),
        _get_cpu_id(),
        _get_motherboard_serial(),
        platform.node(),
        platform.machine(),
    ]
    raw = "|".join(components).encode("utf-8")
    full_hash = hashlib.sha256(raw).hexdigest()
    short = full_hash[:16].upper()
    return "-".join(short[i:i+4] for i in range(0, 16, 4))


def _compute_expected_key(hwid: str) -> str:
    h = hmac.new(SECRET_KEY, hwid.encode("utf-8"), hashlib.sha256)
    digest = h.hexdigest()[:24].upper()
    return "-".join(digest[i:i+6] for i in range(0, 24, 6))


def verify_license(license_key: str) -> tuple[bool, str]:
    """Verifikasi license key secara lokal (kriptografi)."""
    hwid = get_hwid()
    license_key_clean = license_key.strip().upper().replace(" ", "")
    expected = _compute_expected_key(hwid)

    if hmac.compare_digest(license_key_clean, expected):
        return True, "OK"
    else:
        return False, f"License tidak valid untuk perangkat ini.\nHWID: {hwid}"


def _check_online(hwid: str, license_key: str) -> tuple[bool, str]:
    """
    Validasi ke server Render.
    Return (True, "OK") kalau valid.
    Return (True, "offline") kalau server tidak bisa dihubungi — fallback offline.
    Return (False, pesan) kalau server aktif tapi license ditolak.
    """
    if not URLLIB_AVAILABLE:
        return True, "offline"

    try:
        payload = json.dumps({
            "hwid": hwid,
            "license_key": license_key
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{LICENSE_SERVER_URL}/validate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("valid"):
                return True, "OK"
            return False, "License tidak valid di server."

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        try:
            detail = json.loads(body).get("detail", "License ditolak server.")
        except Exception:
            detail = "License ditolak server."
        return False, detail

    except Exception:
        # Server tidak bisa dihubungi — fallback offline
        # App tetap bisa dipakai saat internet mati
        return True, "offline"


def _should_check_online() -> bool:
    """Cek apakah sudah waktunya online check lagi (max 1x per jam)."""
    try:
        if os.path.exists(LICENSE_FILE):
            with open(LICENSE_FILE, "r") as f:
                data = json.load(f)
            last_online = data.get("last_online_check", 0)
            import time
            return (time.time() - last_online) > _ONLINE_CHECK_INTERVAL_SECONDS
    except Exception:
        pass
    return True


def _update_last_online_check():
    """Update timestamp online check terakhir."""
    import time
    try:
        data = {}
        if os.path.exists(LICENSE_FILE):
            with open(LICENSE_FILE, "r") as f:
                data = json.load(f)
        data["last_online_check"] = time.time()
        with open(LICENSE_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def load_saved_license() -> str | None:
    try:
        if os.path.exists(LICENSE_FILE):
            with open(LICENSE_FILE, "r") as f:
                data = json.load(f)
                return data.get("license_key", None)
    except Exception:
        pass
    return None


def save_license(license_key: str):
    try:
        existing = {}
        if os.path.exists(LICENSE_FILE):
            with open(LICENSE_FILE, "r") as f:
                existing = json.load(f)
        existing["license_key"] = license_key
        existing["hwid"]        = get_hwid()
        with open(LICENSE_FILE, "w") as f:
            json.dump(existing, f)
    except Exception:
        pass


def is_activated() -> tuple[bool, str]:
    """
    Cek apakah laptop ini sudah aktif.
    1. Cek lokal dulu (kriptografi, cepat)
    2. Kalau sudah waktunya, cek ke server juga (max 1x per jam)

    Returns:
        (True, "OK")          → aktif
        (False, pesan_error)  → tidak aktif
    """
    key = load_saved_license()
    if not key:
        return False, "Belum ada license tersimpan."

    # Cek lokal
    valid, msg = verify_license(key)
    if not valid:
        return False, msg

    # Cek online (hanya 1x per jam)
    if _should_check_online():
        hwid = get_hwid()
        online_valid, online_msg = _check_online(hwid, key)
        if online_msg != "offline":
            _update_last_online_check()
        if not online_valid:
            return False, online_msg

    return True, "OK"
