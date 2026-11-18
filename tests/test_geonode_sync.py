"""Test logika sinkronisasi GeoNode (geonode_sync) — tanpa QGIS & tanpa jaringan.
Data dataset: cuplikan respons publik API staging GeoNode (tests/fixtures/geonode_dataset.json).
    python -m unittest discover -s iso19115_metadata_editor/tests -t .
"""
import email.parser
import json
import os
import unittest

from .. import geonode_sync as gs
from .. import gmd_exporter, model

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GMD, GCO = gmd_exporter.GMD, gmd_exporter.GCO


def q(tag):
    return "{%s}%s" % (GMD, tag)


def dataset(**ubah):
    with open(os.path.join(HERE, "tests", "fixtures", "geonode_dataset.json"), encoding="utf-8") as fh:
        d = json.load(fh)
    d.update(ubah)
    return d


def set_judul(g, teks):
    """Ganti judul data (identificationInfo/*/citation/CI_Citation/title) — bukan title sitasi lain."""
    for idf in g.findall(q("identificationInfo")):
        for kelas in idf:
            el = kelas.find("%s/%s/%s/{%s}CharacterString" % (q("citation"), q("CI_Citation"), q("title"), GCO))
            if el is not None:
                el.text = teks
                return
    raise AssertionError("judul data tidak ditemukan")


def contoh():
    return model.load(os.path.join(HERE, "contoh_lengkap.xml"))[0]


class SiapkanXML(unittest.TestCase):

    def test_file_identifier_jadi_uuid_dataset(self):
        ds, catatan = dataset(), []
        g = gs.siapkan_xml(contoh(), ds, catatan=catatan)
        self.assertEqual(g.findtext("%s/{%s}CharacterString" % (q("fileIdentifier"), GCO)), ds["uuid"])
        self.assertTrue(any("fileIdentifier" in c for c in catatan))

    def test_tautan_geonode_disisipkan_saat_preserve(self):
        ds = dataset()
        g = gs.siapkan_xml(contoh(), ds, sisip_tautan=True)
        online = [(ci.findtext("%s/%s" % (q("linkage"), q("URL"))),
                   ci.findtext("%s/{%s}CharacterString" % (q("protocol"), GCO)),
                   ci.findtext("%s/{%s}CharacterString" % (q("name"), GCO)))
                  for ci in g.iter(q("CI_OnlineResource"))]
        wms = [o for o in online if o[1] == "OGC:WMS"]
        self.assertEqual(len(wms), 1)
        self.assertEqual(wms[0][2], ds["alternate"])  # nama layer = alternate, seperti CSW GeoNode
        self.assertTrue(any(o[1] == gs.PROTOKOL_UNDUH for o in online))
        self.assertTrue(any(o[1] == gs.PROTOKOL_TAUTAN for o in online))
        self.assertIsNotNone(g.find(".//" + q("graphicOverview")))
        self.assertEqual(len(online), len(set(online)), "tautan tidak boleh ganda")

    def test_tanpa_preserve_tidak_menyisipkan_tautan(self):
        g = gs.siapkan_xml(contoh(), dataset(), sisip_tautan=False)
        protokol = [e.text for e in g.iter("{%s}CharacterString" % GCO) if e.text and e.text.startswith("OGC:")]
        self.assertEqual(protokol, [])

    def test_struktur_tetap_sesuai_xsd(self):
        g = gs.siapkan_xml(contoh(), dataset())
        order = gmd_exporter._gmd_order()
        for el in g.iter():
            kelas = el.tag.rsplit("}", 1)[-1]
            if el.tag.startswith("{%s}" % GMD) and kelas in order:
                urutan = [p for p, _ in order[kelas]]
                pos = [urutan.index(c.tag.rsplit("}", 1)[-1]) for c in el]
                self.assertEqual(pos, sorted(pos), kelas)

    def test_dataset_tanpa_uuid_ditolak(self):
        with self.assertRaises(ValueError):
            gs.siapkan_xml(contoh(), dataset(uuid=""))


class BantuAPI(unittest.TestCase):

    def test_url_dasar(self):
        self.assertEqual(gs.url_dasar("https://geonode.contoh.go.id/#/"),
                         "https://geonode.contoh.go.id")
        self.assertEqual(gs.url_dasar("geoportal.contoh.go.id/"), "https://geoportal.contoh.go.id")

    def test_izin_ubah_dari_perms(self):
        self.assertFalse(gs.boleh_ubah(dataset()))  # perms anonim: view & download
        self.assertTrue(gs.boleh_ubah(dataset(perms=["view_resourcebase", "change_resourcebase_metadata"])))

    def test_form_unggah_multipart(self):
        xml = gs.xml_bytes(gs.siapkan_xml(contoh(), dataset()))
        body, tipe = gs.form_unggah(3, xml, "geonode:umkm")
        pesan = email.parser.BytesParser().parsebytes(b"Content-Type: " + tipe.encode() + b"\r\n\r\n" + body)
        bagian = {p.get_param("name", header="content-disposition"): p for p in pesan.get_payload()}
        self.assertEqual(bagian["action"].get_payload(), "resource_metadata_upload")
        self.assertEqual(bagian["resource_pk"].get_payload(), "3")  # GeoNode 5
        self.assertEqual(bagian["dataset_title"].get_payload(), "geonode:umkm")  # GeoNode 4.x (importer)
        self.assertEqual(bagian["base_file"].get_filename(), "metadata.xml")
        self.assertEqual(bagian["base_file"].get_payload(decode=True), xml.split(b"?>", 1)[1].lstrip())
        # handler vektor/raster GeoNode 5 hanya membaca files["xml_file"] (base_file memilih handler)
        self.assertEqual(bagian["xml_file"].get_filename(), "metadata.xml")
        self.assertEqual(bagian["xml_file"].get_payload(decode=True), bagian["base_file"].get_payload(decode=True))

    def test_unggahan_tanpa_deklarasi_xml(self):
        """GeoNode membaca unggahan sebagai str lalu lxml.fromstring — str berdeklarasi encoding ditolak
        (galat nyata di staging: "Unicode strings with encoding declaration are not supported")."""
        import xml.etree.ElementTree as ET
        xml = gs.xml_bytes(gs.siapkan_xml(contoh(), dataset()))
        self.assertTrue(xml.startswith(b"<?xml"))
        body, tipe = gs.form_unggah(3, b"\xef\xbb\xbf" + xml, "geonode:umkm")
        pesan = email.parser.BytesParser().parsebytes(b"Content-Type: " + tipe.encode() + b"\r\n\r\n" + body)
        for p in pesan.get_payload():
            if p.get_filename():
                isi = p.get_payload(decode=True)
                self.assertTrue(isi.startswith(b"<gmd:MD_Metadata"), isi[:60])
                teks = isi.decode("utf-8")  # seperti GeoNode: dibaca sebagai teks lalu di-parse
                self.assertEqual(gs.judul_xml(ET.fromstring(teks)), gs.judul_xml(ET.fromstring(xml)))

    def test_status_dan_csw(self):
        self.assertEqual(gs.ringkas_status({"status": "failed", "log": "XML tidak valid"}), ("failed", "XML tidak valid"))
        g = gs.siapkan_xml(contoh(), dataset())
        teks = gs.xml_bytes(g).decode("utf-8")
        uuid = dataset()["uuid"]
        self.assertEqual(gs.periksa_record_csw(teks, uuid, g, preserve=True), [])
        self.assertTrue(gs.periksa_record_csw(teks, "uuid-lain", g))
        lain = gs.siapkan_xml(contoh(), dataset())
        set_judul(lain, "Judul lain")
        self.assertTrue(any("Judul" in m for m in gs.periksa_record_csw(teks, uuid, lain)))

    def test_record_template_geonode_terdeteksi(self):
        """Kasus nyata staging (dataset #2): unggahan tanpa xml_file → CSW dibuat ulang dari template
        GeoNode walau preserve aktif; pemeriksaan lama (uuid + judul) menganggapnya berhasil."""
        with open(os.path.join(HERE, "tests", "fixtures", "csw_template_geonode.xml"), encoding="utf-8") as fh:
            record = fh.read()
        md_csw = gs.ambil_md_metadata(record)
        uuid = md_csw.findtext("%s/{%s}CharacterString" % (q("fileIdentifier"), GCO))
        g = gs.siapkan_xml(contoh(), dataset(uuid=uuid))
        set_judul(g, gs.judul_xml(md_csw))  # judul sama → pemeriksaan lama lolos
        self.assertFalse(any("Judul" in m for m in gs.periksa_record_csw(record, uuid, g)))
        masalah = gs.periksa_record_csw(record, uuid, g, preserve=True)
        self.assertTrue(any("Abstrak" in m for m in masalah), masalah)
        self.assertTrue(any("template" in m for m in masalah), masalah)

    def test_periksa_isian_dataset(self):
        g = gs.siapkan_xml(contoh(), dataset())
        judul, abstrak = gs.judul_xml(g), gs.abstrak_xml(g)
        self.assertTrue(abstrak)
        self.assertEqual(gs.periksa_dataset({"title": judul, "raw_abstract": "  " + abstrak + "\n"}, g), [])
        self.assertEqual(gs.periksa_dataset({"title": judul, "abstract": "<p>%s</p>" % abstrak}, g), [])
        self.assertEqual(len(gs.periksa_dataset({"title": "kerentanan_pangan_oke", "abstract": ""}, g)), 2)


class Katalog(unittest.TestCase):

    def test_wms_pratinjau_pakai_layanan_virtual_per_layer(self):
        url, layer = gs.wms_pratinjau(dataset())
        self.assertEqual(url, "https://geonode.contoh.go.id/geoserver/geonode/"
                              "umkm_1000_lebih_1f9e51a74e9acea0c461050f6a9e113d/ows")
        self.assertEqual(layer, "umkm_1000_lebih_1f9e51a74e9acea0c461050f6a9e113d")  # tanpa awalan workspace
        self.assertEqual(gs.layanan_wms(dataset())[1], dataset()["alternate"])

    def test_wms_pratinjau_bukan_geoserver_apa_adanya(self):
        ds = dataset(links=[{"link_type": "OGC:WMS", "url": "https://peta.contoh.go.id/wms?map=a"}], alternate="a:b")
        self.assertEqual(gs.wms_pratinjau(ds), ("https://peta.contoh.go.id/wms", "a:b"))
        self.assertIsNone(gs.wms_pratinjau(dataset(links=[])))

    def test_token_hanya_ke_host_geonode(self):
        base = "https://geonode.contoh.go.id/#/"
        self.assertTrue(gs.host_sama("https://geonode.contoh.go.id/uploaded/thumbs/a.jpg", base))
        self.assertFalse(gs.host_sama("https://cdn.lain.com/uploaded/thumbs/a.jpg", base))
        self.assertFalse(gs.host_sama("http://geonode.contoh.go.id/a.jpg", base))  # turun ke http
        self.assertFalse(gs.host_sama("https://geonode.contoh.go.id.jahat.com/a.jpg", base))
        self.assertFalse(gs.host_sama("/relatif.jpg", base))

    def test_cakupan_dataset(self):
        ext = {"coords": [110.20357, -7.4999, 110.23545, -7.4319], "srid": "EPSG:4326"}
        self.assertEqual(gs.cakupan_dataset(dataset(extent=ext)), (110.20357, -7.4999, 110.23545, -7.4319))
        poli = {"type": "Polygon", "coordinates": [[[110.2, -7.5], [110.3, -7.5], [110.3, -7.4], [110.2, -7.4], [110.2, -7.5]]]}
        self.assertEqual(gs.cakupan_dataset(dataset(extent={"coords": [1, 2, 3, 4], "srid": "EPSG:32749"},
                                                    ll_bbox_polygon=poli)), (110.2, -7.5, 110.3, -7.4))
        self.assertIsNone(gs.cakupan_dataset(dataset()))

    def test_ringkas_dataset(self):
        r = gs.ringkas_dataset(dataset(subtype="raster", owner={"username": "admin", "first_name": "Budi"},
                                       date="2026-10-30T08:00:00Z", category={"gn_description": "Ekonomi"}))
        self.assertEqual((r["jenis"], r["pemilik"], r["tanggal"], r["kategori"]), ("Raster", "Budi", "2026-10-30", "Ekonomi"))
        self.assertFalse(r["boleh_ubah"])
        self.assertTrue(r["thumbnail"].startswith("https://"))
        self.assertEqual(gs.ringkas_dataset({})["judul"], "(tanpa judul)")


class VersiGeoNode(unittest.TestCase):
    # daftar endpoint /api/v2/ asli staging uji (GeoNode 5.0.x)
    AKAR_5 = dict.fromkeys("assets categories datasets documents executionrequest geoapps groups keywords maps "
                           "metadata owners regions resources tkeywords upload-parallelism-limits "
                           "upload-size-limits users".split(), "url")

    def test_deteksi_generasi(self):
        akar_44 = {k: v for k, v in self.AKAR_5.items() if k != "metadata"}
        akar_4x = {k: v for k, v in akar_44.items() if k != "assets"}
        self.assertEqual(gs.versi_dari_api(self.AKAR_5), "5")
        self.assertEqual(gs.versi_dari_api(akar_44), "4.4")
        self.assertEqual(gs.versi_dari_api(akar_4x, {"pk": 1, "extent": {}}), "4.2")
        self.assertEqual(gs.versi_dari_api(akar_4x, {"pk": 1, "ll_bbox_polygon": {}}), "4.0")
        self.assertIsNone(gs.versi_dari_api(akar_4x, None))  # 4.x tanpa dataset terlihat: belum pasti
        self.assertIsNone(gs.versi_dari_api({"detail": "bukan GeoNode"}))
        self.assertIsNone(gs.versi_dari_api(["bukan", "dict"]))

    def test_profil_versi(self):
        self.assertTrue(gs.VERSI["5"]["preserve_api"] and gs.VERSI["4.4"]["preserve_api"])
        self.assertTrue(gs.VERSI["4.2"]["unggah"] and not gs.VERSI["4.2"]["preserve_api"])
        self.assertFalse(gs.VERSI["4.0"]["unggah"])
        ds = {"pk": 2, "alternate": "geonode:kerentanan_pangan_oke"}
        self.assertEqual(gs.halaman_metadata("5", ds), "/metadata/2")
        self.assertEqual(gs.halaman_metadata("4.2", ds), "/datasets/geonode:kerentanan_pangan_oke/metadata")


class TemplateBersih(unittest.TestCase):
    MINIMAL = ('<gmd:MD_Metadata xmlns:gmd="%s" xmlns:gco="%s"><gmd:fileIdentifier><gco:CharacterString>uji-uuid'
               '</gco:CharacterString></gmd:fileIdentifier><gmd:identificationInfo><gmd:MD_DataIdentification>'
               '<gmd:citation><gmd:CI_Citation><gmd:title><gco:CharacterString>JUDUL-UJI</gco:CharacterString>'
               '</gmd:title></gmd:CI_Citation></gmd:citation><gmd:abstract><gco:CharacterString>ABSTRAK-UJI'
               '</gco:CharacterString></gmd:abstract></gmd:MD_DataIdentification></gmd:identificationInfo>'
               '</gmd:MD_Metadata>' % (GMD, GCO))

    def nilai(self, g):
        return {" ".join(e.text.split()) for e in g.iter() if e.text and e.text.strip()} | {
            v for e in g.iter() for k, v in e.attrib.items() if k == "codeSpace"}

    def test_mode_geonode_hanya_data_geonode(self):
        from .. import gmd_importer
        src = gmd_exporter.ET.fromstring(self.MINIMAL)
        root = gmd_importer.convert_gmd_to_iso3(src, os.path.join(HERE, "template.xml"), bersih=True)
        sisa = [e.get("codeSpace") for e in root.iter() if (e.get("codeSpace") or "").strip()]
        self.assertEqual(sisa, [], "nilai contoh template (KAB/KEC) harus dibuang")
        nilai = self.nilai(gmd_exporter.export_to_gmd(root))
        # selain data sumber hanya default struktur exporter (hierarchyLevel/lingkup = dataset)
        self.assertEqual(nilai - {"uji-uuid", "JUDUL-UJI", "ABSTRAK-UJI", "dataset"}, set())

    def test_label_slot_formulir_tetap(self):
        from .. import gmd_importer
        root = model.load(os.path.join(HERE, "template.xml"))[0]
        n = gmd_importer.bersihkan_template(root)
        self.assertEqual(n, 2)  # hanya KAB & KEC yang merupakan nilai contoh
        slot = [e.text for e in root.iter() if e.tag.endswith("CI_TelephoneTypeCode")]
        self.assertIn("voice", slot)

    def test_bahasa_data_mewarisi_metadata(self):
        """Simpan 19115-3 standar: bahasa sumber daya kosong → warisi locale metadata (Schematron
        rule.mri.defaultlocalewhenhastext); formulir hasil impor GeoNode dulu gagal di sini."""
        from .. import big_compat, gmd_importer
        src = gmd_exporter.ET.fromstring(self.MINIMAL.replace(
            "<gmd:identificationInfo>", '<gmd:language><gco:CharacterString>eng</gco:CharacterString></gmd:language>'
            "<gmd:identificationInfo>"))
        root = big_compat.ke_standar(gmd_importer.convert_gmd_to_iso3(src, os.path.join(HERE, "template.xml"), bersih=True))
        lan = "http://standards.iso.org/iso/19115/-3/lan/1.0"
        mri = "http://standards.iso.org/iso/19115/-3/mri/1.0"
        kode = root.find(".//{%s}MD_DataIdentification/{%s}defaultLocale//{%s}LanguageCode" % (mri, mri, lan))
        self.assertIsNotNone(kode)
        self.assertEqual(kode.get("codeListValue"), "eng")

    def test_template_kosong_tanpa_tipe_unsur_contoh(self):
        g = gmd_exporter.export_to_gmd(model.load(os.path.join(HERE, "template.xml"))[0])
        self.assertEqual([e.text for e in g.iter("{%s}LocalName" % GCO)], [])
        nama = [(e.text, e.get("codeSpace")) for e in gmd_exporter.export_to_gmd(contoh()).iter("{%s}LocalName" % GCO)]
        self.assertIn(("Kabupaten", "KAB"), nama)  # tipe unsur bernama tetap diekspor beserta kodenya


def record_template_staging():
    with open(os.path.join(HERE, "tests", "fixtures", "csw_template_geonode.xml"), encoding="utf-8") as fh:
        return gs.ambil_md_metadata(fh.read())


class BolakBalikGeoNode(unittest.TestCase):
    """Ambil record CSW GeoNode (mode bersih) → formulir → XML kirim."""

    def kirim(self, md, **ubah):
        from .. import gmd_importer
        uuid = md.findtext("%s/{%s}CharacterString" % (q("fileIdentifier"), GCO))
        form = gmd_importer.convert_gmd_to_iso3(md, os.path.join(HERE, "template.xml"), bersih=True)
        return gs.siapkan_xml(form, dataset(uuid=uuid, **ubah))

    def test_tautan_tidak_dobel(self):
        with open(os.path.join(HERE, "..", "iso19115_metadata_editor", "tests", "fixtures", "geonode_dataset.json"),
                  encoding="utf-8") as fh:
            links = json.load(fh)["links"]
        g = self.kirim(record_template_staging(), links=links + [
            {"link_type": "data", "name": "Zipped Shapefile", "url": u} for u in
            [ci.findtext("%s/%s" % (q("linkage"), q("URL"))) for ci in record_template_staging().iter(q("CI_OnlineResource"))
             if "SHAPE-ZIP" in (ci.findtext("%s/%s" % (q("linkage"), q("URL"))) or "")]])
        kunci = [(ci.findtext("%s/%s" % (q("linkage"), q("URL"))), ci.findtext("%s/{%s}CharacterString" % (q("protocol"), GCO)))
                 for ci in g.iter(q("CI_OnlineResource"))]
        self.assertEqual(len(kunci), len(set(kunci)), "URL + protokol yang sama tidak boleh tersisip dua kali")

    def test_datestamp_waktu_kirim(self):
        import datetime
        waktu = datetime.datetime(2026, 11, 5, 9, 30, tzinfo=datetime.timezone.utc)
        g = gs.siapkan_xml(contoh(), dataset(), waktu=waktu)
        self.assertEqual(g.findtext("%s/{%s}DateTime" % (q("dateStamp"), GCO)), "2026-11-05T09:30:00Z")
        self.assertEqual(len(g.findall(q("dateStamp"))), 1)

    def test_datestamp_bawaan_tanggal_dataset(self):
        """GeoNode mengisi tanggal dataset dari dateStamp — bawaan kirim memakai tanggal dataset agar tidak berubah."""
        g = gs.siapkan_xml(contoh(), dataset(date="2026-05-06T05:18:37.261161Z"))
        self.assertEqual(g.findtext("%s/{%s}DateTime" % (q("dateStamp"), GCO)), "2026-05-06T05:18:37.261161Z")
        self.assertEqual(gs.baca_waktu("2026-05-06").isoformat(), "2026-05-06T00:00:00+00:00")
        self.assertIsNone(gs.baca_waktu("bukan tanggal"))

    def test_tanggal_asli_dari_cadangan_lama(self):
        """Cadangan lama tanpa `date`: tanggal sitasi record GeoNode = tanggal dataset (staging: 2026-05-06)."""
        self.assertEqual(gs.tanggal_kutipan(record_template_staging()), "2026-05-06T05:18:37Z")
        info = gs.info_cadangan("https://x.go.id", dataset(date="2026-05-06T05:18:37Z"), "5",
                                gs.baca_waktu("2026-11-05T12:51:40Z"))
        self.assertEqual(info["date"], "2026-05-06T05:18:37Z")

    def test_peran_geonode_jadi_kode_iso(self):
        """Template CSW GeoNode menulis label peran ("Metadata Author", "Point of Contact") — dulu ikut terkirim dan
        ditandai di luar ISO 19139 (uji nyata staging). Mode GeoNode memetakannya ke kode ISO."""
        tidak_standar = []
        md = record_template_staging()
        uuid = md.findtext("%s/{%s}CharacterString" % (q("fileIdentifier"), GCO))
        from .. import gmd_importer
        form = gmd_importer.convert_gmd_to_iso3(md, os.path.join(HERE, "template.xml"), bersih=True)
        g = gs.siapkan_xml(form, dataset(uuid=uuid), tidak_standar=tidak_standar)
        peran = sorted({e.get("codeListValue") for e in g.iter(q("CI_RoleCode"))})
        self.assertEqual(peran, ["author", "owner", "pointOfContact"])
        self.assertFalse([t for t in tidak_standar if "CI_RoleCode" in t], tidak_standar)
        for label, kode in (("Resource User", "user"), ("principal_investigator", "principalInvestigator"),
                            ("poc", "pointOfContact"), ("author", None)):
            el = gmd_exporter.ET.fromstring('<gmd:CI_RoleCode xmlns:gmd="%s" codeListValue="%s">%s</gmd:CI_RoleCode>'
                                            % (GMD, label, label))
            akar = gmd_exporter.ET.Element("r")
            akar.append(el)
            self.assertEqual(gmd_importer.normalkan_peran_geonode(akar), 0 if kode is None else 1)
            self.assertEqual(el.get("codeListValue"), kode or label)

    def test_teks_pengisi_geonode_dibuang(self):
        g = self.kirim(record_template_staging())
        nilai = {(e.text or "").strip() for e in g.iter()}
        self.assertNotIn("None", nilai)
        self.assertNotIn("No abstract provided", nilai)
        self.assertIn("kerentanan_pangan_oke", nilai)  # data sungguhan tetap

    def test_info_tambahan_doi_dan_batasan_ganda(self):
        md = record_template_staging()
        di = md.find("%s/%s" % (q("identificationInfo"), q("MD_DataIdentification")))
        cit = di.find("%s/%s" % (q("citation"), q("CI_Citation")))
        gmx = "http://www.isotc211.org/2005/gmx"
        idf = gmd_exporter.ET.SubElement(gmd_exporter.ET.SubElement(gmd_exporter.ET.SubElement(cit, q("identifier")),
                                                                    q("MD_Identifier")), q("code"))
        gmd_exporter.ET.SubElement(idf, "{%s}Anchor" % gmx).text = "doi:10.1234/uji"
        di.find(q("supplementalInformation")).find("{%s}CharacterString" % GCO).text = "INFO-TAMBAHAN"
        for rc in di.findall(q("resourceConstraints")):
            di.remove(rc)
        for kode, teks in (("license", ["CC-BY-4.0", "DOI: 10.1234/uji"]), ("otherRestrictions", ["BATASAN-LAIN"])):
            lc = gmd_exporter.ET.SubElement(gmd_exporter.ET.SubElement(di, q("resourceConstraints")), q("MD_LegalConstraints"))
            uc = gmd_exporter.ET.SubElement(gmd_exporter.ET.SubElement(lc, q("useConstraints")), q("MD_RestrictionCode"))
            uc.set("codeListValue", kode)
            uc.text = kode
            for t in teks:
                gmd_exporter.ET.SubElement(gmd_exporter.ET.SubElement(lc, q("otherConstraints")),
                                           "{%s}CharacterString" % GCO).text = t
        g = self.kirim(md)
        gdi = g.find("%s/%s" % (q("identificationInfo"), q("MD_DataIdentification")))
        self.assertEqual(gdi.findtext("%s/{%s}CharacterString" % (q("supplementalInformation"), GCO)), "INFO-TAMBAHAN")
        self.assertIn("doi:10.1234/uji", [e.text for e in gdi.iter("{%s}CharacterString" % GCO)])
        legal = gdi.findall("%s/%s" % (q("resourceConstraints"), q("MD_LegalConstraints")))
        self.assertEqual(len(legal), 1)
        self.assertEqual([e.get("codeListValue") for e in legal[0].iter(q("MD_RestrictionCode"))], ["license", "otherRestrictions"])
        self.assertEqual([e.findtext("{%s}CharacterString" % GCO) for e in legal[0].findall(q("otherConstraints"))],
                         ["CC-BY-4.0", "DOI: 10.1234/uji", "BATASAN-LAIN"])


class PengamanSalahTujuan(unittest.TestCase):

    def test_konfirmasi_nama_layer(self):
        ds = dataset()
        self.assertEqual(gs.nama_layer(ds), "umkm_1000_lebih_1f9e51a74e9acea0c461050f6a9e113d")
        self.assertTrue(gs.nama_cocok(" UMKM_1000_lebih_1f9e51a74e9acea0c461050f6a9e113d ", ds))
        self.assertTrue(gs.nama_cocok(ds["alternate"], ds))
        self.assertFalse(gs.nama_cocok("kerentanan_pangan_oke", ds))
        self.assertFalse(gs.nama_cocok("", ds))

    def test_kode_epsg(self):
        for teks in ("EPSG:4326", "4326", "urn:ogc:def:crs:EPSG::4326"):
            self.assertEqual(gs.kode_epsg(teks), "4326")
        self.assertIsNone(gs.kode_epsg("WGS 84"))

    def test_bandingkan_cakupan(self):
        ext = {"coords": [110.19889, -7.50603, 110.23748, -7.43351], "srid": "EPSG:4326"}
        g = gs.siapkan_xml(contoh(), dataset())
        bb = gs.cakupan_xml(g)
        self.assertIsNotNone(bb)
        sama = dataset(extent={"coords": list(bb), "srid": "EPSG:4326"}, srid="EPSG:%s" % gs.crs_xml(g))
        self.assertEqual(gs.bandingkan_cakupan(g, sama), [])
        beda = gs.bandingkan_cakupan(g, dataset(extent=ext, srid="EPSG:32749"))
        self.assertTrue(any(b.startswith("Cakupan") for b in beda))
        self.assertTrue(any("EPSG:32749" in b for b in beda))
        self.assertEqual(gs.bandingkan_cakupan(g, dataset()), [])  # GeoNode tanpa cakupan: tidak dibandingkan

    def test_crs_record_geonode_terbaca(self):
        """Record GeoNode: code 4326, codeSpace EPSG, version 6.11 — dulu terbaca kosong (uji nyata staging)."""
        md = record_template_staging()
        self.assertEqual(gs.crs_xml(md), "4326")
        bb = gs.cakupan_xml(md)
        sama = dataset(extent={"coords": list(bb), "srid": "EPSG:4326"}, srid="EPSG:4326")
        self.assertEqual(gs.bandingkan_cakupan(md, sama), [])
        self.assertTrue(gs.bandingkan_cakupan(md, dict(sama, srid="EPSG:32749")))
        self.assertEqual(gs.crs_xml(gs.siapkan_xml(contoh(), dataset())), "4326")

    def test_cadangan_hanya_ke_dataset_asal(self):
        import datetime
        ds = dataset(pk=3, metadata_uploaded_preserve=False)
        waktu = datetime.datetime(2026, 11, 5, 9, 30, tzinfo=datetime.timezone.utc)
        folder, dasar = gs.lokasi_cadangan("https://geonode.contoh.go.id/#/", ds, waktu)
        self.assertEqual(folder.replace("\\", "/"),
                         "geonode.contoh.go.id/3-umkm_1000_lebih_1f9e51a74e9acea0c461050f6a9e113d")
        self.assertEqual(dasar, "20261105-093000")
        info = gs.info_cadangan("https://geonode.contoh.go.id", ds, "5", waktu)
        self.assertIs(info["metadata_uploaded_preserve"], False)
        self.assertEqual(gs.cek_cadangan(info, "https://geonode.contoh.go.id/", ds), [])
        self.assertTrue(gs.cek_cadangan(info, "https://geoportal.lain.go.id", ds))
        self.assertTrue(gs.cek_cadangan(info, "https://geonode.contoh.go.id", dataset(uuid="lain")))


class AlurAmbilPerbarui(unittest.TestCase):

    def test_ambil_dari_respons_csw_ke_formulir(self):
        from .. import gmd_importer
        g = gs.siapkan_xml(contoh(), dataset())
        respons = (b'<csw:GetRecordByIdResponse xmlns:csw="http://www.opengis.net/cat/csw/2.0.2">'
                   + gmd_exporter.ET.tostring(g) + b"</csw:GetRecordByIdResponse>")
        md = gs.ambil_md_metadata(respons)
        self.assertIsNotNone(md)
        root = gmd_importer.convert_gmd_to_iso3(md, os.path.join(HERE, "template.xml"))
        self.assertEqual(gs.judul_formulir(root), gs.judul_formulir(contoh()))
        self.assertIsNone(gs.ambil_md_metadata(b"<bukan-xml"))

    def test_nama_grup_pengguna(self):
        # bentuk nyata GeoNode 5: DAFTAR GroupProfile (dulu dikira {"groups": [...]} → galat saat login Basic)
        g5 = [{"pk": 1, "title": "Produsen Contoh", "slug": "produsen-contoh", "group": {"pk": 2}},
              {"pk": 3, "title": "", "slug": "walidata"}]
        self.assertEqual(gs.nama_grup(g5), ["Produsen Contoh", "walidata"])
        self.assertEqual(gs.nama_grup({"groups": [{"name": "a"}]}), ["a"])
        self.assertEqual(gs.nama_grup([]), [])
        self.assertEqual(gs.nama_grup(None), [])

    def test_gejala_bug_preserve(self):
        # pesan nyata dari staging (unggah dengan preserve di GeoNode yang belum ditambal)
        nyata = ("Start tag expected, '<' not found, line 1, column 1 (<string>, line 1); {'errors': ['Task: "
                 "geonode.upload.import_resource raised an error during actions for layer: resource_metadata_upload")
        self.assertTrue(gs.gejala_bug_preserve(nyata))
        self.assertFalse(gs.gejala_bug_preserve("Unicode strings with encoding declaration are not supported."))
        self.assertFalse(gs.gejala_bug_preserve(""))
        self.assertIn(gs.URL_ALAT_TAMBAL, gs.SARAN_CSW_RUSAK)
        data = [dataset(pk=1, metadata_uploaded_preserve=True), dataset(pk=2, metadata_uploaded_preserve=False),
                dataset(pk=3)]
        self.assertEqual([d["pk"] for d in gs.dataset_preserve(data)], [1])

    def test_exceptionreport_csw_terbaca(self):
        lapor = (b'<ows:ExceptionReport xmlns:ows="http://www.opengis.net/ows" version="1.2.0"><ows:Exception '
                 b'exceptionCode="NoApplicableCode"><ows:ExceptionText>Unicode strings with encoding declaration '
                 b'are not supported.</ows:ExceptionText></ows:Exception></ows:ExceptionReport>')
        self.assertIn("encoding declaration", gs.pesan_csw(lapor))
        self.assertEqual(gs.pesan_csw(gs.xml_bytes(gs.siapkan_xml(contoh(), dataset()))), "")
        self.assertEqual(gs.pesan_csw(b"<html>bukan xml"), "")

    def test_formulir_kosong_terdeteksi(self):
        self.assertEqual(gs.judul_formulir(model.load(os.path.join(HERE, "template.xml"))[0]), "")

    def test_tautan_dataset(self):
        t = {"url": "https://geonode.contoh.go.id/#/", "pk": 3}
        self.assertTrue(gs.tautan_cocok(t, "https://geonode.contoh.go.id", "3"))
        self.assertFalse(gs.tautan_cocok(t, "https://geonode.contoh.go.id", 2))
        self.assertFalse(gs.tautan_cocok(None, "https://geonode.contoh.go.id", 3))
        self.assertEqual(gs.pk_tautan(t, "https://geonode.contoh.go.id"), "3")
        self.assertIsNone(gs.pk_tautan(t, "https://geoportal.belitung.go.id"))
        self.assertIsNone(gs.pk_tautan(None, "https://geonode.contoh.go.id"))


class PenghalangDiDepanGeoNode(unittest.TestCase):
    """Respons yang tidak berasal dari GeoNode tidak boleh dibaca sebagai «password salah» (kasus nyata Belitung:
    cek bot Cloudflare menjawab HTTP 403 untuk semua permintaan QGIS)."""
    BASE = "https://geoportal.belitung.go.id"
    HALAMAN_CF = b"<!DOCTYPE html><html lang='en-US'><head><title>Just a moment...</title></head><body>" \
                 b"<script src='https://challenges.cloudflare.com/cdn-cgi/challenge-platform/'></script></body></html>"

    def test_tantangan_cloudflare(self):
        h = {"server": "cloudflare", "cf-mitigated": "challenge", "content-type": "text/html; charset=UTF-8"}
        p = gs.pesan_penghalang(403, h, self.HALAMAN_CF, self.BASE, harap_json=True)
        self.assertIn("cek bot Cloudflare", p)
        self.assertIn("geoportal.belitung.go.id", p)
        self.assertIn("bukan karena username/password", p)
        for jalur in gs.PATH_PLUGIN:
            self.assertIn(jalur, p)
        # solusinya di pengelola Cloudflare; pindah jaringan terbukti tidak bisa diandalkan (Belitung)
        self.assertLess(p.index("pengelola Cloudflare"), p.index("jaringan lain"))
        self.assertIn("tidak bisa diandalkan", p)
        # badan kosong (dibaca terpotong) tetap dikenali dari header-nya; juga untuk CSW (XML) & 503
        self.assertTrue(gs.pesan_penghalang(403, h, b"", self.BASE))
        self.assertTrue(gs.pesan_penghalang(503, h, b"", self.BASE))

    def test_blokir_cloudflare_dan_lapisan_lain(self):
        blok = b"<html><head><title>Attention Required! | Cloudflare</title></head><body>Sorry, you have been blocked"
        self.assertIn("diblokir Cloudflare", gs.pesan_penghalang(403, {"server": "cloudflare"}, blok, self.BASE))
        waf = b"<html><body><h1>403 Forbidden</h1><hr>nginx</body></html>"
        self.assertIn("firewall/WAF/proxy", gs.pesan_penghalang(403, {"server": "nginx"}, waf, self.BASE, True))
        self.assertEqual(gs.pesan_penghalang(403, {"server": "nginx"}, waf, self.BASE, harap_json=False), "")

    def test_respons_geonode_bukan_penghalang(self):
        cf = {"server": "cloudflare"}  # situs di belakang Cloudflare: SEMUA respons ber-header server cloudflare
        salah = json.dumps({"detail": "Invalid username/password."}).encode()
        self.assertEqual(gs.pesan_penghalang(403, cf, salah, self.BASE, harap_json=True), "")
        self.assertEqual(gs.pesan_penghalang(401, cf, b'{"detail": "User is not authenticated"}', self.BASE, True), "")
        self.assertEqual(gs.pesan_penghalang(200, cf, b'{"datasets": []}', self.BASE, True), "")
        # record CSW rusak (bug preserve): halaman galat 500 Django tetap galat GeoNode
        self.assertEqual(gs.pesan_penghalang(500, cf, b"<html><body>Server Error (500)</body></html>", self.BASE), "")


if __name__ == "__main__":
    unittest.main()
