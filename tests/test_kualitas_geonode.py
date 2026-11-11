"""Test regresi: laporan kualitas berjenis & hasil kuantitatif (ISO 19139 bolak-balik), dan XML buatan GeoNode
yang dibuka lewat "Buka XML Metadata..." — tanpa QGIS.

    python -m unittest discover -s iso19115_metadata_editor/tests -t .
"""
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET  # nosec B405

from .. import gmd_exporter, gmd_importer, layout, model

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(HERE, "template.xml")
GMD = gmd_exporter.GMD
GCO = gmd_exporter.GCO

# Dulu: setiap laporan masuk sebagai DQ_DomainConsistency + DQ_ConformanceResult (pilihan pertama), dan hasil
# kuantitatif terekspor kosong (gmd:result nilReason="missing") — nilai & satuannya hilang.
GMD_LAPORAN = """<gmd:MD_Metadata xmlns:gmd="http://www.isotc211.org/2005/gmd" xmlns:gco="http://www.isotc211.org/2005/gco"
    xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:xlink="http://www.w3.org/1999/xlink">
  <gmd:fileIdentifier><gco:CharacterString>uji-kualitas</gco:CharacterString></gmd:fileIdentifier>
  <gmd:dataQualityInfo><gmd:DQ_DataQuality>
    <gmd:scope><gmd:DQ_Scope><gmd:level><gmd:MD_ScopeCode codeList="x" codeListValue="dataset">dataset</gmd:MD_ScopeCode></gmd:level></gmd:DQ_Scope></gmd:scope>
    <gmd:report><gmd:DQ_DomainConsistency>
      <gmd:nameOfMeasure><gco:CharacterString>Pola kode wilayah</gco:CharacterString></gmd:nameOfMeasure>
      <gmd:result><gmd:DQ_ConformanceResult>
        <gmd:specification><gmd:CI_Citation><gmd:title><gco:CharacterString>Kode Kemendagri</gco:CharacterString></gmd:title>
          <gmd:date gco:nilReason="missing"/></gmd:CI_Citation></gmd:specification>
        <gmd:explanation><gco:CharacterString>49 dari 49 sesuai</gco:CharacterString></gmd:explanation>
        <gmd:pass><gco:Boolean>true</gco:Boolean></gmd:pass>
      </gmd:DQ_ConformanceResult></gmd:result>
    </gmd:DQ_DomainConsistency></gmd:report>
    <gmd:report><gmd:DQ_CompletenessOmission>
      <gmd:nameOfMeasure><gco:CharacterString>Desa tidak terpetakan</gco:CharacterString></gmd:nameOfMeasure>
      <gmd:result><gmd:DQ_QuantitativeResult>
        <gmd:valueUnit><gml:UnitDefinition gml:id="u1"><gml:identifier codeSpace="GeoMDB">desa</gml:identifier>
          <gml:name>desa</gml:name></gml:UnitDefinition></gmd:valueUnit>
        <gmd:value><gco:Record>3</gco:Record></gmd:value>
      </gmd:DQ_QuantitativeResult></gmd:result>
    </gmd:DQ_CompletenessOmission></gmd:report>
    <gmd:report><gmd:DQ_AbsoluteExternalPositionalAccuracy>
      <gmd:nameOfMeasure><gco:CharacterString>RMSE horizontal</gco:CharacterString></gmd:nameOfMeasure>
      <gmd:result><gmd:DQ_QuantitativeResult>
        <gmd:valueUnit xlink:href="http://www.opengis.net/def/uom/EPSG/0/9001"/>
        <gmd:value><gco:Record>2.5</gco:Record></gmd:value>
      </gmd:DQ_QuantitativeResult></gmd:result>
    </gmd:DQ_AbsoluteExternalPositionalAccuracy></gmd:report>
  </gmd:DQ_DataQuality></gmd:dataQualityInfo>
</gmd:MD_Metadata>"""


def laporan_formulir(root):
    """[(kelas laporan, [(kelas hasil, isian)])] dari formulir (tahap 7)."""
    s7 = {s.id: s for s in layout.build(root)[0]}[7]
    out = []

    def cari(nodes):
        for n in nodes:
            if isinstance(n, layout.BList) and getattr(n, "path", "") == "dataQualityInfo/report":
                return n
            if isinstance(n, layout.BOptional) and n.present:
                r = cari(n.nodes)
                if r is not None:
                    return r
        return None

    for inst in cari(s7.nodes).instances:
        hasil = []
        for n in inst.nodes:
            if isinstance(n, layout.BList) and getattr(n, "path", "") == "result":
                hasil = [(next(c.tag.rsplit("}", 1)[-1] for c in r.el), gmd_exporter._collect_dict_from_nodes(r.nodes))
                         for r in n.instances]
        out.append((next(c.tag.rsplit("}", 1)[-1] for c in inst.el), hasil))
    return out


class LaporanKualitas(unittest.TestCase):

    def setUp(self):
        self.root = gmd_importer.convert_gmd_to_iso3(ET.fromstring(GMD_LAPORAN), TEMPLATE)  # nosec B314

    def test_jenis_laporan_dan_hasil_terbaca(self):
        lap = laporan_formulir(self.root)
        self.assertEqual([k for k, _ in lap], ["DQ_DomainConsistency", "DQ_CompletenessOmission",
                                               "DQ_AbsoluteExternalPositionalAccuracy"])
        self.assertEqual([[h for h, _ in hs] for _, hs in lap],
                         [["DQ_ConformanceResult"], ["DQ_QuantitativeResult"], ["DQ_QuantitativeResult"]])
        self.assertEqual(lap[0][1][0][1].get("explanation"), "49 dari 49 sesuai")
        self.assertEqual({k: lap[1][1][0][1].get(k) for k in ("quantitativeValue", "quantitativeUnit")},
                         {"quantitativeValue": "3", "quantitativeUnit": "desa"})
        self.assertEqual(lap[2][1][0][1].get("quantitativeUnitCode"), "http://www.opengis.net/def/uom/EPSG/0/9001")
        self.assertEqual(lap[2][1][0][1].get("quantitativeValue"), "2.5")

    def test_hasil_kuantitatif_terekspor_dan_bolak_balik(self):
        catatan = []
        g = gmd_exporter.export_to_gmd(self.root, catatan=catatan)
        reps = [list(r)[0] for r in g.iter("{%s}report" % GMD)]
        self.assertEqual([r.tag.rsplit("}", 1)[-1] for r in reps],
                         ["DQ_DomainConsistency", "DQ_CompletenessOmission", "DQ_AbsoluteExternalPositionalAccuracy"])
        kuant = list(g.iter("{%s}DQ_QuantitativeResult" % GMD))
        self.assertEqual([q.findtext("{%s}value/{%s}Record" % (GMD, GCO)) for q in kuant], ["3", "2.5"])
        # urutan xs:sequence: valueUnit (wajib) sebelum value
        self.assertEqual([c.tag.rsplit("}", 1)[-1] for c in kuant[0]], ["valueUnit", "value"])
        self.assertEqual(kuant[0].find(".//{%s}name" % gmd_exporter.GML).text, "desa")
        self.assertEqual(kuant[1].find("{%s}valueUnit" % GMD).get("{%s}href" % gmd_exporter.XLINK),
                         "http://www.opengis.net/def/uom/EPSG/0/9001")
        self.assertFalse([r for r in g.iter("{%s}result" % GMD) if r.get("{%s}nilReason" % GCO)], "hasil kosong")
        # bolak-balik: formulir dari hasil ekspor = formulir semula
        balik = gmd_importer.convert_gmd_to_iso3(g, TEMPLATE)
        self.assertEqual(laporan_formulir(balik), laporan_formulir(self.root))


class EksporBerkas(unittest.TestCase):
    """Satu isi, dua tujuan: Palapa/CSW tanpa deklarasi; GeoNode (Upload Metadata) wajib deklarasi tanpa encoding."""

    def simpan(self, **kw):
        root, _ = model.load(os.path.join(HERE, "contoh_lengkap.xml"))
        g = gmd_exporter.export_to_gmd(root, catatan=[])
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, "hasil.xml")
            gmd_exporter.save_gmd_to_file(g, f, **kw)
            with open(f, encoding="utf-8") as fh:
                return fh.read()

    def test_palapa_tanpa_deklarasi(self):
        self.assertTrue(self.simpan().startswith("<gmd:MD_Metadata"))

    def test_geonode_dengan_deklarasi_tanpa_encoding(self):
        teks = self.simpan(deklarasi=True)
        baris1, sisa = teks.split("\n", 1)
        self.assertEqual(baris1, '<?xml version="1.0"?>')
        self.assertTrue(sisa.startswith("<gmd:MD_Metadata"))
        # GeoNode yang mem-parse unggahan sebagai teks: teks berdeklarasi encoding ditolak lxml/ElementTree
        ET.fromstring(teks)  # nosec B314
        self.assertEqual(sisa, self.simpan())


class XmlGeoNode(unittest.TestCase):

    def setUp(self):
        akar = ET.parse(os.path.join(HERE, "tests", "fixtures", "csw_template_geonode.xml")).getroot()  # nosec B314
        self.gn = akar if akar.tag == "{%s}MD_Metadata" % GMD else akar.find(".//{%s}MD_Metadata" % GMD)

    def test_dikenali(self):
        self.assertTrue(gmd_importer.buatan_geonode(self.gn))
        root, _ = model.load(os.path.join(HERE, "contoh_lengkap.xml"))
        self.assertFalse(gmd_importer.buatan_geonode(gmd_exporter.export_to_gmd(root, catatan=[])))

    def test_teks_pengisi_tidak_masuk_formulir(self):
        self.assertIn("No information provided", ET.tostring(self.gn, encoding="unicode"))
        root = gmd_importer.convert_gmd_to_iso3(self.gn, TEMPLATE, bersih=True)
        nilai = set()

        def walk(nodes):
            for n in nodes:
                if isinstance(n, layout.BField) and (n.field.get() or "").strip():
                    nilai.add(n.field.get().strip())
                elif isinstance(n, layout.BOptional) and n.present:
                    walk(n.nodes)
                elif isinstance(n, layout.BList):
                    for i in n.instances:
                        walk(i.nodes)
        for s in layout.build(root)[0]:
            walk(s.nodes)
        self.assertFalse(nilai & {"None", "No abstract provided", "No information provided"})
        self.assertNotIn("Metadata Author", nilai)


if __name__ == "__main__":
    unittest.main()
