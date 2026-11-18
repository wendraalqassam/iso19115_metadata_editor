"""Dialog "Kirim ke GeoNode": login dengan akun GeoNode sendiri, pilih dataset, unggah metadata ISO 19139.
Mengambil metadata dataset GeoNode ke formulir ada di katalog "Ambil dari GeoNode..." (geonode_katalog.py).

Mode kirim: bawaan TANPA preserve — GeoNode memperbarui kolom yang dikenalnya dan membuat ulang record CSW dari
templatenya. Preserve (CSW menyajikan XML GeoMDB utuh) hanya dipakai pada server yang ditandai "sudah ditambal":
GeoNode 4.2.5 s.d. master merusak record ber-preserve (gs.BUG_PRESERVE) sampai ditambal dengan alat
gs.URL_ALAT_TAMBAL. Deteksi server belum ditambal: (1) record CSW rusak pada dataset ber-preserve saat daftar
dimuat; (2) gejala bug saat mengirim dengan preserve → preserve dimatikan, dikirim ulang, server ditandai "belum".

Pengaman salah-tujuan (GeoNode tidak punya "undo"):
  - formulir hasil "Ambil dari GeoNode" dikunci ke dataset asalnya; ganti tujuan harus disengaja;
  - pengiriman ke dataset yang bukan asal formulir wajib konfirmasi dengan mengetik nama layer tujuan;
  - sebelum menimpa, record CSW lama disimpan sebagai cadangan dan bisa dipulihkan ("Pulihkan dari cadangan…");
  - cakupan & sistem referensi formulir dibandingkan dengan GeoNode saat ini; bila beda, pengguna memilih."""
import datetime
import html
import json
import os

from urllib.parse import urlsplit

from qgis.core import QgsApplication, QgsSettings
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPlainTextEdit,
    QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from . import gmd_importer, kesesuaian, layout
from . import geonode_sync as gs
from .geonode_daftar import DaftarDataset
from .geonode_klien import GeoNodeDiblokir, GeoNodeError
from .geonode_panel import KUNCI, PanelKoneksi, satu_aksi

JUDUL = "Kirim Metadata ke GeoNode"
UKURAN_HALAMAN = 24
YA = QMessageBox.StandardButton.Yes


def folder_cadangan():
    """<profil QGIS>/geomdb_cadangan/<host>/<pk>-<layer>/<waktu>.xml (+ .json keterangan)."""
    return os.path.join(QgsApplication.qgisSettingsDirPath(), "geomdb_cadangan")


def _kunci_tambal(base):
    return KUNCI + "tambal/" + (urlsplit(gs.url_dasar(base)).hostname or "")


def status_tambal(base):
    """'sudah' | 'belum' | '' (belum diketahui) — status tambal bug preserve server GeoNode, diingat per host."""
    return QgsSettings().value(_kunci_tambal(base), "", type=str) if gs.url_dasar(base) else ""


def tandai_tambal(base, status):
    if gs.url_dasar(base):
        QgsSettings().setValue(_kunci_tambal(base), status)


TAUTAN_TAMBAL = "<a href='%s'>alat tambal GeoNode</a>" % gs.URL_ALAT_TAMBAL


def _angka(v):
    return ("%.10f" % v).rstrip("0").rstrip(".")


class DialogGeoNode(QDialog):
    def __init__(self, editor, parent=None):
        super().__init__(parent or editor)
        self.editor = editor
        self.setWindowTitle(JUDUL)
        self.resize(1000, 840)
        tautan = getattr(editor, "geonode_tautan", None)
        self._kunci = bool(tautan)  # tujuan dikunci ke dataset asal formulir (lihat _kunci_aktif)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.panel = PanelKoneksi(JUDUL, self._catat, self)
        self.panel.tersambung.connect(lambda *_: self.muat_dataset())
        self.panel.autentikasi_berganti.connect(self._kosongkan)
        self.e_url = self.panel.e_url
        self.e_url.editingFinished.connect(self._atur_kunci)

        self.lbl_tautan = QLabel("")
        self.lbl_tautan.setWordWrap(True)
        self.lbl_tautan.setStyleSheet("color: #475569;")
        self.b_ganti = QPushButton("Ganti dataset tujuan…")
        self.b_ganti.setToolTip("Buka pilihan dataset lain. Mengirim ke dataset lain mengganti seluruh metadatanya.")
        self.b_ganti.clicked.connect(self.ganti_tujuan)

        # Klik ganda sengaja tidak mengirim: memperbarui metadata hanya lewat tombol «Perbarui di GeoNode».
        self.katalog = DaftarDataset(UKURAN_HALAMAN)
        self.katalog.muat.connect(lambda h: self.muat_dataset(h))
        self.katalog.dipilih.connect(self._pilihan_berubah)

        self.cb_tambal = QCheckBox("Server GeoNode ini sudah ditambal — pakai preserve (CSW menyajikan metadata "
                                   "GeoMDB lengkap)")
        self.cb_tambal.setToolTip("Centang hanya setelah admin server menjalankan alat tambal GeoNode. Bila ternyata "
                                  "belum, plugin otomatis kembali mengirim tanpa preserve dan memulihkan record CSW.")
        self.cb_tambal.toggled.connect(self._tambal_dipilih)
        self.lbl_preserve = QLabel("")
        self.lbl_preserve.setWordWrap(True)
        self.lbl_preserve.setStyleSheet("color: #475569;")
        self.lbl_preserve.setOpenExternalLinks(True)
        self._rusak = []  # dataset ber-preserve yang record CSW-nya rusak (deteksi server belum ditambal)
        self._diperiksa = set()  # host yang sudah diperiksa pada sesi dialog ini
        self.panel.versi_berubah.connect(self._atur_versi)
        self.e_url.editingFinished.connect(self._muat_status_tambal)

        b_pulihkan = QPushButton("Pulihkan dari cadangan…")
        b_pulihkan.setToolTip("Kembalikan metadata dataset GeoNode ke keadaan sebelum ditimpa (cadangan otomatis plugin).")
        b_pulihkan.clicked.connect(lambda *_: self.pulihkan())
        self.b_kirim = QPushButton("⬆ Perbarui di GeoNode")
        self.b_kirim.setToolTip("Ganti metadata dataset terpilih di GeoNode dengan isian formulir GeoMDB saat ini.")
        self.b_kirim.setEnabled(False)
        self.b_kirim.clicked.connect(lambda *_: self.kirim())
        b_tutup = QPushButton("Tutup")
        b_tutup.clicked.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(self.panel)
        baris_tautan = QHBoxLayout()
        baris_tautan.addWidget(self.lbl_tautan, 1)
        baris_tautan.addWidget(self.b_ganti)
        lay.addLayout(baris_tautan)
        bawah = QWidget()
        vb = QVBoxLayout(bawah)
        vb.setContentsMargins(0, 0, 0, 0)
        vb.addWidget(self.cb_tambal)
        vb.addWidget(self.lbl_preserve)
        vb.addWidget(QLabel("Log:"))
        vb.addWidget(self.log, 1)
        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.katalog)
        split.addWidget(bawah)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)
        split.setSizes([480, 220])
        lay.addWidget(split, 1)
        tombol = QHBoxLayout()
        tombol.addWidget(b_pulihkan)
        tombol.addStretch(1)
        tombol.addWidget(self.b_kirim)
        tombol.addWidget(b_tutup)
        lay.addLayout(tombol)
        for b in self.findChildren(QPushButton):  # Enter di kotak cari tidak boleh menekan tombol mana pun
            b.setAutoDefault(False)
            b.setDefault(False)

        # Formulir yang diambil dari GeoNode: langsung masuk & pilih dataset asalnya
        if tautan:
            self.e_url.setText(tautan["url"])
            self._catat("Formulir tertaut ke dataset «%s» (#%s)." % (tautan["title"], tautan["pk"]))
        self._muat_status_tambal()
        self._atur_kunci()
        if tautan:
            self.panel.masuk()

    def done(self, hasil):
        self.katalog.tutup()
        super().done(hasil)

    # ------------------------------------------------------------------ bantu
    def _catat(self, teks):
        self.log.appendPlainText(teks)
        QApplication.processEvents()

    def _kosongkan(self):
        """Autentikasi berganti: buang daftar & hasil deteksi milik login sebelumnya (lihat PanelKoneksi)."""
        if getattr(self, "_sibuk", False):
            return
        self.katalog.kosongkan()
        self._rusak, self._diperiksa = [], set()
        self._atur_versi()
        self._catat("Autentikasi diganti — daftar dataset dikosongkan.")

    def _klien(self):
        return self.panel.klien()

    def _tautan(self):
        return getattr(self.editor, "geonode_tautan", None)

    def _profil(self):
        return gs.VERSI.get(self.panel.versi())

    def _kunci_aktif(self):
        t = self._tautan()
        return bool(self._kunci and t and gs.url_dasar(t["url"]) == gs.url_dasar(self.e_url.text()))

    def _atur_kunci(self):
        t, aktif = self._tautan(), self._kunci_aktif()
        self.katalog.atur_cari(not aktif)
        self.b_ganti.setVisible(aktif)
        if aktif:
            teks = ("🔒 Tujuan dikunci ke dataset asal formulir: <b>%s</b> (#%s)." % (
                html.escape(str(t["title"])), html.escape(str(t["pk"]))))
        elif t:
            teks = ("Formulir diambil dari <b>%s</b> (#%s), tetapi tujuan dibuka: mengirim ke dataset lain wajib "
                    "konfirmasi dengan mengetik nama layer tujuan." % (html.escape(str(t["title"])),
                                                                       html.escape(str(t["pk"]))))
        else:
            teks = ("Formulir ini tidak diambil dari GeoNode — pengiriman wajib konfirmasi dengan mengetik nama layer "
                    "tujuan. Untuk menyunting metadata dataset yang sudah ada, ambil dulu lewat «Ambil dari GeoNode...».")
        self.lbl_tautan.setText(teks)

    def _pakai_preserve(self):
        p = self._profil()
        return bool(p and p["preserve_api"] and self.cb_tambal.isChecked())

    def _muat_status_tambal(self):
        self.cb_tambal.blockSignals(True)
        self.cb_tambal.setChecked(status_tambal(self.e_url.text()) == "sudah")
        self.cb_tambal.blockSignals(False)
        self._atur_versi()

    def _tambal_dipilih(self, centang):
        tandai_tambal(self.e_url.text(), "sudah" if centang else "belum")
        self._atur_versi()

    def _atur_versi(self):
        """Keterangan mode kirim & ketersediaan Perbarui mengikuti generasi GeoNode (gs.VERSI) dan status tambal."""
        p = self._profil()
        self.cb_tambal.setVisible(bool(p and p["unggah"] and p["preserve_api"]))
        biasa = ("<b>Mode biasa (tanpa preserve):</b> GeoNode memperbarui kolom yang dikenalnya (judul, abstrak, kata "
                 "kunci, …) dan membuat ulang record CSW dari templatenya; metadata lengkap tetap di berkas GeoMDB.")
        saran = (" Agar CSW GeoNode menyajikan metadata GeoMDB lengkap, admin server perlu menjalankan %s." % TAUTAN_TAMBAL)
        if p is None:
            teks = ("Versi GeoNode belum diketahui — klik «Masuk & muat dataset» untuk mendeteksinya, "
                    "atau pilih versinya secara manual.")
        elif not p["unggah"]:
            teks = ("<b>%s belum menyediakan API unggah metadata XML</b> (tersedia mulai GeoNode 4.2.3). Dari "
                    "plugin hanya bisa mengambil metadata; perbarui lewat form GeoNode." % p["label"])
        elif not p["preserve_api"]:
            teks = (biasa + " %s tidak membuka pengaturan preserve lewat API: bila admin mencentang «Metadata "
                    "uploaded preserve» pada dataset, server WAJIB sudah ditambal (%s), kalau tidak record CSW-nya "
                    "rusak." % (p["label"], TAUTAN_TAMBAL))
        elif self._pakai_preserve():
            teks = ("<b>Mode preserve:</b> CSW GeoNode menyajikan XML GeoMDB lengkap apa adanya; tautan WMS/WFS/unduhan "
                    "& thumbnail GeoNode disisipkan otomatis. Bila ternyata server belum ditambal, plugin otomatis "
                    "kembali ke mode biasa dan memulihkan record CSW-nya.")
        else:
            teks = biasa + saran
        if self._rusak:
            teks += ("<br><span style='color:#b45309'>⚠ <b>Server ini belum ditambal:</b> record CSW dataset ber-preserve "
                     "rusak (%s). Perbaiki lewat «Pulihkan dari cadangan…», lalu minta admin menjalankan %s.</span>"
                     % (html.escape(", ".join(self._rusak[:3])), TAUTAN_TAMBAL))
        self.lbl_preserve.setText(teks)
        self._pilihan_berubah()

    def _periksa_tambal(self, k):
        """Deteksi server belum ditambal TANPA mengubah apa pun: record CSW dataset ber-preserve yang rusak (bug
        preserve GeoNode) adalah buktinya. Sekali per host per sesi dialog; paling banyak 3 dataset diperiksa."""
        host = urlsplit(k.base).hostname
        if host in self._diperiksa or not (self._profil() or {}).get("preserve_api"):
            return
        self._diperiksa.add(host)
        try:
            data = k.datasets(ukuran=50)[0]
        except GeoNodeError:
            return
        rusak = []
        for d in gs.dataset_preserve(data)[:3]:
            try:  # bukti = galat server (HTTP 500 / ExceptionReport); "tak ditemukan" bisa karena record tak terlihat
                k.csw_record(d["uuid"])  # (mis. dataset tidak publik + login username/password)
            except GeoNodeDiblokir:
                return  # CSW diblokir proteksi bot di depan GeoNode: bukan bukti, tidak bisa diperiksa
            except GeoNodeError:
                rusak.append(d.get("title") or str(d.get("pk")))
        if rusak:
            self._rusak = rusak
            tandai_tambal(k.base, "belum")
            self._muat_status_tambal()
            self._catat("Server belum ditambal: record CSW dataset ber-preserve rusak (%s). Alat tambal: %s"
                        % (", ".join(rusak), gs.URL_ALAT_TAMBAL))

    def _pilihan_berubah(self, *_):
        p, d = self._profil(), self.katalog.terpilih()
        self.b_kirim.setEnabled(bool(d and gs.boleh_ubah(d) and p and p["unggah"]))

    # ------------------------------------------------------------------ daftar dataset
    def masuk(self):
        self.panel.masuk()

    def ganti_tujuan(self):
        if QMessageBox.question(
                self, JUDUL, "Buka pilihan dataset tujuan lain?\n\nMengirim formulir ini ke dataset lain akan MENGGANTI "
                "seluruh metadata dataset itu. Konfirmasi dengan mengetik nama layer tujuan tetap diminta.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != YA:
            return
        self._kunci = False
        self._atur_kunci()
        self.muat_dataset()

    @satu_aksi
    def muat_dataset(self, halaman=1):
        self._atur_kunci()
        try:
            k = self._klien()
            if self._kunci_aktif():
                data, total, halaman = [k.dataset(self._tautan()["pk"])], 1, 1
            else:
                data, total = k.datasets(cari=self.katalog.cari(), halaman=max(1, halaman), ukuran=UKURAN_HALAMAN)
        except GeoNodeError as e:
            self._catat("Gagal memuat dataset: %s" % e)
            return
        self.katalog.isi(k, data, total, halaman, utama=gs.pk_tautan(self._tautan(), k.base))
        self._catat("%d dataset dimuat (dari %d), %d boleh diubah akun ini." % (
            len(data), total, sum(gs.boleh_ubah(d) for d in data)))
        self._periksa_tambal(k)

    # ------------------------------------------------------------------ pengaman
    def _konfirmasi_nama(self, ds):
        """Pengiriman ke dataset yang bukan asal formulir: ketik nama layer tujuan (bukan sekadar Yes)."""
        t = self._tautan()
        asal = (("Formulir ini diambil dari dataset «%s», BUKAN dataset tujuan." % t["title"]) if t
                else "Formulir ini tidak diambil dari GeoNode.")
        teks, ok = QInputDialog.getText(
            self, JUDUL, "%s\nMetadata dataset «%s» akan DIGANTI SELURUHNYA dengan isian formulir ini.\n\n"
            "Untuk konfirmasi, ketik nama layer dataset tujuan:\n%s" % (asal, ds.get("title"), gs.nama_layer(ds)))
        if not ok:
            return False
        if not gs.nama_cocok(teks, ds):
            QMessageBox.warning(self, JUDUL, "Nama layer yang diketik tidak cocok — pengiriman dibatalkan.")
            return False
        return True

    def _tanya_cakupan(self, beda):
        """'formulir' | 'geonode' | None (batal) — cakupan/CRS formulir berbeda dengan GeoNode saat ini."""
        mb = QMessageBox(QMessageBox.Icon.Question, JUDUL,
                         "Cakupan / sistem referensi di formulir berbeda dengan GeoNode saat ini (mis. data sudah "
                         "diganti di GeoNode sejak metadatanya diambil):\n\n%s\n\nMana yang dikirim?"
                         % "\n".join("• " + b for b in beda), parent=self)
        b_form = mb.addButton("Kirim isian formulir", QMessageBox.ButtonRole.AcceptRole)
        b_gn = mb.addButton("Pakai nilai GeoNode", QMessageBox.ButtonRole.ActionRole)
        mb.addButton("Batal", QMessageBox.ButtonRole.RejectRole)
        mb.setDefaultButton(b_form)
        mb.exec()
        return {b_form: "formulir", b_gn: "geonode"}.get(mb.clickedButton())

    def _terapkan_cakupan_geonode(self, ds):
        """Salin cakupan & EPSG terkini GeoNode ke formulir (bukan hanya ke XML), agar keduanya tetap sama."""
        secs = {s.id: s for s in layout.build(self.editor.root)[0]}
        f = {n.key: n for sid in (2, 4) if sid in secs for n in layout.iter_fields(secs[sid].nodes)}
        c = gs.cakupan_dataset(ds)
        if c:
            for key, v in zip(("westBound", "southBound", "eastBound", "northBound"), c):
                if key in f:
                    f[key].field.set(_angka(v))
        kode = gs.kode_epsg(ds.get("srid"))
        if kode and "referenceSystemCode" in f:
            f["referenceSystemCode"].field.set(kode)
            if "referenceSystemCodeSpace" in f:
                f["referenceSystemCodeSpace"].field.set("EPSG")
        self.editor.rebuild()

    def _cadangkan(self, k, ds, versi):
        """Simpan record CSW dataset (metadata sebelum ditimpa) + keterangan JSON; kembalikan jalur XML."""
        waktu = datetime.datetime.now(datetime.timezone.utc)
        md = gs.ambil_md_metadata(k.csw_record(ds["uuid"]))
        if md is None:
            raise GeoNodeError("record CSW dataset ini tidak ditemukan")
        rel, dasar = gs.lokasi_cadangan(k.base, ds, waktu)
        folder = os.path.join(folder_cadangan(), rel)
        os.makedirs(folder, exist_ok=True)
        jalur = os.path.join(folder, dasar + ".xml")
        with open(jalur, "wb") as fh:
            fh.write(gs.xml_bytes(md))
        info = dict(gs.info_cadangan(k.base, ds, versi, waktu), xml=dasar + ".xml")
        with open(os.path.join(folder, dasar + ".json"), "w", encoding="utf-8") as fh:
            json.dump(info, fh, ensure_ascii=False, indent=1)
        return jalur

    # ------------------------------------------------------------------ aksi
    def _siapkan(self, ds, preserve=False):
        """Tautan layanan & thumbnail hanya disisipkan untuk preserve; tanpa preserve GeoNode menulisnya sendiri."""
        catatan, tidak_standar = [], []
        g = gs.siapkan_xml(self.editor.root, ds, sisip_tautan=preserve, catatan=catatan, tidak_standar=tidak_standar)
        return g, catatan, tidak_standar

    def _unggah(self, k, pk, g, ds):
        """Unggah XML & tunggu GeoNode memprosesnya; (status, pesan)."""
        exec_id = k.unggah_metadata(pk, gs.xml_bytes(g), ds.get("alternate") or "")
        self._catat("    diproses GeoNode (execution %s) …" % exec_id)
        st = k.tunggu_eksekusi(exec_id, lapor=lambda s, langkah: self._catat("    status: %s %s" % (s, langkah)))
        return gs.ringkas_status(st)

    def _csw_terbaca(self, k, ds):
        """True/False; None bila CSW tak bisa diperiksa (diblokir proteksi bot di depan GeoNode) — bukan gejala bug."""
        try:
            return gs.ambil_md_metadata(k.csw_record(ds["uuid"])) is not None
        except GeoNodeDiblokir:
            return None
        except GeoNodeError:
            return False

    @satu_aksi
    def kirim(self):
        pk = self.katalog.pk()
        if pk is None:
            return
        versi = self.panel.versi()
        profil = gs.VERSI.get(versi)
        try:
            if profil is None:
                raise GeoNodeError("Versi GeoNode belum diketahui — klik «Masuk & muat dataset» atau pilih versinya.")
            if not profil["unggah"]:
                raise GeoNodeError("%s belum menyediakan API unggah metadata XML (mulai GeoNode 4.2.3)." % profil["label"])
            self.editor.apply_values()
            if not gs.judul_formulir(self.editor.root):
                raise GeoNodeError("Judul Data di formulir kosong — metadata GeoNode akan tertimpa isian kosong. "
                                   "Ambil metadatanya dulu lewat «Ambil dari GeoNode...» di bagian atas editor, "
                                   "atau isi formulirnya.")
            k = self._klien()
            ds = k.dataset(pk)
            if not gs.boleh_ubah(ds):
                raise GeoNodeError("Akun Anda tidak punya izin mengubah metadata dataset ini.")
            if not gs.tautan_cocok(self._tautan(), k.base, pk) and not self._konfirmasi_nama(ds):
                return
            # Login username/password: CSW GeoNode menganggapnya anonim → record dataset tidak publik tak terlihat
            csw_bisa = not (self.panel.basic() and not k.terlihat_publik(pk))
            alasan_csw = "" if csw_bisa else "dataset belum dipublikasikan; CSW GeoNode tidak mengenali login username/password"
            preserve = self._pakai_preserve()
            g, catatan, tidak_standar = self._siapkan(ds, preserve)
            beda = gs.bandingkan_cakupan(g, ds)
            if beda:
                pilihan = self._tanya_cakupan(beda)
                if pilihan is None:
                    return
                if pilihan == "geonode":
                    self._terapkan_cakupan_geonode(ds)
                    g, catatan, tidak_standar = self._siapkan(ds, preserve)
                self._catat("Cakupan/CRS berbeda dengan GeoNode — dikirim nilai %s." % pilihan)
            if QMessageBox.question(
                    self, JUDUL,
                    "Metadata dataset «%s» di %s (%s) akan diganti dengan isian GeoMDB saat ini.\n%s\n"
                    "Metadata lama disimpan dulu sebagai cadangan.\n\nLanjutkan?" % (
                        ds.get("title"), k.base, profil["label"],
                        "Mode preserve: CSW GeoNode menyajikan XML GeoMDB apa adanya." if preserve else
                        "Mode biasa: GeoNode memperbarui kolom yang dikenalnya & membuat ulang record CSW dari "
                        "templatenya.")
            ) != YA:
                return
            self.b_kirim.setEnabled(False)
            judul = gs.judul_xml(g)
            self._catat("1/5 XML ISO 19139 disiapkan (fileIdentifier = %s)." % ds.get("uuid"))
            try:
                if not csw_bisa:
                    raise GeoNodeError(gs.SARAN_BASIC_PRIVAT)
                cadangan = self._cadangkan(k, ds, versi)
                self._catat("2/5 Cadangan metadata lama: %s" % cadangan)
            except (GeoNodeError, OSError) as e:
                if QMessageBox.warning(
                        self, JUDUL, "Cadangan metadata lama gagal dibuat:\n%s\n\nLanjut TANPA cadangan?" % e,
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No) != YA:
                    return
                cadangan = None
                self._catat("2/5 TANPA cadangan (%s)." % e)
            if not profil["preserve_api"]:
                self._catat("3/5 %s: preserve tidak diatur plugin (hanya lewat Django admin)." % profil["label"])
            elif bool(ds.get("metadata_uploaded_preserve")) != preserve:
                k.set_preserve(pk, preserve)  # harus sebelum unggah (lihat geonode_sync)
                self._catat("3/5 preserve %s." % ("dinyalakan" if preserve else "dimatikan (mode biasa)"))
            else:
                self._catat("3/5 preserve %s." % ("sudah aktif" if preserve else "tidak dipakai (mode biasa)"))
            self._catat("4/5 XML diunggah …")
            status, pesan = self._unggah(k, pk, g, ds)
            pulih_otomatis = False
            if preserve and ((status != gs.SELESAI and gs.gejala_bug_preserve(pesan)) or
                             (status == gs.SELESAI and csw_bisa and self._csw_terbaca(k, ds) is False)):
                # Server ternyata BELUM ditambal: matikan preserve (GeoNode membuat ulang record dari template),
                # kirim ulang tanpa preserve, tandai server, tunjukkan alat tambal.
                self._catat("    Gejala bug preserve GeoNode — server belum ditambal. Dikirim ulang tanpa preserve.")
                tandai_tambal(k.base, "belum")
                self._muat_status_tambal()
                k.set_preserve(pk, False)
                preserve, pulih_otomatis = False, True
                g, catatan, tidak_standar = self._siapkan(ds, False)
                status, pesan = self._unggah(k, pk, g, ds)
            if status != gs.SELESAI:
                raise GeoNodeError("Pemrosesan GeoNode %s: %s" % (status or "tidak selesai", pesan or "-"))
            masalah_csw = []
            if csw_bisa:
                try:
                    masalah_csw = gs.periksa_record_csw(k.csw_record(ds["uuid"]), ds["uuid"], g, preserve=preserve)
                    if preserve and not masalah_csw:
                        tandai_tambal(k.base, "sudah")  # terbukti: XML GeoMDB tersaji utuh
                except GeoNodeDiblokir:
                    alasan_csw = "CSW diblokir proteksi bot di depan GeoNode"
            masalah_db = gs.periksa_dataset(k.dataset(pk), g)
            self._catat("5/5 CSW GeoNode %s\n    Isian GeoNode (%s) %s" % (
                "tidak diperiksa (%s)." % alasan_csw if alasan_csw else
                "sesuai." if not masalah_csw else "BELUM sesuai: " + " ".join(masalah_csw),
                gs.halaman_metadata(versi, ds),
                "sesuai." if not masalah_db else "BELUM sesuai: " + " ".join(masalah_db)))
            masalah = masalah_csw + masalah_db
            isi = kesesuaian.html([
                ("Pemeriksaan CSW GeoNode", masalah_csw),
                ("Pemeriksaan isian GeoNode (halaman metadata & API)", masalah_db),
                ("Tidak kompatibel ISO 19139 — tidak dikirim (tetap di berkas ISO 19115-3)", catatan),
                ("Nilai daftar kode di luar ISO 19139 — katalog lain bisa tidak mengenalinya", tidak_standar),
            ], html.escape)
            mode = ("<br><br><b>Mode preserve:</b> CSW GeoNode menyajikan XML GeoMDB lengkap." if preserve else
                    "<br><br><b>Mode biasa:</b> CSW GeoNode dibuat ulang dari templatenya (hanya kolom yang dikenal "
                    "GeoNode). Untuk CSW lengkap, admin server perlu menjalankan alat tambal GeoNode:<br>"
                    "<a href='%s'>%s</a>" % (gs.URL_ALAT_TAMBAL, gs.URL_ALAT_TAMBAL))
            if pulih_otomatis:
                mode = ("<br><br><b>Server GeoNode ini belum ditambal</b> — preserve memicu bug GeoNode, jadi plugin "
                        "otomatis mengirim ulang tanpa preserve dan record CSW-nya sehat." + mode)
            (QMessageBox.information if not masalah and not pulih_otomatis else QMessageBox.warning)(
                self, JUDUL, "Metadata «%s» terkirim ke GeoNode dan %s.%s<br><br>%s%s" % (
                    html.escape(judul), ("terverifikasi di isian GeoNode (CSW tidak diperiksa: %s)" % html.escape(
                        alasan_csw) if alasan_csw else "terverifikasi di CSW & isian GeoNode") if not masalah
                    else "<b>belum terbukti diterapkan — periksa catatan di bawah</b>", mode, isi,
                    ("<br>Metadata sebelumnya dicadangkan; bisa dikembalikan lewat «Pulihkan dari cadangan…»:<br>"
                     "<code>%s</code>" % html.escape(cadangan)) if cadangan else ""))
        except GeoNodeError as e:
            self._catat("Gagal: %s" % e)
            QMessageBox.warning(self, JUDUL, "Gagal mengirim ke GeoNode:\n%s" % e)
        except Exception as e:  # galat tak terduga: tampilkan, jangan tutup QGIS
            self._catat("Galat: %s" % e)
            QMessageBox.warning(self, JUDUL, "Galat tak terduga:\n%s" % e)
        finally:
            self._pilihan_berubah()

    @satu_aksi
    def pulihkan(self):
        """Unggah kembali cadangan ke dataset ASALNYA (uuid dicocokkan) TANPA preserve — sekaligus memperbaiki
        record CSW yang rusak oleh bug preserve GeoNode (gs.BUG_PRESERVE) — dengan tanggal dataset semula."""
        os.makedirs(folder_cadangan(), exist_ok=True)
        jalur, _ = QFileDialog.getOpenFileName(self, "Pulihkan dari cadangan", folder_cadangan(),
                                               "Keterangan cadangan GeoMDB (*.json)")
        if not jalur:
            return
        try:
            with open(jalur, encoding="utf-8") as fh:
                info = json.load(fh)
            jalur_xml = os.path.join(os.path.dirname(jalur), info.get("xml") or
                                     os.path.splitext(os.path.basename(jalur))[0] + ".xml")
            with open(jalur_xml, "rb") as fh:
                md = gs.ambil_md_metadata(fh.read())
            if md is None:
                raise GeoNodeError("Berkas XML cadangan tidak berisi gmd:MD_Metadata.")
            # Teks pengisi template GeoNode ("None", "No abstract provided") jangan sampai jadi isian sungguhan
            gmd_importer.buang_pengisi_geonode(md)
            profil = self._profil()
            if profil is None or not profil["unggah"]:
                raise GeoNodeError("Versi GeoNode ini tidak mendukung unggah metadata dari plugin.")
            k = self._klien()
            ds = k.dataset(info.get("pk"))
            masalah = gs.cek_cadangan(info, k.base, ds)
            if masalah:
                raise GeoNodeError(" ".join(masalah))
            if not gs.boleh_ubah(ds):
                raise GeoNodeError("Akun Anda tidak punya izin mengubah metadata dataset ini.")
            # Tanggal dataset semula: GeoNode mengisi `date` dari dateStamp. Cadangan lama belum mencatat `date`;
            # pada record buatan GeoNode tanggal sitasi = tanggal dataset.
            tanggal = gs.baca_waktu(info.get("date")) or gs.baca_waktu(gs.tanggal_kutipan(md))
            if tanggal:
                gs.atur_datestamp(md, tanggal)
            if QMessageBox.question(
                    self, JUDUL, "Pulihkan metadata dataset «%s» (#%s) ke keadaan cadangan %s?\n"
                    "Metadata saat ini akan diganti; preserve dimatikan%s." % (
                        ds.get("title"), ds.get("pk"), info.get("waktu"),
                        ", tanggal dataset dikembalikan ke %s" % tanggal.date() if tanggal else ""),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No) != YA:
                return
            if ds.get("metadata_uploaded_preserve"):
                if not profil["preserve_api"]:
                    raise GeoNodeError("Preserve dataset ini masih aktif dan %s tidak mengizinkan plugin mematikannya. "
                                       "Minta admin menghapus centang «Metadata uploaded preserve» (Django admin → "
                                       "Datasets), lalu ulangi." % profil["label"])
                k.set_preserve(ds["pk"], False)  # sebelum unggah — GeoNode lalu membuat ulang record CSW dari template
                self._catat("Pulihkan: preserve dimatikan. %s" % gs.BUG_PRESERVE)
            exec_id = k.unggah_metadata(ds["pk"], gs.xml_bytes(md), ds.get("alternate") or "")
            self._catat("Pulihkan: cadangan %s diunggah (execution %s) …" % (os.path.basename(jalur_xml), exec_id))
            status, pesan = gs.ringkas_status(k.tunggu_eksekusi(exec_id))
            if status != gs.SELESAI:
                raise GeoNodeError("Pemrosesan GeoNode %s: %s" % (status or "tidak selesai", pesan or "-"))
            if self.panel.basic() and not k.terlihat_publik(ds["pk"]):
                sehat, ket = True, "Record CSW tidak diperiksa (dataset tidak publik + login username/password)."
            else:
                try:  # record CSW harus kembali terbaca
                    sehat = gs.ambil_md_metadata(k.csw_record(ds["uuid"])) is not None
                    ket = "Record CSW GeoNode terbaca kembali." if sehat else "Record CSW GeoNode belum terbaca."
                except GeoNodeError as e:
                    sehat, ket = False, "Record CSW GeoNode belum terbaca:\n%s" % e
            self._catat("Pulihkan selesai — %s" % ket.replace("\n", " "))
            (QMessageBox.information if sehat else QMessageBox.warning)(
                self, JUDUL, "Metadata dataset «%s» dipulihkan dari cadangan %s.\n%s" % (
                    ds.get("title"), info.get("waktu"), ket))
        except (GeoNodeError, OSError, ValueError, KeyError) as e:
            self._catat("Gagal memulihkan: %s" % e)
            QMessageBox.warning(self, JUDUL, "Gagal memulihkan dari cadangan:\n%s" % e)
