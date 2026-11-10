"""Dialog "Ambil dari GeoNode": katalog dataset GeoNode (mode kartu / daftar) dengan pratinjau peta dari
layanan WMS dataset, lalu muat metadata dataset terpilih (record ISO dari CSW GeoNode) ke formulir.
Pembaruan ke GeoNode tetap lewat tombol "Kirim ke GeoNode" di bawah editor (geonode_dialog.py)."""
import html

from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsDataSourceUri, QgsProject, QgsRasterLayer, QgsRectangle,
    QgsSettings,
)
from qgis.gui import QgsMapCanvas, QgsMapToolPan
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QApplication, QCheckBox, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSplitter, QTextBrowser,
    QToolButton, QVBoxLayout, QWidget,
)

from . import gmd_importer
from . import geonode_sync as gs
from .geonode_daftar import DaftarDataset, potong as _potong
from .geonode_klien import GeoNodeError
from .geonode_panel import KUNCI, PanelKoneksi, satu_aksi

JUDUL = "Ambil Metadata dari GeoNode"
UKURAN_HALAMAN = 24
WEB_MERCATOR = "EPSG:3857"
OSM = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
INDONESIA = (94.0, -11.5, 141.5, 6.5)  # tampilan awal peta sebelum dataset dipilih


class DialogKatalogGeoNode(QDialog):
    def __init__(self, editor, parent=None):
        super().__init__(parent or editor)
        self.editor = editor
        self.setWindowTitle(JUDUL)
        self.resize(1180, 760)
        s = QgsSettings()
        self._klien = None
        self._pk = None
        self._wms = self._basemap = None
        self._sedang = False     # pratinjau WMS sedang dimuat (pembuatan layer WMS memblokir)
        self._hidup = True

        self.status = QLabel("")
        self.status.setWordWrap(True)  # pesan galat panjang tidak boleh melebarkan dialog
        self.panel = PanelKoneksi(JUDUL, self._catat, self)
        self.panel.tersambung.connect(lambda: self.muat(1))
        self.panel.autentikasi_berganti.connect(self._kosongkan)

        self.katalog = DaftarDataset(UKURAN_HALAMAN)
        self.katalog.muat.connect(lambda h: self.muat(h))
        self.katalog.dipilih.connect(self._pilih)
        self.katalog.diaktifkan.connect(lambda _pk: self.ambil())

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
        self.b_ambil.clicked.connect(lambda *_: self.ambil())
        b_tutup = QPushButton("Tutup")
        b_tutup.clicked.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(self.panel)
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
        split.addWidget(self.katalog)
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

    def _kosongkan(self):
        """Autentikasi berganti: buang daftar lama — dataset tidak publik & izin milik login sebelumnya tidak boleh
        tertinggal, juga bila login baru gagal. Daftar dimuat ulang oleh Masuk otomatis panel."""
        if getattr(self, "_sibuk", False):
            return  # aksi lain sedang berjalan; Masuk ulang memuat ulang daftar sesudahnya
        self._klien = None
        self.katalog.kosongkan()
        self._catat("Autentikasi diganti — daftar dataset dikosongkan.")

    # ------------------------------------------------------------------ katalog
    @satu_aksi
    def muat(self, halaman=1):
        try:
            k = self.panel.klien()
            data, total = k.datasets(cari=self.katalog.cari(), halaman=max(1, halaman), ukuran=UKURAN_HALAMAN)
        except GeoNodeError as e:
            self._catat("Gagal memuat katalog: %s" % e)
            return
        self._klien = k
        utama = gs.pk_tautan(getattr(self.editor, "geonode_tautan", None), k.base)
        self.katalog.isi(k, data, total, halaman, utama=utama)
        self._catat("%d dataset ditampilkan (dari %d), %d boleh diubah akun ini." % (
            len(data), total, sum(gs.boleh_ubah(d) for d in data)))

    def _pilih(self, pk):
        """Pilihan di daftar berganti (sinyal DaftarDataset.dipilih): rincian & pratinjau peta."""
        self._pk = pk
        d = self.katalog.dataset(pk)
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
        d = self.katalog.dataset(pk)
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
        d = self.katalog.dataset(self._pk)
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
    @satu_aksi
    def ambil(self):
        """Isi formulir dengan metadata dataset terpilih (record ISO dari CSW GeoNode) dan tautkan editor."""
        d = self.katalog.dataset(self._pk)
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
            if self.panel.basic() and not k.terlihat_publik(d["pk"]):
                raise GeoNodeError(gs.SARAN_BASIC_PRIVAT)
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
        self.katalog.tutup()
        QgsSettings().setValue(KUNCI + "katalog_osm", self.cb_osm.isChecked())
        self.kanvas.stopRendering()
        self.kanvas.setLayers([])
        super().done(hasil)
