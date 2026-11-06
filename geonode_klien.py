"""Klien API GeoNode lewat jaringan QGIS (proxy & SSL mengikuti pengaturan QGIS).

Kredensial tidak pernah dipegang plugin: header Authorization disisipkan Authentication Manager
QGIS dari konfigurasi `authcfg` (OAuth2 / Basic), yang tersimpan terenkripsi di qgis-auth.db.
"""
import json

from qgis.core import QgsApplication, QgsNetworkAccessManager
from qgis.PyQt.QtCore import QByteArray, QEventLoop, QTimer, QUrl, QUrlQuery
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest

from . import geonode_sync as gs


class GeoNodeError(Exception):
    def __init__(self, pesan, status=None):
        super().__init__(pesan)
        self.status = status


def _pesan_galat(status, isi):
    """Ringkas pesan galat API GeoNode (DRF: {"errors": [...]} / {"detail": ...})."""
    try:
        j = json.loads(isi.decode("utf-8"))
        for k in ("errors", "detail", "message", "error"):
            if j.get(k):
                v = j[k]
                return "; ".join(map(str, v)) if isinstance(v, list) else str(v)
    except (ValueError, AttributeError):
        pass
    return isi.decode("utf-8", "replace").strip()[:300] or "HTTP %s" % status


class KlienGeoNode:
    def __init__(self, url, authcfg=""):
        self.base = gs.url_dasar(url)
        self.authcfg = authcfg or ""

    def _kirim(self, metode, path, data=None, tipe=None, kueri=None, terima="application/json", batas_waktu=60):
        url = QUrl(path if path.startswith("http") else self.base + path)
        if kueri:
            q = QUrlQuery()
            for k, v in kueri.items():
                for x in (v if isinstance(v, (list, tuple)) else (v,)):  # list → parameter berulang
                    q.addQueryItem(k, str(x))
            url.setQuery(q)
        req = QNetworkRequest(url)
        req.setRawHeader(b"Accept", terima.encode())
        if tipe:
            req.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, tipe)
        if self.authcfg:
            hasil = QgsApplication.authManager().updateNetworkRequest(req, self.authcfg)
            ok, req = hasil if isinstance(hasil, tuple) else (hasil, req)
            if not ok:
                raise GeoNodeError("Konfigurasi autentikasi QGIS tidak dapat dipakai (master password / authcfg).")
        nam = QgsNetworkAccessManager.instance()
        if metode == "GET":
            reply = nam.get(req)
        elif metode == "POST":
            reply = nam.post(req, QByteArray(data or b""))
        else:
            reply = nam.sendCustomRequest(req, metode.encode(), QByteArray(data or b""))
        if self.authcfg:
            QgsApplication.authManager().updateNetworkReply(reply, self.authcfg)
        loop = QEventLoop()
        reply.finished.connect(loop.quit)
        QTimer.singleShot(batas_waktu * 1000, loop.quit)
        loop.exec()
        if not reply.isFinished():
            reply.abort()
            reply.deleteLater()
            raise GeoNodeError("Waktu tunggu habis menghubungi %s" % self.base)
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) or 0
        isi = bytes(reply.readAll())
        galat = reply.error()
        teks_galat = reply.errorString()
        reply.deleteLater()
        if status == 0 and galat != QNetworkReply.NetworkError.NoError:
            raise GeoNodeError("Gagal terhubung ke %s: %s" % (self.base, teks_galat))
        return int(status), isi

    def _json(self, metode, path, sah=(200,), **kw):
        status, isi = self._kirim(metode, path, **kw)
        if status not in sah:
            raise GeoNodeError(_pesan_galat(status, isi), status)
        try:
            return json.loads(isi.decode("utf-8")) if isi else {}
        except ValueError:
            raise GeoNodeError("Respons bukan JSON (HTTP %s) — periksa URL GeoNode." % status, status)

    # ------------------------------------------------------------------ API
    def userinfo(self):
        """Profil pengguna yang sedang login (OAuth2); GeoNodeError(status=401) bila belum login."""
        return gs.bersihkan_userinfo(self._json("GET", gs.ALAMAT["userinfo"]))

    def info_pengguna_basic(self, username):
        """Profil untuk login username/password: /api/o/v4/userinfo hanya mengenali OAuth2, jadi dipakai API pengguna
        (/api/v2/users, wajib login). Password salah → GeoNodeError(status=401). Bentuk hasil seperti userinfo()."""
        j = self._json("GET", "/api/v2/users", kueri={"filter{username}": username, "page_size": 1})
        u = (j.get("users") or [{}])[0]
        grup = []
        if u.get("pk") is not None:
            try:  # informasi tambahan — gagal membacanya tidak boleh menggagalkan login
                grup = gs.nama_grup(self._json("GET", "/api/v2/users/%s/groups" % u["pk"]))
            except GeoNodeError:
                grup = []
        if u.get("is_superuser"):
            grup.append("admin")
        nama = " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x)
        return {"preferred_username": u.get("username") or username, "name": nama, "groups": [g for g in grup if g]}

    def terlihat_publik(self, pk):
        """Dataset bisa dilihat pengguna anonim? CSW GeoNode memperlakukan login username/password sebagai anonim,
        jadi record dataset yang tidak publik tak terbaca dengan login itu."""
        try:
            KlienGeoNode(self.base).dataset(pk)
            return True
        except GeoNodeError as e:
            if e.status in (401, 403, 404):
                return False
            raise

    def datasets(self, cari="", halaman=1, ukuran=50):
        kueri = {"page": halaman, "page_size": ukuran}
        if cari:  # tanpa search_fields GeoNode mengabaikan `search` dan mengembalikan semua dataset
            kueri["search"] = cari
            kueri["search_fields"] = list(gs.KOLOM_CARI)
        j = self._json("GET", gs.ALAMAT["datasets"], kueri=kueri)
        return j.get("datasets") or [], int(j.get("total") or 0)

    def dataset(self, pk):
        j = self._json("GET", gs.ALAMAT["dataset"].format(pk=pk))
        return j.get("dataset") or j

    def set_preserve(self, pk, nilai=True):
        """metadata_uploaded_preserve — jalankan SEBELUM unggah (lihat geonode_sync)."""
        data = json.dumps({"metadata_uploaded_preserve": bool(nilai)}).encode()
        j = self._json("PATCH", gs.ALAMAT["resource"].format(pk=pk), data=data, tipe="application/json")
        res = j.get("resource") or j
        if "metadata_uploaded_preserve" in res and bool(res["metadata_uploaded_preserve"]) != bool(nilai):
            raise GeoNodeError("GeoNode tidak menerima perubahan metadata_uploaded_preserve.")
        return res

    def deteksi_versi(self):
        """Generasi GeoNode ("5", "4.4", "4.2", "4.0") atau None — lihat geonode_sync.versi_dari_api.
        Pakai klien tanpa authcfg agar bisa dijalankan sebelum login (endpoint yang dipakai publik)."""
        akar = self._json("GET", "/api/v2/", batas_waktu=15)
        contoh = None
        if isinstance(akar, dict) and "datasets" in akar and not ({"metadata", "assets"} & set(akar)):
            j = self._json("GET", gs.ALAMAT["datasets"], kueri={"page_size": 1}, batas_waktu=15)
            contoh = (j.get("datasets") or [None])[0]
        return gs.versi_dari_api(akar, contoh)

    def unggah_metadata(self, pk, xml, alternate=""):
        body, tipe = gs.form_unggah(pk, xml, alternate)
        j = self._json("POST", gs.ALAMAT["unggah"], sah=(200, 201), data=body, tipe=tipe, batas_waktu=180)
        exec_id = j.get("execution_id")
        if not exec_id:
            raise GeoNodeError("GeoNode tidak mengembalikan execution_id: %s" % str(j)[:200])
        return exec_id

    def status_eksekusi(self, exec_id):
        return self._json("GET", gs.ALAMAT["status"].format(exec_id=exec_id))

    def tunggu_eksekusi(self, exec_id, batas_detik=180, jeda_ms=2000, lapor=None):
        """Pantau status unggahan sampai finished/failed. `lapor(status, langkah)` opsional."""
        waktu = 0
        while True:
            st = self.status_eksekusi(exec_id)
            status, _ = gs.ringkas_status(st)
            if lapor:
                lapor(status, st.get("step") or "")
            if status in (gs.SELESAI, gs.GAGAL) or waktu >= batas_detik * 1000:
                return st
            loop = QEventLoop()
            QTimer.singleShot(jeda_ms, loop.quit)
            loop.exec()
            waktu += jeda_ms

    def csw_record(self, uuid):
        status, isi = self._kirim("GET", gs.url_csw_record(self.base, uuid), terima="application/xml")
        if status != 200:
            raise GeoNodeError("CSW GeoNode gagal menyajikan record ini (HTTP %s). %s" % (status, gs.SARAN_CSW_RUSAK),
                               status)
        teks = isi.decode("utf-8", "replace")
        galat = gs.pesan_csw(teks)
        if galat:
            raise GeoNodeError("CSW GeoNode gagal menyajikan record ini: %s. %s" % (galat, gs.SARAN_CSW_RUSAK))
        return teks

    def authcfg_untuk(self, url):
        """authcfg hanya untuk URL di host GeoNode ini — token tidak ikut ke host lain."""
        return self.authcfg if self.authcfg and gs.host_sama(url, self.base) else ""

    def ambil_latar(self, url, selesai):
        """GET tanpa menunggu (thumbnail katalog): `selesai(bytes | None)` dipanggil saat balasan tiba.
        Kembalikan QNetworkReply agar pemanggil bisa membatalkannya (abort) saat dialog ditutup."""
        url = url if url.startswith("http") else self.base + url
        req = QNetworkRequest(QUrl(url))
        authcfg = self.authcfg_untuk(url)
        if authcfg:
            hasil = QgsApplication.authManager().updateNetworkRequest(req, authcfg)
            ok, req = hasil if isinstance(hasil, tuple) else (hasil, req)
        reply = QgsNetworkAccessManager.instance().get(req)
        if authcfg:
            QgsApplication.authManager().updateNetworkReply(reply, authcfg)

        sudah = []

        def _beres():
            if sudah:  # finished hanya diproses sekali per balasan
                return
            sudah.append(True)
            isi = bytes(reply.readAll()) if reply.error() == QNetworkReply.NetworkError.NoError else None
            reply.deleteLater()
            selesai(isi)
        reply.finished.connect(_beres)
        return reply
