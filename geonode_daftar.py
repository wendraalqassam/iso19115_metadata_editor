"""Daftar dataset GeoNode bersama: mode kartu (thumbnail) / mode daftar (kolom), kotak cari, dan navigasi halaman —
dipakai katalog "Ambil dari GeoNode" (geonode_katalog.py) dan dialog "Kirim ke GeoNode" (geonode_dialog.py).
Widget ini hanya menampilkan; memuat dataset dari GeoNode tetap tugas dialog (sinyal `muat`)."""
import html

from qgis.core import QgsSettings
from qgis.PyQt.QtCore import QRectF, QSize, Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from qgis.PyQt.QtWidgets import (
    QAbstractItemView, QButtonGroup, QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem,
    QStackedWidget, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from . import geonode_sync as gs
from .geonode_panel import KUNCI

KARTU = QSize(200, 150)       # thumbnail GeoNode berasio 4:3
IKON_DAFTAR = QSize(48, 36)
PK = Qt.ItemDataRole.UserRole
KOLOM = ("Judul", "Jenis", "Kategori", "Pemilik", "Tanggal", "Izin", "Layer")


def potong(teks, n):
    teks = " ".join((teks or "").split())
    return teks if len(teks) <= n else teks[:n - 1].rstrip() + "…"


class DaftarDataset(QWidget):
    """`dipilih(pk | None)` saat pilihan berganti — juga setelah daftar diisi ulang/dikosongkan, agar dialog
    menyegarkan isiannya; `diaktifkan(pk)` saat kartu/baris diklik ganda; `muat(halaman)` saat pengguna mencari
    (Enter) atau berpindah halaman. pk selalu str."""
    dipilih = pyqtSignal(object)
    diaktifkan = pyqtSignal(str)
    muat = pyqtSignal(int)

    def __init__(self, ukuran_halaman=24, parent=None):
        super().__init__(parent)
        self.ukuran = ukuran_halaman
        self._data = {}          # pk → dataset pada halaman aktif
        self._thumb = {}         # url thumbnail → QPixmap
        self._unduh = {}         # url thumbnail → QNetworkReply yang belum selesai
        self._halaman, self._total = 1, 0
        self._klien = None
        self._pk = None
        self._utama = None       # pk dataset asal formulir (diberi lencana)
        self._hidup = True

        self.e_cari = QLineEdit()
        self.e_cari.setPlaceholderText("Cari dataset (Enter)…")
        self.e_cari.setClearButtonEnabled(True)
        self.e_cari.returnPressed.connect(lambda: self.muat.emit(1))
        self.b_kartu = QToolButton()
        self.b_kartu.setText("▦ Kartu")
        self.b_daftar = QToolButton()
        self.b_daftar.setText("☰ Daftar")
        grp = QButtonGroup(self)
        for b in (self.b_kartu, self.b_daftar):
            b.setCheckable(True)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            b.setStyleSheet("QToolButton { padding: 4px 10px; } QToolButton:checked { background: #e0f2fe; "
                            "border: 1px solid #0284c7; color: #0369a1; font-weight: 600; }")
            grp.addButton(b)
        self.b_kartu.toggled.connect(lambda on: on and self._ganti_mode(0))
        self.b_daftar.toggled.connect(lambda on: on and self._ganti_mode(1))
        self.b_sebelum = QToolButton()
        self.b_sebelum.setText("◀")
        self.b_sebelum.setToolTip("Halaman sebelumnya")
        self.b_sebelum.clicked.connect(lambda: self.muat.emit(self._halaman - 1))
        self.b_sesudah = QToolButton()
        self.b_sesudah.setText("▶")
        self.b_sesudah.setToolTip("Halaman berikutnya")
        self.b_sesudah.clicked.connect(lambda: self.muat.emit(self._halaman + 1))
        self.lbl_hal = QLabel("")

        # mode kartu
        self.kartu = QListWidget()
        self.kartu.setViewMode(QListView.ViewMode.IconMode)
        self.kartu.setIconSize(KARTU)
        self.kartu.setGridSize(QSize(KARTU.width() + 20, KARTU.height() + 58))
        self.kartu.setResizeMode(QListView.ResizeMode.Adjust)
        self.kartu.setMovement(QListView.Movement.Static)
        self.kartu.setWordWrap(True)
        self.kartu.setUniformItemSizes(True)
        self.kartu.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.kartu.currentItemChanged.connect(lambda it, _s: self._pilih(it.data(PK) if it else None))
        self.kartu.itemDoubleClicked.connect(lambda it: self.diaktifkan.emit(it.data(PK)))
        # mode daftar
        self.daftar = QTreeWidget()
        self.daftar.setHeaderLabels(KOLOM)
        self.daftar.setRootIsDecorated(False)
        self.daftar.setAlternatingRowColors(True)
        self.daftar.setUniformRowHeights(True)
        self.daftar.setIconSize(IKON_DAFTAR)
        self.daftar.setSortingEnabled(True)
        self.daftar.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        for i, lebar in enumerate((300, 70, 120, 110, 85, 80)):
            self.daftar.setColumnWidth(i, lebar)
        self.daftar.currentItemChanged.connect(lambda it, _s: self._pilih(it.data(0, PK) if it else None))
        self.daftar.itemDoubleClicked.connect(lambda it, _k: self.diaktifkan.emit(it.data(0, PK)))
        self.tumpuk = QStackedWidget()
        self.tumpuk.addWidget(self.kartu)
        self.tumpuk.addWidget(self.daftar)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        alat = QHBoxLayout()
        alat.addWidget(self.e_cari, 1)
        alat.addStretch(0)  # menampung ruang kosong saat kotak cari disembunyikan (tombol tidak melebar)
        alat.addWidget(self.b_kartu)
        alat.addWidget(self.b_daftar)
        alat.addSpacing(12)
        alat.addWidget(self.b_sebelum)
        alat.addWidget(self.lbl_hal)
        alat.addWidget(self.b_sesudah)
        lay.addLayout(alat)
        lay.addWidget(self.tumpuk, 1)

        mode = QgsSettings().value(KUNCI + "katalog_mode", "kartu", type=str)  # sama untuk kedua dialog
        (self.b_daftar if mode == "daftar" else self.b_kartu).setChecked(True)
        self._halaman_navigasi()

    # ------------------------------------------------------------------ API
    def cari(self):
        return self.e_cari.text().strip()

    def halaman(self):
        return self._halaman

    def pk(self):
        return self._pk

    def dataset(self, pk):
        return self._data.get(pk) if pk else None

    def terpilih(self):
        return self.dataset(self._pk)

    def atur_cari(self, tampil):
        """Kotak cari & navigasi halaman (disembunyikan bila daftar hanya berisi dataset tujuan yang dikunci)."""
        for w in (self.e_cari, self.b_sebelum, self.lbl_hal, self.b_sesudah):
            w.setVisible(tampil)

    def isi(self, klien, data, total, halaman=1, utama=None):
        """Tampilkan satu halaman dataset. Pilihan sebelumnya dipertahankan bila masih ada; bila tidak, dataset
        `utama` (asal formulir) dipilih. `dipilih` selalu dipancarkan sesudahnya."""
        self._klien, self._halaman, self._total = klien, max(1, halaman), total
        self._batalkan_unduhan()
        self._data = {str(d.get("pk")): d for d in data}
        self._utama = str(utama) if utama is not None else None
        pilih = self._pk if self._pk in self._data else self._utama if self._utama in self._data else None
        for v in (self.kartu, self.daftar):
            v.blockSignals(True)
        self.kartu.clear()
        self.daftar.clear()
        self.daftar.setSortingEnabled(False)
        for d in data:
            r = gs.ringkas_dataset(d)
            pk = str(r["pk"])
            # Satu URL diunduh sekali walau dipakai beberapa dataset (mis. thumbnail bawaan GeoNode): dua unduhan
            # serentak URL yang sama membuat QGIS crash saat balasannya diproses di tengah aksi lain.
            if r["thumbnail"] and r["thumbnail"] not in self._thumb and r["thumbnail"] not in self._unduh:
                self._unduh_thumbnail(r["thumbnail"])
            it = QListWidgetItem(QIcon(self._gambar_kartu(r)), "%s\n%s" % (
                potong(r["judul"], 56), " · ".join(x for x in (r["jenis"], r["pemilik"]) if x and x != "-")))
            it.setData(PK, pk)
            it.setToolTip(self._tip(r))
            it.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            self.kartu.addItem(it)
            baris = QTreeWidgetItem([r["judul"], r["jenis"], r["kategori"], r["pemilik"], r["tanggal"],
                                     "Ubah" if r["boleh_ubah"] else "Lihat saja", r["layer"]])
            baris.setData(0, PK, pk)
            baris.setToolTip(0, self._tip(r))
            self._ikon_daftar(baris, r)
            if not r["boleh_ubah"]:
                baris.setForeground(5, QColor("#64748b"))
            if pk == self._utama:
                f = QFont(baris.font(0))
                f.setBold(True)
                baris.setFont(0, f)
            self.daftar.addTopLevelItem(baris)
        self.daftar.setSortingEnabled(True)
        for v in (self.kartu, self.daftar):
            v.blockSignals(False)
        self._halaman_navigasi()
        self._pk = None
        self._pilih(pilih)

    def kosongkan(self):
        """Buang daftar (mis. autentikasi berganti: dataset tidak publik & izin login sebelumnya tak boleh tertinggal)."""
        self._batalkan_unduhan()
        for v in (self.kartu, self.daftar):
            v.blockSignals(True)
            v.clear()
            v.blockSignals(False)
        self._data, self._klien, self._total, self._halaman = {}, None, 0, 1
        self._halaman_navigasi()
        self._pk = None
        self.dipilih.emit(None)

    def tutup(self):
        """Dialog ditutup: hentikan unduhan thumbnail yang masih berjalan."""
        self._hidup = False
        self._batalkan_unduhan()

    # ------------------------------------------------------------------ bantu
    def _ganti_mode(self, indeks):
        self.tumpuk.setCurrentIndex(indeks)
        QgsSettings().setValue(KUNCI + "katalog_mode", "daftar" if indeks else "kartu")

    def _halaman_navigasi(self):
        jml = max(1, -(-self._total // self.ukuran))
        self.lbl_hal.setText("Hal. %d/%d · %d dataset" % (self._halaman, jml, self._total) if self._total else "")
        self.b_sebelum.setEnabled(self._halaman > 1)
        self.b_sesudah.setEnabled(self._halaman < jml)

    def _batalkan_unduhan(self):
        for reply in list(self._unduh.values()):
            reply.abort()
        self._unduh.clear()

    def _pilih(self, pk):
        if pk == self._pk:
            return
        self._pk = pk
        self._sorot(pk)
        self.dipilih.emit(pk)

    def _sorot(self, pk):
        """Samakan pilihan di kedua mode tampilan (tanpa memicu _pilih lagi)."""
        for v in (self.kartu, self.daftar):
            v.blockSignals(True)
        self.kartu.setCurrentItem(None)
        self.daftar.setCurrentItem(None)
        for i in range(self.kartu.count()):
            if self.kartu.item(i).data(PK) == pk:
                self.kartu.setCurrentItem(self.kartu.item(i))
                self.kartu.scrollToItem(self.kartu.item(i))
        for i in range(self.daftar.topLevelItemCount()):
            if self.daftar.topLevelItem(i).data(0, PK) == pk:
                self.daftar.setCurrentItem(self.daftar.topLevelItem(i))
                self.daftar.scrollToItem(self.daftar.topLevelItem(i))
        for v in (self.kartu, self.daftar):
            v.blockSignals(False)

    def _tip(self, r):
        return "<b>%s</b><br><code>%s</code><br>%s<br><i>%s</i>%s" % (
            html.escape(r["judul"]), html.escape(r["layer"]), html.escape(potong(r["abstrak"], 300)),
            "Boleh diubah akun Anda." if r["boleh_ubah"] else "Akun Anda hanya bisa melihat dataset ini.",
            "<br><b>Asal formulir GeoMDB saat ini.</b>" if str(r["pk"]) == self._utama else "")

    def _lencana(self, p, x, y, teks, warna, kanan=False):
        fm = p.fontMetrics()
        w, h = fm.horizontalAdvance(teks) + 12, fm.height() + 4
        kotak = QRectF(x - w if kanan else x, y, w, h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(warna)
        p.drawRoundedRect(kotak, 4, 4)
        p.setPen(QColor("#ffffff"))
        p.drawText(kotak, Qt.AlignmentFlag.AlignCenter, teks)

    def _gambar_kartu(self, r):
        w, h = KARTU.width(), KARTU.height()
        pm = QPixmap(w, h)
        pm.fill(QColor("#e2e8f0"))
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        src = self._thumb.get(r["thumbnail"])
        if src is not None:
            s = src.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(0, 0, s, (s.width() - w) // 2, (s.height() - h) // 2, w, h)
        else:
            p.setPen(QColor("#64748b"))
            p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter,
                       "Memuat thumbnail…" if r["thumbnail"] in self._unduh else "Tanpa thumbnail")
        f = QFont(p.font())
        f.setPointSizeF(max(7.0, f.pointSizeF() - 1))
        f.setBold(True)
        p.setFont(f)
        self._lencana(p, 6, h - p.fontMetrics().height() - 10, r["jenis"], QColor("#0369a1"))
        if str(r["pk"]) == self._utama:
            self._lencana(p, 6, 6, "Asal formulir", QColor("#15803d"))
        if not r["boleh_ubah"]:
            self._lencana(p, w - 6, 6, "Hanya lihat", QColor(71, 85, 105, 220), kanan=True)
        p.end()
        return pm

    def _ikon_daftar(self, baris, r):
        src = self._thumb.get(r["thumbnail"])
        if src is not None:
            baris.setIcon(0, QIcon(src))

    def _unduh_thumbnail(self, url):
        if self._klien is None:
            return

        def selesai(isi, url=url):
            self._unduh.pop(url, None)
            if not self._hidup:
                return
            pm = QPixmap()
            if isi and pm.loadFromData(isi):
                self._thumb[url] = pm
            self._segarkan_ikon(url)
        self._unduh[url] = self._klien.ambil_latar(url, selesai)

    def _segarkan_ikon(self, url):
        for i in range(self.kartu.count()):
            it = self.kartu.item(i)
            r = gs.ringkas_dataset(self._data.get(it.data(PK)) or {})
            if r["thumbnail"] == url:
                it.setIcon(QIcon(self._gambar_kartu(r)))
        for i in range(self.daftar.topLevelItemCount()):
            baris = self.daftar.topLevelItem(i)
            r = gs.ringkas_dataset(self._data.get(baris.data(0, PK)) or {})
            if r["thumbnail"] == url:
                self._ikon_daftar(baris, r)
