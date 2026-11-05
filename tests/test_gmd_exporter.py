"""Test regresi ekspor ISO 19139 (gmd_exporter) — tanpa QGIS.

Jalankan dari folder induk plugin:
    python -m unittest discover -s iso19115_metadata_editor/tests -t .

Struktur diperiksa terhadap gmd_order.json (urutan & kewajiban properti yang diturunkan dari XSD
resmi gmd 1.0). Validasi XSD + Schematron penuh dapat dijalankan dengan validator geomdb-hub:
    python scripts/xml-validation/validate.py --file hasil.xml --schema gmd
"""
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET  # nosec B405

from .. import gmd_exporter, gmd_importer, layout, model

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GMD = gmd_exporter.GMD
GCO = gmd_exporter.GCO
CONTOH = ("contoh_lengkap.xml", "contoh_raster.xml", "template.xml")


def q(tag):
    return "{%s}%s" % (GMD, tag)


def ekspor(nama):
    root, _ = model.load(os.path.join(HERE, nama))
    catatan = []
    return root, gmd_exporter.export_to_gmd(root, catatan=catatan), catatan


class EksporGMD(unittest.TestCase):

    def test_tidak_membawa_data_contoh_template(self):
        # Dulu kontak "Yudha Setya", placeholder [..], dan tautan WMS contoh dari gmd_template.xml
        # ikut terekspor setiap kali field terkait tidak diisi.
        for nama in CONTOH:
            _, g, _ = ekspor(nama)
            teks = ET.tostring(g, encoding="unicode")
            self.assertNotRegex(teks, r"\[[A-Z_/]+\]", nama)
            for contoh in ("Yudha Setya", "Batas Kabupaten Bone", "satupeta.gorontaloprov"):
                self.assertNotIn(contoh, teks, nama)

    def test_struktur_sesuai_xsd(self):
        # Setiap kelas gmd hanya memuat properti yang sah, berurutan sesuai xs:sequence,
        # dan properti wajibnya ada (berisi atau gco:nilReason).
        order = gmd_exporter._gmd_order()
        for nama in CONTOH:
            _, g, _ = ekspor(nama)
            for el in g.iter():
                kelas = el.tag.rsplit("}", 1)[-1]
                if not el.tag.startswith("{%s}" % GMD) or kelas not in order:
                    continue
                urutan = [p for p, _ in order[kelas]]
                anak = [c.tag.rsplit("}", 1)[-1] for c in el]
                self.assertTrue(set(anak) <= set(urutan), "%s: %s berisi %s" % (nama, kelas, anak))
                posisi = [urutan.index(a) for a in anak]
                self.assertEqual(posisi, sorted(posisi), "%s: urutan anak %s" % (nama, kelas))
                for prop, minimal in order[kelas]:
                    if minimal:
                        self.assertIn(prop, anak, "%s: %s wajib punya %s" % (nama, kelas, prop))

    def test_isian_penting_terekspor(self):
        _, g, catatan = ekspor("contoh_lengkap.xml")
        # Lineage satu blok dengan laporan, di DQ_DataQuality pertama: OWSLib (GeoNode/pycsw)
        # hanya membaca blok pertama.
        dq = g.find("%s/%s" % (q("dataQualityInfo"), q("DQ_DataQuality")))
        self.assertIsNotNone(dq.find("%s/%s/%s" % (q("lineage"), q("LI_Lineage"), q("statement"))))
        self.assertIsNotNone(dq.find(q("report")))
        # Batasan dulu tidak pernah terekspor (template tak memuat bloknya).
        self.assertTrue(g.findall(".//%s/%s" % (q("resourceConstraints"), q("MD_LegalConstraints"))))
        # Tautan distribusi dulu terhalang bug indentasi Tahap 6.
        urls = [u.text for u in g.iter(q("URL"))]
        self.assertIn("https://data.example.org/batas-admin", urls)  # Tahap 2 (sumber daya online data)
        self.assertIn("https://data.example.org/unduh/batas-admin.zip", urls)  # Tahap 6
        # Isian tanpa padanan ISO 19139 dilaporkan, bukan hilang diam-diam.
        self.assertTrue(any("katalog unsur" in c for c in catatan))

    def test_semua_kontak_metadata_dari_formulir(self):
        root, g, _ = ekspor("contoh_lengkap.xml")
        s1 = [s for s in layout.build(root)[0] if s.id == 1][0]
        kontak = [i for n in s1.nodes if isinstance(n, layout.BList) and n.path == "contact"
                  for i in n.instances if any(gmd_exporter._collect_dict_from_nodes(i.nodes).values())]
        self.assertEqual(len(g.findall(q("contact"))), len(kontak))

    def test_deskripsi_tahap_proses_tidak_tertimpa_sumber(self):
        # `description` milik bagian "Sumber Masukan Proses" dulu menimpa deskripsi tahap proses.
        _, g, _ = ekspor("contoh_raster.xml")
        desk = [ps.findtext("%s/{%s}CharacterString" % (q("description"), GCO)) for ps in g.iter(q("LI_ProcessStep"))]
        self.assertIn("Digitasi batas administrasi", desk)

    def test_bolak_balik_lewat_importer(self):
        asli, g, _ = ekspor("contoh_lengkap.xml")
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, "hasil.xml")
            gmd_exporter.save_gmd_to_file(g, f)
            balik = gmd_importer.convert_gmd_to_iso3(f, os.path.join(HERE, "template.xml"))

        def isian(root):
            out = set()

            def walk(nodes, sid):
                for n in nodes:
                    if isinstance(n, layout.BField) and (n.field.get() or "").strip():
                        out.add((sid, n.key, n.field.get().strip()))
                    elif isinstance(n, layout.BOptional) and n.present:
                        walk(n.nodes, sid)
                    elif isinstance(n, layout.BList):
                        for i in n.instances:
                            walk(i.nodes, sid)
            for s in layout.build(root)[0]:
                walk(s.nodes, s.id)
            return out

        a, b = isian(asli), isian(balik)
        for kunci in ("dataTitle", "dataAbstract", "lineageStatement", "otherConstraints",
                      "useLimitation", "measure", "specificUsage", "schemaGraphicsURL"):
            nilai_asli = {v for (s, k, v) in a if k == kunci}
            self.assertTrue(nilai_asli, kunci)
            self.assertEqual(nilai_asli, {v for (s, k, v) in b if k == kunci}, kunci)


if __name__ == "__main__":
    unittest.main()
