"""Test: ekspor/impor raster ISO 19139, simpan ISO 19115-3 standar vs mode BIG, dan pemberitahuan
kesesuaian standar (daftar kode, enumerasi, pilihan formulir). Tanpa QGIS:
    python -m unittest discover -s iso19115_metadata_editor/tests -t .
"""
import copy
import os
import tempfile
import unittest
from collections import Counter

from .. import big_compat, gmd_exporter, gmd_importer, kesesuaian, layout, model

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GMD = gmd_exporter.GMD
GCO = gmd_exporter.GCO
GML32 = "http://www.opengis.net/gml/3.2"


def q(tag):
    return "{%s}%s" % (GMD, tag)


def muat(nama):
    return model.load(os.path.join(HERE, nama))[0]


def isian(root, tahap=None):
    """Counter (tahap, kunci, nilai) seluruh isian formulir yang terisi."""
    out = Counter()

    def walk(nodes, sid):
        for n in nodes:
            if isinstance(n, layout.BField) and (n.field.get() or "").strip():
                out[(sid, n.key, n.field.get().strip())] += 1
            elif isinstance(n, layout.BOptional) and n.present:
                walk(n.nodes, sid)
            elif isinstance(n, layout.BList):
                for i in n.instances:
                    walk(i.nodes, sid)
    for s in layout.build(root)[0]:
        if tahap is None or s.id in tahap:
            walk(s.nodes, s.id)
    return out


def simpan_standar(root):
    out = copy.deepcopy(root)
    big_compat.ke_standar(out)
    model.prune_empty(out)
    return out


class RasterISO19139(unittest.TestCase):

    def setUp(self):
        self.root = muat("contoh_raster.xml")
        self.catatan = []
        self.g = gmd_exporter.export_to_gmd(self.root, catatan=self.catatan)

    def test_grid_citra_dan_band_terekspor(self):
        geo = self.g.find(".//" + q("MD_Georectified"))
        self.assertIsNotNone(geo)
        self.assertIsNotNone(self.g.find(".//" + q("MD_Georeferenceable")))
        # ejaan formulir "centre" → enumerasi ISO 19139 "center"
        self.assertEqual(geo.findtext("%s/%s" % (q("pointInPixel"), q("MD_PixelOrientationCode"))), "center")
        pos = [p.text for p in geo.iter("{%s}pos" % GML32)]
        self.assertIn("-6.4 106.6", pos)
        img = self.g.find(".//" + q("MD_ImageDescription"))
        self.assertIsNotNone(img)
        self.assertTrue(img.findall("%s/%s" % (q("dimension"), q("MD_Band"))))
        # bagian ISO 19115-2 dilaporkan, bukan hilang diam-diam
        self.assertTrue(any("GCP" in c for c in self.catatan))
        self.assertTrue(any("boundMin" in c for c in self.catatan))

    def test_kode_tipe_unsur_dan_negara(self):
        ln = [e for e in self.g.iter("{%s}LocalName" % GCO) if e.get("codeSpace")]
        self.assertTrue(ln, "kode tipe unsur → atribut codeSpace")
        self.assertIsNotNone(self.g.find("%s/%s/%s" % (q("locale"), q("PT_Locale"), q("country"))))

    def test_bolak_balik_raster(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, "raster.xml")
            gmd_exporter.save_gmd_to_file(self.g, f)
            balik = gmd_importer.convert_gmd_to_iso3(f, os.path.join(HERE, "template.xml"))
        a, b = isian(self.root, (3, 5)), isian(balik, (3, 5))
        for kunci in ("rasterNumDimensions", "dimName", "rasterCornerPoint1Lat", "rasterPointPixel",
                      "controlPointAvailability", "georeferencedParameters", "description", "maxValue",
                      "imageCloudCoverPercentage", "imageQualityCode"):
            nilai_asli = {v for (s, k, v) in a if k == kunci}
            self.assertTrue(nilai_asli, kunci)
            self.assertTrue(nilai_asli <= {v for (s, k, v) in b if k == kunci}, kunci)
        # grid & georef memakai kunci yang sama: masing-masing harus masuk ke bagiannya sendiri
        self.assertEqual(a[(3, "rasterNumDimensions", "2")], b[(3, "rasterNumDimensions", "2")])

    def test_sumber_masukan_tahap_proses_kembali(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, "raster.xml")
            gmd_exporter.save_gmd_to_file(self.g, f)
            balik = gmd_importer.convert_gmd_to_iso3(f, os.path.join(HERE, "template.xml"))

        def sumber(root):
            s8 = [s for s in layout.build(root)[0] if s.id == 8][0]
            return [gmd_exporter._bidang_langsung(o.nodes) for n in s8.nodes
                    if isinstance(n, layout.BList) and n.path.endswith("processStep")
                    for i in n.instances for o in i.nodes
                    if isinstance(o, layout.BOptional) and o.snippet == "proc_source" and o.present]
        self.assertEqual(sumber(self.root)[0]["citationTitle"], sumber(balik)[0].get("citationTitle"))


class SimpanISO191153(unittest.TestCase):

    def test_mode_standar_tanpa_struktur_big(self):
        for nama in ("contoh_lengkap.xml", "contoh_raster.xml"):
            out = simpan_standar(muat(nama))
            tag = {e.tag.rsplit("}", 1)[-1] for e in out.iter()}
            for big in ("Scope", "OutputCitation", "processParameter", "GM_Point", "LE_ParameterDirectionCode"):
                self.assertNotIn(big, tag, "%s: %s" % (nama, big))
            for sd in out.iter("{%s}stepDateTime" % big_compat.NS["mrl"]):
                self.assertIsNotNone(sd.find("{%s}TimeInstant" % GML32), nama)

    def test_mode_standar_urutan_sesuai_xsd(self):
        out = simpan_standar(muat("contoh_raster.xml"))
        for el in out.iter():
            urutan = model.ORDER.get(el.tag.rsplit("}", 1)[-1])
            if urutan:
                pos = [urutan.index(c.tag.rsplit("}", 1)[-1]) for c in el if c.tag.rsplit("}", 1)[-1] in urutan]
                self.assertEqual(pos, sorted(pos), el.tag)
        # order.json dulu menaruh LE_Processing/algorithm di depan (XSD: paling belakang)
        self.assertEqual(model.ORDER["LE_Processing"][-1], "algorithm")

    def test_mode_standar_bisa_dibuka_ulang_utuh(self):
        for nama in ("contoh_lengkap.xml", "contoh_raster.xml"):
            asli = muat(nama)
            with tempfile.TemporaryDirectory() as tmp:
                f = os.path.join(tmp, "simpan.xml")
                model.save(simpan_standar(asli), f)
                dibuka = model.load(f)[0]
            self.assertEqual(isian(asli), isian(dibuka), nama)

    def test_band_dengan_batas_diberi_satuan(self):
        out = simpan_standar(muat("contoh_raster.xml"))
        mrc = big_compat.NS["mrc"]
        for band in out.iter("{%s}MD_Band" % mrc):
            if band.find("{%s}boundMin" % mrc) is not None:
                self.assertIn("nm", "".join(band.find("{%s}boundUnits" % mrc).itertext()))

    def test_mode_big_tetap_sama_dan_mencatat_penyimpangan(self):
        root = muat("contoh_raster.xml")
        lama = copy.deepcopy(root)
        big_compat.normalize_steps(lama)
        lama = big_compat.to_big(lama)          # perilaku lama (tanpa catatan)
        baru, catatan = copy.deepcopy(root), []
        big_compat.normalize_steps(baru, catatan)
        baru = big_compat.to_big(baru, catatan)
        self.assertEqual(model.ET.tostring(lama), model.ET.tostring(baru))
        self.assertTrue(any("gco:DateTime" in c for c in catatan))
        self.assertTrue(any("MD_Georectified" in c for c in catatan))


class Kesesuaian(unittest.TestCase):

    def test_kode_di_luar_daftar_iso(self):
        out = simpan_standar(muat("contoh_raster.xml"))
        pesan = " ".join(kesesuaian.kode_tidak_standar(out, "19115-3"))
        self.assertIn("«license»", pesan)       # ISO 19115-3: "licence"
        self.assertIn("«facsimile»", pesan)     # ISO 19115-3: "fax"
        tidak_standar = []
        gmd_exporter.export_to_gmd(muat("contoh_raster.xml"), tidak_standar=tidak_standar)
        self.assertIn("«browsing»", " ".join(tidak_standar))  # hanya ada di daftar ISO 19115-3

    def test_kategori_topik_di_luar_enumerasi_19139(self):
        root = muat("contoh_lengkap.xml")
        s2 = [s for s in layout.build(root)[0] if s.id == 2][0]
        tc = [n for n in s2.nodes if isinstance(n, layout.BList) and n.path.endswith("topicCategory")][0]
        tc.instances[0].nodes[0].field.set("disaster")
        catatan = []
        g = gmd_exporter.export_to_gmd(root, catatan=catatan)
        nilai = [e.text for e in g.iter(q("MD_TopicCategoryCode"))]
        self.assertNotIn("disaster", nilai)          # enumerasi tertutup: membuat XML tidak valid
        self.assertTrue(any("disaster" in c for c in catatan))

    def test_draf_terdeteksi(self):
        self.assertGreater(kesesuaian.isian_kosong(muat("template.xml")), 0)
        self.assertEqual(kesesuaian.isian_kosong(simpan_standar(muat("contoh_lengkap.xml"))), 0)

    def test_pilihan_formulir_tidak_standar_ditandai(self):
        opsi = layout._options(layout.F("x", "x", "x", "constraintOptions"), None)
        tanda = {v for lbl, v, d in opsi if layout.TANDA_TIDAK_STANDAR in lbl}
        self.assertIn("license", tanda)
        self.assertNotIn("copyright", tanda)


if __name__ == "__main__":
    unittest.main()
