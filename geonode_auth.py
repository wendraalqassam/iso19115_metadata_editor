"""Konfigurasi OAuth2 QGIS untuk login ke GeoNode dengan akun masing-masing pengguna.

Admin GeoNode cukup sekali mendaftarkan aplikasi di Django admin → Django OAuth Toolkit →
Applications: grant "Authorization code", Redirect URIs http://127.0.0.1:7070/ (sama dengan
PORT di bawah). Client type "Public" (disarankan: tanpa secret, memakai PKCE) atau
"Confidential" (Client ID + Client secret; secret tersimpan terenkripsi di Auth Manager QGIS).
Kunci JSON mengikuti properti QgsAuthOAuth2Config (src/auth/oauth2/core di QGIS).
"""
import json

from qgis.core import Qgis, QgsApplication, QgsAuthMethodConfig

from . import geonode_sync as gs

PORT = 7070
GRANT_AUTH_CODE, GRANT_PKCE = 0, 3  # QgsAuthOAuth2Config::GrantFlow; PKCE sejak QGIS 3.34


def dukung_pkce():
    return getattr(Qgis, "QGIS_VERSION_INT", 0) >= 33400


def konfigurasi_oauth2(url, client_id, client_secret=""):
    """Aplikasi Public: PKCE (QGIS ≥ 3.34). Aplikasi Confidential (ada secret): Authorization Code
    biasa — client_secret dikirim QGIS ke /o/token/ saat menukar code."""
    base = gs.url_dasar(url)
    secret = (client_secret or "").strip()
    return {
        "configType": 1,  # Custom
        "grantFlow": GRANT_AUTH_CODE if secret or not dukung_pkce() else GRANT_PKCE,
        "name": "GeoNode",
        "requestUrl": base + "/o/authorize/",
        "tokenUrl": base + "/o/token/",
        "refreshTokenUrl": base + "/o/token/",
        "clientId": client_id.strip(),
        "clientSecret": secret,  # kosong untuk aplikasi Public
        "scope": "read write",
        "redirectHost": "127.0.0.1",
        "redirectPort": PORT,
        "redirectUrl": "",
        "persistToken": True,
        "accessMethod": 0,  # header Authorization: Bearer
        "requestTimeout": 30,
        "version": 1,
    }


def buat_authcfg(url, client_id, client_secret=""):
    """Simpan konfigurasi OAuth2 baru di Authentication Manager QGIS; kembalikan ID authcfg."""
    if not client_id.strip():
        raise ValueError("Client ID aplikasi OAuth2 GeoNode wajib diisi.")
    am = QgsApplication.authManager()
    if "OAuth2" not in am.authMethodsKeys():
        raise RuntimeError("Metode autentikasi OAuth2 tidak tersedia di instalasi QGIS ini.")
    if not am.setMasterPassword(True):  # minta master password bila belum dibuka
        raise RuntimeError("Master password QGIS diperlukan untuk menyimpan kredensial.")
    cfg = QgsAuthMethodConfig("OAuth2")
    cfg.setName("GeoMDB — GeoNode %s" % gs.url_dasar(url).split("://", 1)[-1])
    cfg.setUri(gs.url_dasar(url))
    cfg.setConfig("oauth2config", json.dumps(konfigurasi_oauth2(url, client_id, client_secret)))
    hasil = am.storeAuthenticationConfig(cfg)
    ok = hasil[0] if isinstance(hasil, tuple) else hasil
    if isinstance(hasil, tuple) and len(hasil) > 1:
        cfg = hasil[1]
    if not ok or not cfg.id():
        raise RuntimeError("Gagal menyimpan konfigurasi autentikasi QGIS.")
    return cfg.id()
