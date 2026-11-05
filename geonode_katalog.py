"""Dialog "Ambil dari GeoNode": katalog dataset GeoNode (mode kartu / daftar) dengan pratinjau peta dari
layanan WMS dataset, lalu muat metadata dataset terpilih (record ISO dari CSW GeoNode) ke formulir.
Pembaruan ke GeoNode tetap lewat tombol "Kirim ke GeoNode" di bawah editor (geonode_dialog.py)."""
import html

from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsDataSourceUri, QgsProject, QgsRasterLayer, QgsRectangle,
    QgsSettings,
)
from qgis.gui import QgsMapCanvas, QgsMapToolPan
from qgis.PyQt.QtCore import QRectF, QSize, Qt, QTimer
from qgis.PyQt.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from qgis.PyQt.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QListView,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSplitter, QStackedWidget, QTextBrowser, QToolButton,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from . import gmd_importer
from . import geonode_sync as gs
from .geonode_klien import GeoNodeError
from .geonode_panel import KUNCI, PanelKoneksi

JUDUL = "Ambil Metadata dari GeoNode"
UKURAN_HALAMAN = 24
KARTU = QSize(200, 150)       # thumbnail GeoNode berasio 4:3
IKON_DAFTAR = QSize(48, 36)
PK = Qt.ItemDataRole.UserRole
WEB_MERCATOR = "EPSG:3857"
OSM = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
INDONESIA = (94.0, -11.5, 141.5, 6.5)  # tampilan awal peta sebelum dataset dipilih
KOLOM = ("Judul", "Jenis", "Kategori", "Pemilik", "Tanggal", "Izin", "Layer")


def _potong(teks, n):
    teks = " ".join((teks or "").split())
    return teks if len(teks) <= n else teks[:n - 1].rstrip() + "…"


class DialogKatalogGeoNode(QDialog):
    def __init__(self, editor, parent=None):
        super().__init__(parent or editor)
        self.editor = editor
        self.setWindowTitle(JUDUL)
        self.resize(1180, 760)
        s = QgsSettings()
        self._data = {}          # pk (str) → dataset dari halaman katalog aktif
        self._thumb = {}         # url thumbnail → QPixmap (None = sedang diunduh)
        self._unduh = {}         # url thumbnail → QNetworkReply yang belum selesai
        self._halaman, self._total = 1, 0
        self._klien = None
        self._pk = None
        self._wms = self._basemap = None
        self._sedang = False     # pratinjau WMS sedang dimuat (pembuatan layer WMS memblokir)
        self._hidup = True

        self.status = QLabel("")
        self.panel = PanelKoneksi(JUDUL, self._catat, self)
        self.panel.tersambung.connect(lambda: self.muat(1))

        self.e_cari = QLineEdit()
        self.e_cari.setPlaceholderText("Cari dataset (Enter)…")
        self.e_cari.setClearButtonEnabled(True)
        self.e_cari.returnPressed.connect(lambda: self.muat(1))
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
        self.b_sebelum.clicked.connect(lambda: self.muat(self._halaman - 1))
        self.b_sesudah = QToolButton()
        self.b_sesudah.setText("▶")
        self.b_sesudah.setToolTip("Halaman berikutnya")
        self.b_sesudah.clicked.connect(lambda: self.muat(self._halaman + 1))
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
        self.kartu.itemDoubleClicked.connect(lambda _it: self.ambil())
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
        self.daftar.itemDoubleClicked.connect(lambda _it, _k: self.ambil())
        self.tumpuk = QStackedWidget()
        self.tumpuk.addWidget(self.kartu)
        self.tumpuk.addWidget(self.daftar)

        # pratinjau peta
        self.kanvas = QgsMapCanvas()
        self.kanvas.setCanvasColor(QColor("#eef2f6"))
        self.kanvas.setDestinationCrs(QgsCoordinateReferenceSystem(WEB_MERCATOR))
        self.kanvas.setMinimumSize(340, 260)
        self._geser = QgsMapToolPan(self.kanvas)
        self.kanvas.setMapTool(self._geser)
        self.cb_osm = QCheckBox("Peta dasar OpenStreetMap")
        self.cb_osm.setChecked(s.value(KUNCI + "katalog_osm", True, type=bool))
        self.cb_osm.toggled.connect(self._atur_lapisan)
        self.lbl_osm = QLabel("© kontributor OpenStreetMap")
        self.lbl_osm.setStyleSheet("color: #64748b; font-size: 10px;")
        b_cakupan = QToolButton()
        b_cakupan.setText("⤢ Ke cakupan data")
        b_cakupan.clicked.connect(self._ke_cakupan)
        self.lbl_peta = QLabel("Pilih dataset untuk melihat pratinjau peta dari layanan WMS-nya.")
        self.lbl_peta.setWordWrap(True)
        self.lbl_peta.setStyleSheet("color: #475569;")
        self.info = QTextBrowser()
        self.info.setOpenExternalLinks(True)

        self.b_ambil = QPushButton("⬇ Ambil ke formulir")
        self.b_ambil.setToolTip("Isi formulir GeoMDB dengan metadata dataset terpilih (record ISO dari CSW GeoNode) "
                                "untuk disunting. Klik ganda kartu/baris juga mengambilnya.")
        self.b_ambil.setEnabled(False)
        self.b_ambil.clicked.connect(self.ambil)
        b_tutup = QPushButton("Tutup")
        b_tutup.clicked.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(self.panel)
        alat = QHBoxLayout()
        alat.addWidget(self.e_cari, 1)
        alat.addWidget(self.b_kartu)
        alat.addWidget(self.b_daftar)
        alat.addSpacing(12)
        alat.addWidget(self.b_sebelum)
        alat.addWidget(self.lbl_hal)
        alat.addWidget(self.b_sesudah)
        lay.addLayout(alat)
        kanan = QWidget()
        vk = QVBoxLayout(kanan)
        vk.setContentsMargins(0, 0, 0, 0)
        vk.addWidget(self.kanvas, 3)
        baris_peta = QHBoxLayout()
        baris_peta.addWidget(self.cb_osm)
        baris_peta.addWidget(self.lbl_osm)
        baris_peta.addStretch(1)
        baris_peta.addWidget(b_cakupan)
        vk.addLayout(baris_peta)
        vk.addWidget(self.lbl_peta)
        vk.addWidget(self.info, 2)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self.tumpuk)
        split.addWidget(kanan)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        split.setSizes([660, 500])
        lay.addWidget(split, 1)
        bawah = QHBoxLayout()
        bawah.addWidget(self.status, 1)
        bawah.addWidget(self.b_ambil)
        bawah.addWidget(b_tutup)
        lay.addLayout(bawah)
        for b in self.findChildren(QPushButton):  # Enter di kotak cari tidak boleh menekan tombol mana pun
            b.setAutoDefault(False)
            b.setDefault(False)

        self._tunda = QTimer(self)  # navigasi cepat (panah) tidak memuat WMS untuk tiap baris yang dilewati
        self._tunda.setSingleShot(True)
        self._tunda.setInterval(350)
        self._tunda.timeout.connect(self._pratinjau)

        (self.b_daftar if s.value(KUNCI + "katalog_mode", "kartu", type=str) == "daftar" else self.b_kartu).setChecked(True)
        self._halaman_navigasi()
        self._atur_lapisan()
        self._ke_cakupan()
        tautan = getattr(editor, "geonode_tautan", None)
        if tautan:
            self.panel.e_url.setText(tautan["url"])
        if gs.url_dasar(self.panel.e_url.text()):
            QTimer.singleShot(0, self.panel.masuk)  # tampilkan dialog dulu, baru hubungi GeoNode

    # ------------------------------------------------------------------ bantu
    def _catat(self, teks):
        self.status.setText(teks)
        QApplication.processEvents()

    def _ganti_mode(self, indeks):
        self.tumpuk.setCurrentIndex(indeks)
        QgsSettings().setValue(KUNCI + "katalog_mode", "daftar" if indeks else "kartu")

    def _halaman_navigasi(self):
        jml = max(1, -(-self._total // UKURAN_HALAMAN))
        self.lbl_hal.setText("Hal. %d/%d · %d dataset" % (self._halaman, jml, self._total) if self._total else "")
        self.b_sebelum.setEnabled(self._halaman > 1)
        self.b_sesudah.setEnabled(self._halaman < jml)

    def _batalkan_unduhan(self):
        for reply in list(self._unduh.values()):
            reply.abort()
        self._unduh.clear()

    # ------------------------------------------------------------------ katalog
    def muat(self, halaman=1):
        try:
            k = self.panel.klien()
            data, total = k.datasets(cari=self.e_cari.text().strip(), halaman=max(1, halaman), ukuran=UKURAN_HALAMAN)
        except GeoNodeError as e:
            self._catat("Gagal memuat katalog: %s" % e)
            return
        self._klien, self._halaman, self._total = k, max(1, halaman), total
        self._batalkan_unduhan()
        self._data = {str(d.get("pk")): d for d in data}
        tautan = getattr(self.editor, "geonode_tautan", None)
        pilih = self._pk if self._pk in self._data else None
        for v in (self.kartu, self.daftar):
            v.blockSignals(True)
        self.kartu.clear()
        self.daftar.clear()
        self.daftar.setSortingEnabled(False)
        bisa = 0
        for d in data:
            r = gs.ringkas_dataset(d)
            pk = str(r["pk"])
            bisa += r["boleh_ubah"]
            if r["thumbnail"] and r["thumbnail"] not in self._thumb:
                self._unduh_thumbnail(r["thumbnail"])
            it = QListWidgetItem(QIcon(self._gambar_kartu(r)), "%s\n%s" % (
                _potong(r["judul"], 56), " · ".join(x for x in (r["jenis"], r["pemilik"]) if x and x != "-")))
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
            self.daftar.addTopLevelItem(baris)
            if pilih is None and gs.tautan_cocok(tautan, k.base, pk):
                pilih = pk
        self.daftar.setSortingEnabled(True)
        for v in (self.kartu, self.daftar):
            v.blockSignals(False)
        self._halaman_navigasi()
        self._catat("%d dataset ditampilkan (dari %d), %d boleh diubah akun ini." % (len(data), total, bisa))
        self._pk = None
        self._pilih(pilih)

    def _tip(self, r):
        return "<b>%s</b><br><code>%s</code><br>%s<br><i>%s</i>" % (
            html.escape(r["judul"]), html.escape(r["layer"]), html.escape(_potong(r["abstrak"], 300)),
            "Boleh diubah akun Anda." if r["boleh_ubah"] else "Akun Anda hanya bisa melihat dataset ini.")

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

    def _pilih(self, pk):
        if pk == self._pk and pk is not None:
            return
        self._pk = pk
        self._sorot(pk)
        d = self._data.get(pk) if pk else None
        self.b_ambil.setEnabled(d is not None)
        self._isi_info(d)
        if d is None:
            self._wms = None
            self.lbl_peta.setText("Pilih dataset untuk melihat pratinjau peta dari layanan WMS-nya.")
            self._atur_lapisan()
            return
        self.lbl_peta.setText("Memuat pratinjau WMS …")
        self._tunda.start()

    def _isi_info(self, d):
        if d is None:
            self.info.setHtml("")
            return
        r = gs.ringkas_dataset(d)
        meta = " · ".join(html.escape(x) for x in (r["jenis"], r["kategori"], r["pemilik"], r["tanggal"]) if x and x != "-")
        izin = ("<span style='color:#15803d'>✔ Boleh diubah akun ini</span>" if r["boleh_ubah"] else
                "<span style='color:#64748b'>🔒 Hanya lihat — akun ini tidak bisa memperbarui metadatanya</span>")
        detail = d.get("detail_url") or ""
        if detail and not detail.startswith("http") and self._klien is not None:
            detail = self._klien.base + detail
        tautan = ("<br><a href='%s'>Buka halaman dataset di GeoNode ↗</a>" % html.escape(detail, quote=True)
                  if detail.startswith(("https://", "http://")) else "")
        self.info.setHtml("<b style='font-size:13px'>%s</b><br><span style='color:#475569'>%s</span><br>%s<br>"
                          "<span style='color:#475569'>Layer:</span> <code>%s</code>%s<p>%s</p>" % (
                              html.escape(r["judul"]), meta, izin, html.escape(r["layer"]), tautan,
                              html.escape(_potong(r["abstrak"], 800)) or "<i>Tanpa abstrak.</i>"))

    # ------------------------------------------------------------------ pratinjau peta
    def _lapisan_wms(self, url, layer, judul):
        uri = QgsDataSourceUri()
        uri.setParam("url", url)
        uri.setParam("layers", layer)
        uri.setParam("styles", "")
        uri.setParam("format", "image/png")
        uri.setParam("crs", WEB_MERCATOR)
        uri.setParam("dpiMode", "7")
        uri.setParam("contextualWMSLegend", "0")
        authcfg = self._klien.authcfg_untuk(url) if self._klien else ""
        if authcfg:  # dataset privat: GeoServer GeoNode menerima token OAuth2 yang sama
            uri.setAuthConfigId(authcfg)
        return QgsRasterLayer(bytes(uri.encodedUri()).decode(), judul, "wms")

    def _pratinjau(self):
        if self._sedang:
            return  # pemuatan sebelumnya akan mengulang untuk pilihan terbaru
        pk = self._pk
        d = self._data.get(pk) if pk else None
        if d is None:
            return
        w = gs.wms_pratinjau(d)
        if not w:
            self._wms = None
            self.lbl_peta.setText("Dataset ini tidak punya layanan WMS — pratinjau peta tidak tersedia.")
            self._atur_lapisan()
            self._ke_cakupan()
            return
        self._sedang = True
        try:
            judul = d.get("title") or w[1]
            lapisan = self._lapisan_wms(w[0], w[1], judul)
            umum = gs.layanan_wms(d)
            if not lapisan.isValid() and umum and umum[0].split("?", 1)[0] != w[0]:
                w = (umum[0].split("?", 1)[0], umum[1])  # GeoServer tanpa layanan virtual per-layer
                lapisan = self._lapisan_wms(w[0], w[1], judul)
        finally:
            self._sedang = False
        if not self._hidup:
            return
        if pk != self._pk:  # pilihan berubah selama memuat
            self._tunda.start()
            return
        if lapisan.isValid():
            self._wms = lapisan
            self.lbl_peta.setText("WMS: %s — layer <code>%s</code>" % (html.escape(w[0]), html.escape(w[1])))
        else:
            self._wms = None
            self.lbl_peta.setText("Layanan WMS dataset ini tidak dapat dimuat: %s" % html.escape(
                _potong(lapisan.error().summary(), 200) or w[0]))
        self._atur_lapisan()
        self._ke_cakupan()

    def _peta_dasar(self):
        if self._basemap is None:
            uri = QgsDataSourceUri()
            uri.setParam("type", "xyz")
            uri.setParam("url", OSM)
            uri.setParam("zmin", "0")
            uri.setParam("zmax", "19")
            self._basemap = QgsRasterLayer(bytes(uri.encodedUri()).decode(), "OpenStreetMap", "wms")
        return self._basemap

    def _atur_lapisan(self, *_):
        osm = self.cb_osm.isChecked()
        self.lbl_osm.setVisible(osm)
        lapisan = [x for x in (self._wms, self._peta_dasar() if osm else None) if x is not None and x.isValid()]
        self.kanvas.setLayers(lapisan)
        self.kanvas.refresh()

    def _ke_cakupan(self):
        d = self._data.get(self._pk) if self._pk else None
        c = gs.cakupan_dataset(d) if d else None
        tujuan = QgsCoordinateReferenceSystem(WEB_MERCATOR)
        try:
            if c is None and self._wms is not None and d is not None:
                kotak = QgsCoordinateTransform(self._wms.crs(), tujuan, QgsProject.instance()).transformBoundingBox(
                    self._wms.extent())
            else:
                x0, y0, x1, y1 = c or INDONESIA
                kotak = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"), tujuan, QgsProject.instance()) \
                    .transformBoundingBox(QgsRectangle(max(x0, -180), max(y0, -85), min(x1, 180), min(y1, 85)))
        except Exception:  # QgsCsException: cakupan tak bisa ditransformasi → tampilan Indonesia
            kotak = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"), tujuan, QgsProject.instance()) \
                .transformBoundingBox(QgsRectangle(*INDONESIA))
        if kotak.width() < 200 or kotak.height() < 200:  # data titik / sangat kecil
            kotak = QgsRectangle(kotak.center().x() - 500, kotak.center().y() - 500,
                                 kotak.center().x() + 500, kotak.center().y() + 500)
        kotak.scale(1.08)
        self.kanvas.setExtent(kotak)
        self.kanvas.refresh()

    # ------------------------------------------------------------------ aksi
    def ambil(self):
        """Isi formulir dengan metadata dataset terpilih (record ISO dari CSW GeoNode) dan tautkan editor."""
        d = self._data.get(self._pk) if self._pk else None
        if d is None or self._klien is None:
            return
        k = self._klien
        try:
            if not d.get("uuid"):
                d = k.dataset(d["pk"])
            ed = self.editor
            if ed.root is not None:
                ed.apply_values()
                if gs.judul_formulir(ed.root) and QMessageBox.question(
                        self, JUDUL, "Isian formulir saat ini akan diganti dengan metadata dataset «%s» dari "
                        "GeoNode. Simpan dulu bila masih diperlukan.\n\nLanjutkan?" % d.get("title")
                ) != QMessageBox.StandardButton.Yes:
                    return
            self._catat("Mengambil record ISO «%s» dari CSW GeoNode …" % d.get("title"))
            md = gs.ambil_md_metadata(k.csw_record(d["uuid"]))
            if md is None:
                raise GeoNodeError("Record ISO dataset ini tidak ditemukan di CSW GeoNode.")
            from . import dialog as editor_mod
            root = gmd_importer.convert_gmd_to_iso3(md, editor_mod.TEMPLATE, bersih=True)  # hanya data GeoNode
            ed.muat_dari_geonode(root, {"url": k.base, "pk": d["pk"], "uuid": d["uuid"], "title": d.get("title")})
            QMessageBox.information(self, JUDUL, "Metadata «%s» dimuat ke formulir dan tertaut ke dataset ini.\n\n"
                                    "Sunting isiannya, lalu klik «☁ Kirim ke GeoNode...» di bawah formulir untuk "
                                    "memperbarui metadatanya di GeoNode." % d.get("title"))
            self.accept()
        except GeoNodeError as e:
            self._catat("Gagal mengambil: %s" % e)
            QMessageBox.warning(self, JUDUL, "Gagal mengambil metadata dari GeoNode:\n%s" % e)
        except Exception as e:  # galat tak terduga: tampilkan, jangan tutup QGIS
            self._catat("Galat: %s" % e)
            QMessageBox.warning(self, JUDUL, "Galat tak terduga:\n%s" % e)

    def done(self, hasil):
        self._hidup = False
        self._tunda.stop()
        self._batalkan_unduhan()
        QgsSettings().setValue(KUNCI + "katalog_osm", self.cb_osm.isChecked())
        self.kanvas.stopRendering()
        self.kanvas.setLayers([])
        super().done(hasil)
