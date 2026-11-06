"""Panel koneksi GeoNode bersama (URL, versi GeoNode, autentikasi QGIS, tombol Masuk) — dipakai dialog
katalog "Ambil dari GeoNode" dan dialog "Kirim ke GeoNode". URL, versi & authcfg tersimpan di QgsSettings."""
import functools
import html

from qgis.core import QgsSettings
from qgis.gui import QgsAuthConfigSelect
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout,
    QWidget,
)

from . import geonode_auth
from . import geonode_sync as gs
from .geonode_klien import GeoNodeError, KlienGeoNode

KUNCI = "GeoMDB/geonode/"
OTOMATIS = "auto"


def satu_aksi(fungsi):
    """Aksi dialog GeoNode tidak boleh berjalan bersamaan. processEvents (log/status) dan loop jaringan bisa memicu
    klik, Enter, atau timer «Masuk otomatis» di tengah aksi lain; memuat ulang daftar di tengah «Ambil» membuat QGIS
    crash. Aksi kedua diabaikan selama aksi pertama belum selesai. Hubungkan ke sinyal lewat lambda (argumen sinyal
    seperti `checked` tidak diteruskan)."""
    @functools.wraps(fungsi)
    def bungkus(self, *a, **k):
        if getattr(self, "_sibuk", False):
            return None
        self._sibuk = True
        try:
            return fungsi(self, *a, **k)
        finally:
            self._sibuk = False
    return bungkus


class PanelKoneksi(QWidget):
    """`tersambung` dipancarkan setelah Masuk berhasil (login, atau anonim bila belum ada authcfg);
    `versi_berubah` setelah versi GeoNode terdeteksi atau dipilih manual."""
    tersambung = pyqtSignal()
    versi_berubah = pyqtSignal()

    def __init__(self, judul, catat, parent=None):
        super().__init__(parent)
        self.judul = judul
        self.catat = catat
        self._terdeteksi = {}  # url dasar → generasi GeoNode (None = tak dapat dipastikan)
        self.metode = ""  # metode login authcfg saat Masuk: "OAuth2" | "Basic" | "" (anonim / lainnya)
        s = QgsSettings()
        self.e_url = QLineEdit(s.value(KUNCI + "url", "", type=str))
        self.e_url.setPlaceholderText("https://geoportal.contoh.go.id")
        self.e_url.returnPressed.connect(self.masuk)
        self.e_url.editingFinished.connect(lambda: self.deteksi(diam=True))
        self.cb_versi = QComboBox()
        self.cb_versi.addItem("Deteksi otomatis", OTOMATIS)
        for kunci, profil in gs.VERSI.items():
            self.cb_versi.addItem(profil["label"], kunci)
        self.cb_versi.setCurrentIndex(max(0, self.cb_versi.findData(s.value(KUNCI + "versi", OTOMATIS, type=str))))
        self.cb_versi.setToolTip("Menentukan cara plugin mengirim metadata. Deteksi otomatis membaca daftar layanan "
                                 "API GeoNode (tanpa login); pilih manual bila hasil deteksi keliru.")
        self.cb_versi.currentIndexChanged.connect(self._versi_dipilih)
        self.lbl_versi = QLabel("")
        self.lbl_versi.setStyleSheet("color: #475569;")
        self.sel_auth = QgsAuthConfigSelect(self)
        self.sel_auth.setConfigId(s.value(KUNCI + "authcfg", "", type=str))
        b_oauth = QPushButton("Buat konfigurasi OAuth2…")
        b_oauth.setToolTip("Buat konfigurasi login OAuth2 GeoNode dari Client ID aplikasi yang didaftarkan admin GeoNode.")
        b_oauth.clicked.connect(self.buat_oauth2)
        b_basic = QPushButton("Login username/password…")
        b_basic.setToolTip("Login dengan username & password akun GeoNode (tanpa mendaftarkan aplikasi OAuth2). Cukup "
                           "untuk dataset yang sudah dipublikasikan; dataset tidak publik perlu OAuth2.")
        b_basic.clicked.connect(self.buat_basic)
        self.b_masuk = QPushButton("Masuk && muat dataset")  # && = karakter & (bukan pintasan)
        self.b_masuk.clicked.connect(self.masuk)
        self.lbl_user = QLabel("Belum masuk.")
        self.lbl_user.setWordWrap(True)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("URL GeoNode", self.e_url)
        baris_versi = QHBoxLayout()
        baris_versi.addWidget(self.cb_versi)
        baris_versi.addWidget(self.lbl_versi, 1)
        form.addRow("Versi GeoNode", baris_versi)
        baris_auth = QHBoxLayout()
        baris_auth.addWidget(self.sel_auth, 1)
        baris_auth.addWidget(b_basic)
        baris_auth.addWidget(b_oauth)
        form.addRow("Autentikasi", baris_auth)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(form)
        baris = QHBoxLayout()
        baris.addWidget(self.b_masuk)
        baris.addWidget(self.lbl_user, 1)
        lay.addLayout(baris)

    # ------------------------------------------------------------------ versi
    def versi(self):
        """Generasi GeoNode yang dipakai (kunci gs.VERSI): pilihan manual, atau hasil deteksi; None bila belum tahu."""
        pilih = self.cb_versi.currentData()
        if pilih and pilih != OTOMATIS:
            return pilih
        return self._terdeteksi.get(gs.url_dasar(self.e_url.text()))

    def deteksi(self, klien=None, diam=False, paksa=False):
        """Deteksi generasi GeoNode dari URL — tanpa login (klien anonim) kecuali `klien` diberikan."""
        url = gs.url_dasar(self.e_url.text())
        if not url:
            self.lbl_versi.setText("")
            return None
        if url in self._terdeteksi and not paksa:
            self._tampil_versi()
            return self._terdeteksi[url]
        try:
            v = (klien or KlienGeoNode(url)).deteksi_versi()
        except GeoNodeError as e:
            v = None
            if not diam:
                self.catat("Versi GeoNode tidak dapat dideteksi: %s" % e)
        self._terdeteksi[url] = v
        self._tampil_versi()
        self.versi_berubah.emit()
        return v

    def _tampil_versi(self):
        url = gs.url_dasar(self.e_url.text())
        v = self._terdeteksi.get(url)
        pilih = self.cb_versi.currentData()
        if v:
            teks = "Terdeteksi: %s" % gs.VERSI[v]["label"]
            if pilih not in (OTOMATIS, v):
                teks += " — berbeda dengan pilihan manual"
        elif url in self._terdeteksi:
            teks = "Tidak terdeteksi — masuk dulu, atau pilih versinya secara manual."
        else:
            teks = ""
        self.lbl_versi.setText(teks)

    def _versi_dipilih(self, _i):
        QgsSettings().setValue(KUNCI + "versi", self.cb_versi.currentData())
        self._tampil_versi()
        self.versi_berubah.emit()

    # ------------------------------------------------------------------ koneksi
    def klien(self):
        url = gs.url_dasar(self.e_url.text())
        if not url:
            raise GeoNodeError("Isi URL GeoNode terlebih dahulu.")
        s = QgsSettings()
        s.setValue(KUNCI + "url", url)
        s.setValue(KUNCI + "authcfg", self.sel_auth.configId())
        return KlienGeoNode(url, self.sel_auth.configId())

    def buat_oauth2(self):
        url = gs.url_dasar(self.e_url.text())
        if not url:
            QMessageBox.information(self, self.judul, "Isi URL GeoNode terlebih dahulu.")
            return
        v = self.deteksi()  # sebelum login: endpoint yang dipakai publik
        info = ("GeoNode terdeteksi: %s\n\n" % gs.VERSI[v]["label"]) if v else \
            "Versi GeoNode belum dapat dideteksi dari URL ini (periksa URL-nya).\n\n"
        cid, ok = QInputDialog.getText(self, self.judul, info + "Client ID aplikasi OAuth2 GeoNode\n(dari admin "
                                       "GeoNode; redirect URI: http://127.0.0.1:%d/)" % geonode_auth.PORT)
        if not ok or not cid.strip():
            return
        secret, ok = QInputDialog.getText(self, self.judul, "Client secret (kosongkan bila aplikasi bertipe Public)\n"
                                          "Disimpan terenkripsi di Authentication Manager QGIS.",
                                          QLineEdit.EchoMode.Password)
        if not ok:
            return
        try:
            self.sel_auth.setConfigId(geonode_auth.buat_authcfg(url, cid, secret))
            alur = ("Authorization Code + client secret" if secret.strip()
                    else "PKCE" if geonode_auth.dukung_pkce() else "Authorization Code")
            self.catat("Konfigurasi OAuth2 dibuat (%s). Saat masuk, QGIS membuka browser untuk login GeoNode." % alur)
        except Exception as e:
            QMessageBox.warning(self, self.judul, str(e))

    def buat_basic(self):
        url = gs.url_dasar(self.e_url.text())
        if not url:
            QMessageBox.information(self, self.judul, "Isi URL GeoNode terlebih dahulu.")
            return
        user, ok = QInputDialog.getText(self, self.judul, "Username akun GeoNode")
        if not ok or not user.strip():
            return
        sandi, ok = QInputDialog.getText(self, self.judul, "Password akun GeoNode «%s»\nDisimpan terenkripsi di "
                                         "Authentication Manager QGIS." % user.strip(), QLineEdit.EchoMode.Password)
        if not ok:
            return
        try:
            self.sel_auth.setConfigId(geonode_auth.buat_authcfg_basic(url, user, sandi))
            self.catat("Login username/password «%s» disimpan. Klik «Masuk & muat dataset»." % user.strip())
        except Exception as e:
            QMessageBox.warning(self, self.judul, str(e))

    def basic(self):
        """Login terakhir memakai username/password? (CSW GeoNode memperlakukannya sebagai anonim.)"""
        return self.metode == "Basic"

    def masuk(self):
        try:
            k = self.klien()
            self.catat("Menghubungi %s …" % k.base)
            self.metode, username = geonode_auth.info_authcfg(k.authcfg)
            try:
                if self.basic():
                    info = k.info_pengguna_basic(username)
                else:
                    info = k.userinfo()
                grup = ", ".join(info.get("groups") or []) or "-"
                self.lbl_user.setText("Masuk sebagai <b>%s</b> (grup: %s)%s" % (
                    html.escape(info.get("preferred_username") or info.get("name") or "?"), html.escape(grup),
                    " — login username/password: cukup untuk dataset yang sudah dipublikasikan; dataset tidak "
                    "publik perlu OAuth2." if self.basic() else ""))
            except GeoNodeError as e:
                if self.basic() and e.status in (401, 403):
                    raise GeoNodeError("Username atau password GeoNode salah (konfigurasi «%s»)." % k.authcfg, e.status)
                if e.status in (401, 403):
                    self.lbl_user.setText("Belum masuk — pilih/buat konfigurasi autentikasi. Dataset publik tetap "
                                          "tampil, tetapi tidak bisa diubah.")
                else:
                    raise
            if not self.deteksi(diam=True):  # 4.x tanpa dataset publik: ulangi dengan akun yang login
                self.deteksi(klien=k, diam=True, paksa=True)
        except GeoNodeError as e:
            self.catat("Gagal: %s" % e)
            QMessageBox.warning(self, self.judul, str(e))
            return
        except Exception as e:  # galat tak terduga (mis. bentuk respons GeoNode lain): tampilkan, jangan traceback QGIS
            self.catat("Galat: %s" % e)
            QMessageBox.warning(self, self.judul, "Galat tak terduga saat masuk:\n%s" % e)
            return
        self.tersambung.emit()
