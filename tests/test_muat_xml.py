"""Test muat berkas XML (model.load) — respons CSW dibuka sampai MD_Metadata di dalamnya. Tanpa QGIS.
    python -m unittest discover -s iso19115_metadata_editor/tests -t .
"""
import copy
import os
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET  # nosec B405

from .. import gmd_importer, layout, model

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSW = "http://www.opengis.net/cat/csw/2.0.2"


def isian_terisi(root):
    """Jumlah isian Form BIG yang terisi — nol bila formulir tidak menemukan metadatanya."""
    n = 0

    def jalan(nodes):
        nonlocal n
        for x in nodes:
            if isinstance(x, layout.BField) and x.field is not None and (x.field.get() or "").strip():
                n += 1
            elif isinstance(x, layout.BOptional) and x.present:
                jalan(x.nodes)
            elif isinstance(x, layout.BList):
                for inst in x.instances:
                    jalan(inst.nodes)
    for s in layout.build(root)[0]:
        jalan(s.nodes)
    return n


class MuatResponsCSW(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="geomdb-muat-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.lepas = os.path.join(HERE, "contoh_lengkap.xml")
        self.md = model.load(self.lepas)[0]

    def tulis_csw(self, nama, records, hasil_pencarian=False):
        akar = ET.Element("{%s}%s" % (CSW, nama))
        wadah = ET.SubElement(akar, "{%s}SearchResults" % CSW) if hasil_pencarian else akar
        for _ in range(records):
            wadah.append(copy.deepcopy(self.md))
        path = os.path.join(self.tmp, "csw.xml")
        ET.ElementTree(akar).write(path, encoding="utf-8", xml_declaration=True)
        return path

    def test_getrecordbyid_19115_3_dimuat_md_metadata(self):
        root, fixes = model.load(self.tulis_csw("GetRecordByIdResponse", 1))
        self.assertEqual(root.tag, self.md.tag)
        self.assertTrue(any("GetRecordByIdResponse" in f for f in fixes), fixes)
        judul = [s.title for s in model.build_sections(root)]
        self.assertIn("Identifier Metadata", judul)      # tampilan "Semua elemen ISO": per bagian, bukan satu "MD_Metadata"
        self.assertNotIn("MD_Metadata", judul)
        self.assertGreater(isian_terisi(root), 0)        # tampilan "Form BIG" menemukan isiannya
        self.assertEqual(isian_terisi(root), isian_terisi(self.md))

    def test_getrecords_banyak_record_ambil_pertama(self):
        root, fixes = model.load(self.tulis_csw("GetRecordsResponse", 2, hasil_pencarian=True))
        self.assertEqual(model.local(root.tag), "MD_Metadata")
        self.assertTrue(any("2 record" in f for f in fixes), fixes)

    def test_simpan_tanpa_pembungkus_csw(self):
        root, _ = model.load(self.tulis_csw("GetRecordByIdResponse", 1))
        keluar = os.path.join(self.tmp, "hasil.xml")
        model.save(root, keluar)
        self.assertEqual(ET.parse(keluar).getroot().tag, self.md.tag)  # nosec B314

    def test_csw_geonode_19139_terdeteksi_gmd(self):
        root, fixes = model.load(os.path.join(HERE, "tests", "fixtures", "csw_template_geonode.xml"))
        self.assertTrue(gmd_importer.is_gmd(root))       # lalu dikonversi ke 19115-3 seperti berkas gmd lepas
        self.assertTrue(any("GetRecordByIdResponse" in f for f in fixes), fixes)

    def test_berkas_lepas_tanpa_catatan(self):
        root, fixes = model.load(self.lepas)
        self.assertEqual(model.local(root.tag), "MD_Metadata")
        self.assertEqual(fixes, [])


if __name__ == "__main__":
    unittest.main()
