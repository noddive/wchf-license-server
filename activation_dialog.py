"""
activation_dialog.py — Dialog aktivasi WCHF Translator
"""

import sys
import tkinter as tk
import customtkinter as ctk

from hwid_license import get_hwid, verify_license, save_license, is_activated, _check_online

ACCENT       = "#00D46A"
ACCENT_HOVER = "#00B358"
DANGER       = "#FF4560"
BG           = "#0D1117"
CARD         = "#1C2230"
FG           = "#F0F4F8"
FG_DIM       = "#A0AEC0"
BORDER       = "#2D3748"


class ActivationDialog(ctk.CTkToplevel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.title("Aktivasi Aplikasi")
        self.geometry("520x420")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.result = False
        self._hwid  = get_hwid()

        self._build_ui()
        self._center()

    def _center(self):
        self.update_idletasks()
        w, h = 520, 420
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0)
        header.pack(fill="x")

        ctk.CTkLabel(
            header, text="🔐  Aktivasi Aplikasi",
            font=("Segoe UI", 18, "bold"), text_color=FG
        ).pack(pady=(20, 4))

        ctk.CTkLabel(
            header, text="Aplikasi ini memerlukan lisensi untuk perangkat Anda.",
            font=("Segoe UI", 12), text_color=FG_DIM
        ).pack(pady=(0, 16))

        # Body
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=28, pady=20)

        ctk.CTkLabel(
            body, text="Hardware ID (HWID) perangkat ini:",
            font=("Segoe UI", 12, "bold"), text_color=FG_DIM, anchor="w"
        ).pack(anchor="w")

        hwid_frame = ctk.CTkFrame(body, fg_color=CARD, corner_radius=8)
        hwid_frame.pack(fill="x", pady=(4, 16))

        ctk.CTkLabel(
            hwid_frame, text=self._hwid,
            font=("Consolas", 16, "bold"), text_color=ACCENT
        ).pack(side="left", padx=16, pady=12)

        ctk.CTkButton(
            hwid_frame, text="Copy", width=60, height=30,
            fg_color=BORDER, hover_color="#4A5568",
            text_color=FG, font=("Segoe UI", 11),
            command=self._copy_hwid
        ).pack(side="right", padx=10)

        ctk.CTkLabel(
            body,
            text="Kirim HWID di atas ke developer untuk mendapatkan License Key.",
            font=("Segoe UI", 11), text_color=FG_DIM,
            wraplength=460, anchor="w", justify="left"
        ).pack(anchor="w", pady=(0, 16))

        ctk.CTkLabel(
            body, text="Masukkan License Key:",
            font=("Segoe UI", 12, "bold"), text_color=FG_DIM, anchor="w"
        ).pack(anchor="w")

        self._key_var = tk.StringVar()
        self._key_entry = ctk.CTkEntry(
            body, textvariable=self._key_var,
            placeholder_text="XXXXXX-XXXXXX-XXXXXX-XXXXXX",
            font=("Consolas", 14), height=40,
            fg_color="#111827", border_color=BORDER, text_color=FG
        )
        self._key_entry.pack(fill="x", pady=(4, 8))
        self._key_entry.bind("<Return>", lambda e: self._activate())

        self._status_label = ctk.CTkLabel(
            body, text="", font=("Segoe UI", 11), text_color=DANGER, wraplength=460
        )
        self._status_label.pack(anchor="w")

        self._activate_btn = ctk.CTkButton(
            body, text="Aktifkan", height=40,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="#000000", font=("Segoe UI", 13, "bold"),
            command=self._activate
        )
        self._activate_btn.pack(fill="x", pady=(12, 0))

    def _copy_hwid(self):
        self.clipboard_clear()
        self.clipboard_append(self._hwid)
        self._status_label.configure(
            text="✅  HWID berhasil di-copy!", text_color=ACCENT)

    def _activate(self):
        key = self._key_var.get().strip()
        if not key:
            self._status_label.configure(
                text="⚠  Masukkan License Key terlebih dahulu.", text_color=DANGER)
            return

        # 1. Cek lokal dulu
        valid, msg = verify_license(key)
        if not valid:
            self._status_label.configure(text=f"❌  {msg}", text_color=DANGER)
            return

        # 2. Cek ke server
        self._status_label.configure(
            text="⏳  Memvalidasi ke server...", text_color=FG_DIM)
        self._activate_btn.configure(state="disabled")
        self.update()

        online_valid, online_msg = _check_online(self._hwid, key)

        self._activate_btn.configure(state="normal")

        if not online_valid:
            self._status_label.configure(
                text=f"❌  {online_msg}", text_color=DANGER)
            return

        # Berhasil
        save_license(key)
        status_text = "✅  Aktivasi berhasil! Aplikasi akan dibuka..."
        if online_msg == "offline":
            status_text = "✅  Aktivasi berhasil! (Mode offline — server tidak terjangkau)"
        self._status_label.configure(text=status_text, text_color=ACCENT)
        self.result = True
        self.after(1400, self.destroy)

    def _on_close(self):
        self.result = False
        self.destroy()


def check_activation_on_startup(root=None) -> bool:
    """
    Cek apakah aplikasi sudah diaktivasi.
    Jika belum atau license di-revoke, tampilkan dialog aktivasi.
    """
    activated, msg = is_activated()
    if activated:
        return True

    _temp_root = None
    if root is None:
        _temp_root = ctk.CTk()
        _temp_root.withdraw()

    dialog = ActivationDialog(root or _temp_root)
    dialog.wait_window()
    result = dialog.result

    if _temp_root:
        _temp_root.destroy()

    return result
