"""Dialog "Kirim ke GeoNode": login dengan akun GeoNode sendiri, pilih dataset, unggah metadata ISO 19139.
Mengambil metadata dataset GeoNode ke formulir ada di katalog "Ambil dari GeoNode..." (geonode_katalog.py).

Preserve (metadata_uploaded_preserve) SELALU aktif, tanpa opsi: plugin dimaksudkan melengkapi metadata GeoNode,
jadi CSW harus menyajikan XML GeoMDB utuh. Tanpa preserve GeoNode membuat ulang record dari templatenya dan
semua isian yang tidak dipetakan ke basis datanya (kontak, riwayat, kualitas, dll.) hilang.

Pengaman salah-tujuan (GeoNode tidak punya "undo"):
  - formulir hasil "Ambil dari GeoNode" dikunci ke dataset asalnya; ganti tujuan harus disengaja;
  - pengiriman ke dataset yang bukan asal formulir wajib konfirmasi dengan mengetik nama layer tujuan;
  - sebelum menimpa, record CSW lama disimpan sebagai cadangan dan bisa dipulihkan ("Pulihkan dari cadangan…");
  - cakupan & sistem referensi formulir dibandingkan dengan GeoNode saat ini; bila beda, pengguna memilih."""
import datetime
import html
import json
import os

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QApplication, QDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from . import gmd_importer, kesesuaian, layout
from . import geonode_sync as gs
from .geonode_klien import GeoNodeError
from .geonode_panel import PanelKoneksi

JUDUL = "Kirim Metadata ke GeoNode"
PK, UBAH = Qt.ItemDataRole.UserRole, Qt.ItemDataRole.UserRole + 1
YA = QMessageBox.StandardButton.Yes


def folder_cadangan():
    """<profil QGIS>/geomdb_cadangan/<host>/<pk>-<layer>/<waktu>.xml (+ .json keterangan)."""
    return os.path.join(QgsApplication.qgisSettingsDirPath(), "geomdb_cadangan")


def _angka(v):
    return ("%.10f" % v).rstrip("0").rstrip(".")


class DialogGeoNode(QDialog):
    def __init__(self, editor, parent=None):
        super().__init__(parent or editor)
        self.editor = editor
        self.setWindowTitle(JUDUL)
        self.resize(760, 660)
        tautan = getattr(editor, "geonode_tautan", None)
        self._kunci = bool(tautan)  # tujuan dikunci ke dataset asal formulir (lihat _kunci_aktif)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.panel = PanelKoneksi(JUDUL, self._catat, self)
        self.panel.tersambung.connect(self.muat_dataset)
        self.e_url = self.panel.e_url
        self.e_url.editingFinished.connect(self._atur_kunci)

        self.lbl_tautan = QLabel("")
        self.lbl_tautan.setWordWrap(True)
        self.lbl_tautan.setStyleSheet("color: #475569;")
        self.b_ganti = QPushButton("Ganti dataset tujuan…")
        self.b_ganti.setToolTip("Buka pilihan dataset lain. Mengirim ke dataset lain mengganti seluruh metadatanya.")
        self.b_ganti.clicked.connect(self.ganti_tujuan)

        self.e_cari = QLineEdit()
        self.e_cari.setPlaceholderText("Cari dataset (Enter)…")
        self.e_cari.returnPressed.connect(self.muat_dataset)
        self.lst = QListWidget()
        self.lst.currentItemChanged.connect(self._pilihan_berubah)

        self.lbl_preserve = QLabel("")
        self.lbl_preserve.setWordWrap(True)
        self.lbl_preserve.setStyleSheet("color: #475569;")
        self.panel.versi_berubah.connect(self._atur_versi)

        b_pulihkan = QPushButton("Pulihkan dari cadangan…")
        b_pulihkan.setToolTip("Kembalikan metadata dataset GeoNode ke keadaan sebelum ditimpa (cadangan otomatis plugin).")
        b_pulihkan.clicked.connect(self.pulihkan)
        self.b_kirim = QPushButton("⬆ Perbarui di GeoNode")
        self.b_kirim.setToolTip("Ganti metadata dataset terpilih di GeoNode dengan isian formulir GeoMDB saat ini.")
        self.b_kirim.setEnabled(False)
        self.b_kirim.clicked.connect(self.kirim)
        b_tutup = QPushButton("Tutup")
        b_tutup.clicked.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(self.panel)
        baris_tautan = QHBoxLayout()
        baris_tautan.addWidget(self.lbl_tautan, 1)
        baris_tautan.addWidget(self.b_ganti)
        lay.addLayout(baris_tautan)
        lay.addWidget(self.e_cari)
        lay.addWidget(self.lst, 2)
        lay.addWidget(self.lbl_preserve)
        lay.addWidget(QLabel("Log:"))
        lay.addWidget(self.log, 1)
        tombol = QHBoxLayout()
        tombol.addWidget(b_pulihkan)
        tombol.addStretch(1)
        tombol.addWidget(self.b_kirim)
        tombol.addWidget(b_tutup)
        lay.addLayout(tombol)
        for b in self.findChildren(QPushButton):  # Enter di kotak cari tidak boleh menekan tombol mana pun
            b.setAutoDefault(False)
            b.setDefault(False)
        self._atur_versi()

        # Formulir yang diambil dari GeoNode: langsung masuk & pilih dataset asalnya
        if tautan:
            self.e_url.setText(tautan["url"])
            self._catat("Formulir tertaut ke dataset «%s» (#%s)." % (tautan["title"], tautan["pk"]))
        self._atur_kunci()
        if tautan:
            self.panel.masuk()

    # ------------------------------------------------------------------ bantu
    def _catat(self, teks):
        self.log.appendPlainText(teks)
        QApplication.processEvents()

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
        self.e_cari.setVisible(not aktif)
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

    def _atur_versi(self):
        """Keterangan & ketersediaan Perbarui mengikuti generasi GeoNode (lihat gs.VERSI)."""
        p = self._profil()
        if p is None:
            teks = ("Versi GeoNode belum diketahui — klik «Masuk & muat dataset» untuk mendeteksinya, "
                    "atau pilih versinya secara manual.")
        elif not p["unggah"]:
            teks = ("<b>%s belum menyediakan API unggah metadata XML</b> (tersedia mulai GeoNode 4.2.3). Dari "
                    "plugin hanya bisa mengambil metadata; perbarui lewat form GeoNode." % p["label"])
        elif not p["preserve_api"]:
            teks = ("%s tidak membuka pengaturan preserve lewat API. CSW menyajikan XML GeoMDB lengkap <b>hanya "
                    "bila admin GeoNode sudah mencentang «Metadata uploaded preserve»</b> untuk dataset ini "
                    "(Django admin → Datasets); tanpa itu CSW dibuat ulang dari template GeoNode. Catatan: dataset "
                    "ber-preserve tidak bisa disunting lewat form metadata GeoNode." % p["label"])
        else:
            teks = ("CSW GeoNode akan menyajikan XML GeoMDB lengkap apa adanya (preserve). Tautan WMS/WFS/unduhan "
                    "dan thumbnail GeoNode disisipkan otomatis; halaman GeoNode tetap menampilkan kolom yang "
                    "dikenalnya.")
        self.lbl_preserve.setText(teks)
        self._pilihan_berubah(self.lst.currentItem())

    def _pilihan_berubah(self, item, _sebelum=None):
        p = self._profil()
        self.b_kirim.setEnabled(bool(item and item.data(UBAH) and p and p["unggah"]))

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

    def muat_dataset(self):
        self._atur_kunci()
        try:
            k = self._klien()
            if self._kunci_aktif():
                data, total = [k.dataset(self._tautan()["pk"])], 1
            else:
                data, total = k.datasets(cari=self.e_cari.text().strip())
        except GeoNodeError as e:
            self._catat("Gagal memuat dataset: %s" % e)
            return
        self.lst.clear()
        bisa = 0
        for d in data:
            ubah = gs.boleh_ubah(d)
            bisa += ubah
            it = QListWidgetItem("%s%s   [%s]" % ("" if ubah else "🔒 ", d.get("title") or d.get("alternate"), d.get("alternate")))
            it.setData(PK, d.get("pk"))
            it.setData(UBAH, ubah)
            it.setToolTip("Boleh diubah oleh akun Anda." if ubah else
                          "Akun Anda tidak punya izin ubah metadata dataset ini (perms GeoNode).")
            if not ubah:
                it.setForeground(Qt.GlobalColor.gray)
            self.lst.addItem(it)
            if gs.tautan_cocok(self._tautan(), self.e_url.text(), d.get("pk")):
                self.lst.setCurrentItem(it)
        self._catat("%d dataset dimuat (dari %d), %d boleh diubah akun ini." % (len(data), total, bisa))

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
    def _siapkan(self, ds):
        catatan, tidak_standar = [], []
        g = gs.siapkan_xml(self.editor.root, ds, catatan=catatan, tidak_standar=tidak_standar)
        return g, catatan, tidak_standar

    def kirim(self):
        item = self.lst.currentItem()
        if item is None:
            return
        pk = item.data(PK)
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
            g, catatan, tidak_standar = self._siapkan(ds)
            beda = gs.bandingkan_cakupan(g, ds)
            if beda:
                pilihan = self._tanya_cakupan(beda)
                if pilihan is None:
                    return
                if pilihan == "geonode":
                    self._terapkan_cakupan_geonode(ds)
                    g, catatan, tidak_standar = self._siapkan(ds)
                self._catat("Cakupan/CRS berbeda dengan GeoNode — dikirim nilai %s." % pilihan)
            if QMessageBox.question(
                    self, JUDUL,
                    "Metadata dataset «%s» di %s (%s) akan diganti dengan isian GeoMDB saat ini.\n%s\n"
                    "Metadata lama disimpan dulu sebagai cadangan.\n\nLanjutkan?" % (
                        ds.get("title"), k.base, profil["label"],
                        "CSW GeoNode akan menyajikan XML GeoMDB apa adanya (preserve)." if profil["preserve_api"] else
                        "Preserve tidak bisa diatur plugin di versi ini — pastikan admin GeoNode sudah mencentang "
                        "«Metadata uploaded preserve» untuk dataset ini, kalau tidak CSW dibuat ulang dari template.")
            ) != YA:
                return
            self.b_kirim.setEnabled(False)
            judul = gs.judul_xml(g)
            self._catat("1/5 XML ISO 19139 disiapkan (fileIdentifier = %s)." % ds.get("uuid"))
            try:
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
                self._catat("3/5 %s: preserve diatur admin di Django admin (tidak lewat API)." % profil["label"])
            elif not ds.get("metadata_uploaded_preserve"):
                k.set_preserve(pk, True)  # harus sebelum unggah (lihat geonode_sync)
                self._catat("3/5 metadata_uploaded_preserve dinyalakan.")
            else:
                self._catat("3/5 preserve sudah aktif.")
            exec_id = k.unggah_metadata(pk, gs.xml_bytes(g), ds.get("alternate") or "")
            self._catat("4/5 XML diunggah, diproses GeoNode (execution %s) …" % exec_id)
            st = k.tunggu_eksekusi(exec_id, lapor=lambda s, langkah: self._catat("    status: %s %s" % (s, langkah)))
            status, pesan = gs.ringkas_status(st)
            if status != gs.SELESAI:
                raise GeoNodeError("Pemrosesan GeoNode %s: %s" % (status or "tidak selesai", pesan or "-"))
            masalah_csw = gs.periksa_record_csw(k.csw_record(ds["uuid"]), ds["uuid"], g, preserve=True)
            if masalah_csw and not profil["preserve_api"]:
                masalah_csw.append("Di %s preserve hanya bisa dinyalakan admin: Django admin → Datasets → dataset ini → "
                                   "centang «Metadata uploaded preserve», lalu kirim ulang." % profil["label"])
            masalah_db = gs.periksa_dataset(k.dataset(pk), g)
            self._catat("5/5 CSW GeoNode %s\n    Isian GeoNode (%s) %s" % (
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
            (QMessageBox.information if not masalah else QMessageBox.warning)(
                self, JUDUL, "Metadata «%s» terkirim ke GeoNode dan %s.<br><br>%s%s" % (
                    html.escape(judul), "terverifikasi di CSW & isian GeoNode" if not masalah
                    else "<b>belum terbukti diterapkan — periksa catatan di bawah</b>", isi,
                    ("<br>Metadata sebelumnya dicadangkan; bisa dikembalikan lewat «Pulihkan dari cadangan…»:<br>"
                     "<code>%s</code>" % html.escape(cadangan)) if cadangan else ""))
        except GeoNodeError as e:
            self._catat("Gagal: %s" % e)
            QMessageBox.warning(self, JUDUL, "Gagal mengirim ke GeoNode:\n%s" % e)
        except Exception as e:  # galat tak terduga: tampilkan, jangan tutup QGIS
            self._catat("Galat: %s" % e)
            QMessageBox.warning(self, JUDUL, "Galat tak terduga:\n%s" % e)
        finally:
            self._pilihan_berubah(self.lst.currentItem())

    def pulihkan(self):
        """Unggah kembali cadangan ke dataset ASALNYA (uuid dicocokkan), dengan status preserve semula."""
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
            if QMessageBox.question(
                    self, JUDUL, "Pulihkan metadata dataset «%s» (#%s) ke keadaan cadangan %s?\n"
                    "Metadata saat ini akan diganti." % (ds.get("title"), ds.get("pk"), info.get("waktu")),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No) != YA:
                return
            lama = info.get("metadata_uploaded_preserve")
            if profil["preserve_api"] and lama is not None and bool(ds.get("metadata_uploaded_preserve")) != bool(lama):
                k.set_preserve(ds["pk"], bool(lama))  # sebelum unggah — kembalikan status preserve semula
                self._catat("Pulihkan: preserve dikembalikan ke %s." % bool(lama))
            exec_id = k.unggah_metadata(ds["pk"], gs.xml_bytes(md), ds.get("alternate") or "")
            self._catat("Pulihkan: cadangan %s diunggah (execution %s) …" % (os.path.basename(jalur_xml), exec_id))
            status, pesan = gs.ringkas_status(k.tunggu_eksekusi(exec_id))
            if status != gs.SELESAI:
                raise GeoNodeError("Pemrosesan GeoNode %s: %s" % (status or "tidak selesai", pesan or "-"))
            self._catat("Pulihkan selesai.")
            QMessageBox.information(self, JUDUL, "Metadata dataset «%s» dipulihkan dari cadangan %s." % (
                ds.get("title"), info.get("waktu")))
        except (GeoNodeError, OSError, ValueError, KeyError) as e:
            self._catat("Gagal memulihkan: %s" % e)
            QMessageBox.warning(self, JUDUL, "Gagal memulihkan dari cadangan:\n%s" % e)
