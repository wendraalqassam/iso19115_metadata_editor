"""Konfigurasi login QGIS ke GeoNode dengan akun masing-masing pengguna: username/password (HTTP Basic).

API GeoNode (/api/v2) menerima login ini. CSW GeoNode tidak mengenalinya (diperlakukan anonim), sehingga record ISO
dataset yang belum dipublikasikan tidak terbaca — lihat geonode_klien.terlihat_publik dan gs.SARAN_BASIC_PRIVAT.
Kredensial tersimpan terenkripsi di Authentication Manager QGIS, bukan di plugin.
"""
from qgis.core import QgsApplication, QgsAuthMethodConfig

from . import geonode_sync as gs

METODE = "Basic"  # satu-satunya metode autentikasi yang didukung GeoMDB


def _siapkan(metode):
    am = QgsApplication.authManager()
    if metode not in am.authMethodsKeys():
        raise RuntimeError("Metode autentikasi %s tidak tersedia di instalasi QGIS ini." % metode)
    if not am.setMasterPassword(True):  # minta master password bila belum dibuka
        raise RuntimeError("Master password QGIS diperlukan untuk menyimpan kredensial.")
    return am


def _simpan(am, cfg):
    hasil = am.storeAuthenticationConfig(cfg)
    ok = hasil[0] if isinstance(hasil, tuple) else hasil
    if isinstance(hasil, tuple) and len(hasil) > 1:
        cfg = hasil[1]
    if not ok or not cfg.id():
        raise RuntimeError("Gagal menyimpan konfigurasi autentikasi QGIS.")
    return cfg.id()


def buat_authcfg_basic(url, username, password):
    """Login username/password akun GeoNode (HTTP Basic), tersimpan terenkripsi di Authentication Manager QGIS."""
    if not username.strip():
        raise ValueError("Username akun GeoNode wajib diisi.")
    am = _siapkan(METODE)
    cfg = QgsAuthMethodConfig(METODE)
    cfg.setName("GeoMDB — GeoNode %s (%s)" % (gs.url_dasar(url).split("://", 1)[-1], username.strip()))
    cfg.setUri(gs.url_dasar(url))
    cfg.setConfig("username", username.strip())
    cfg.setConfig("password", password)
    cfg.setConfig("realm", "")
    return _simpan(am, cfg)


def info_authcfg(authcfg):
    """(metode, username) konfigurasi autentikasi QGIS, mis. ("Basic", "budi"); ("", "") bila kosong atau tidak
    terbaca. Membaca username perlu master password QGIS (sama seperti saat memakainya)."""
    if not authcfg:
        return "", ""
    cfg = QgsAuthMethodConfig()
    hasil = QgsApplication.authManager().loadAuthenticationConfig(authcfg, cfg, True)
    ok = hasil[0] if isinstance(hasil, tuple) else hasil
    if isinstance(hasil, tuple) and len(hasil) > 1:
        cfg = hasil[1]
    if not ok:
        return "", ""
    return cfg.method(), (cfg.config("username", "") or "").strip()


def periksa_authcfg(authcfg):
    """Pesan galat bila konfigurasi autentikasi terpilih tidak bisa dipakai GeoMDB, "" bila bisa (atau kosong =
    anonim). Konfigurasi OAuth2 buatan versi lama dan metode lain ditolak agar QGIS tidak memakainya diam-diam."""
    if not authcfg:
        return ""
    metode, _ = info_authcfg(authcfg)
    if metode == METODE:
        return ""
    if not metode:
        return ("Konfigurasi autentikasi «%s» tidak terbaca (master password QGIS dibatalkan atau konfigurasinya "
                "sudah dihapus). Pilih konfigurasi lain atau buat lewat «Login username/password…»." % authcfg)
    return ("Konfigurasi autentikasi «%s» memakai metode %s. GeoMDB hanya mendukung login username/password akun "
            "GeoNode: buat lewat «Login username/password…», lalu pilih konfigurasi itu." % (authcfg, metode))
