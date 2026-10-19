"""Penyesuaian struktur XML agar dapat dibaca penuh oleh BIG Metadata Editor.

Editor BIG membaca XML dengan selector turunan (descendant) pada struktur miliknya sendiri, yang pada beberapa
blok TIDAK sama dengan skema ISO 19115-3 resmi (mis. MD_Georectified di dalam MD_GridSpatialRepresentation,
`mrl:Scope`, `mrl:processParameter`, `gml:GM_Point`). Fungsi `to_big` menghasilkan salinan XML dengan struktur
tersebut. Hasilnya dimaksudkan untuk diimpor ke editor BIG, bukan untuk validasi XSD ketat.
"""
import copy
import xml.etree.ElementTree as ET

from .model import local

NS = {
    "mdb": "http://standards.iso.org/iso/19115/-3/mdb/2.0",
    "msr": "http://standards.iso.org/iso/19115/-3/msr/2.0",
    "mrc": "http://standards.iso.org/iso/19115/-3/mrc/2.0",
    "mrl": "http://standards.iso.org/iso/19115/-3/mrl/2.0",
    "gco": "http://standards.iso.org/iso/19115/-3/gco/1.0",
    "gml": "http://www.opengis.net/gml/3.2",
}


def q(p, n):
    return "{%s}%s" % (NS[p], n)


def _first_text(el, name):
    for e in el.iter():
        if local(e.tag) == name:
            return "".join(e.itertext()).strip()
    return ""


def _steps(r):
    for ps in r.iter(q("mrl", "LE_ProcessStep")):
        for c in list(ps):
            n = local(c.tag)
            if n == "stepDateTime":
                txt = _first_text(c, "timePosition") or _first_text(c, "DateTime")
                for k in list(c):
                    c.remove(k)
                if txt and "T" not in txt:
                    txt += "T00:00:00"
                ET.SubElement(c, q("gco", "DateTime")).text = txt
            elif n == "scope":
                c.tag = q("mrl", "Scope")
            elif n == "source":
                for cls in c:
                    if local(cls.tag) == "LI_Source":
                        cls.tag = q("mrl", "LE_Source")
            elif n == "output":
                for cls in c:
                    for sub in cls:
                        if local(sub.tag) == "sourceCitation":
                            sub.tag = q("mrl", "OutputCitation")
                    for nom in cls.iter(q("mrl", "LE_NominalResolution")):
                        if nom.find(q("mrl", "scanningResolution")) is None:
                            g = nom.find(q("mrl", "groundResolution"))
                            if g is not None:
                                sc = copy.deepcopy(g)
                                sc.tag = q("mrl", "scanningResolution")
                                nom.insert(0, sc)
        for rt in ps.iter(q("mrl", "runTimeParameters")):
            txt = _first_text(rt, "CharacterString") or _first_text(rt, "Record")
            for k in list(rt):
                rt.remove(k)
            ET.SubElement(rt, q("gco", "Record")).text = txt
        for prm in ps.iter(q("mrl", "parameter")):
            prm.tag = q("mrl", "processParameter")
            for d in prm.iter(q("mrl", "LE_ParameterDirection")):
                d.tag = q("mrl", "LE_ParameterDirectionCode")
                d.set("codeListValue", (d.text or "").strip())


def _gpoint(el):
    for p in el.iter(q("gml", "Point")):
        p.tag = q("gml", "GM_Point")


def _spatial(r):
    infos = [c for c in r if local(c.tag) == "spatialRepresentationInfo" and len(c)]
    gr = next((c for c in infos if local(c[0].tag) == "MD_Georectified"), None)
    gf = next((c for c in infos if local(c[0].tag) == "MI_Georeferenceable"), None)
    if gr is None and gf is None:
        return
    src = (gr if gr is not None else gf)[0]
    new = ET.Element(q("mdb", "spatialRepresentationInfo"))
    grid = ET.SubElement(new, q("msr", "MD_GridSpatialRepresentation"))
    for c in src:
        if local(c.tag) in ("numberOfDimensions", "axisDimensionProperties", "cellGeometry",
                            "transformationParameterAvailability"):
            grid.append(copy.deepcopy(c))
    inner = ET.SubElement(grid, q("msr", "MD_Georectified"))
    if gr is not None:
        for c in gr[0]:
            n = local(c.tag)
            if n in ("checkPointAvailability", "checkPointDescription", "transformationDimensionDescription",
                     "transformationDimensionMapping"):
                inner.append(copy.deepcopy(c))
            elif n in ("cornerPoints", "centrePoint"):
                cc = copy.deepcopy(c)
                _gpoint(cc)
                inner.append(cc)
            elif n == "pointInPixel":
                cc = copy.deepcopy(c)
                cc.tag = q("msr", "pointPixel")
                inner.append(cc)
    if gf is not None:
        for c in gf[0]:
            if local(c.tag) == "geolocationInformation":
                for coll in c:
                    cc = copy.deepcopy(coll)
                    for acc in cc.iter(q("msr", "accuracyReport")):
                        txt = _first_text(acc, "statement")
                        for k in list(acc):
                            acc.remove(k)
                        ET.SubElement(acc, q("gco", "Record")).text = txt
                    inner.append(cc)
    idx = min(list(r).index(x) for x in (gr, gf) if x is not None)
    for x in (gr, gf):
        if x is not None:
            r.remove(x)
    r.insert(idx, new)


RANGE = {"sequenceIdentifier", "description", "name"}
SAMPLE = {"maxValue", "minValue", "units", "scaleFactor", "offset", "meanValue", "numberOfValues",
          "standardDeviation", "otherPropertyType", "otherProperty", "bitsPerValue"}


def _bands(r):
    for att in r.iter(q("mrc", "attribute")):
        for band in [c for c in att if local(c.tag) == "MD_Band"]:
            rd, sd, bd = [], [], []
            for ch in list(band):
                n = local(ch.tag)
                (rd if n in RANGE else sd if n in SAMPLE else bd).append(ch)
            att.remove(band)
            e_rd = ET.SubElement(att, q("mrc", "MD_RangeDimension"))
            e_rd.extend(rd)
            if sd or bd:
                e_sd = ET.SubElement(e_rd, q("mrc", "MD_SampleDimension"))
                e_sd.extend(sd)
                if bd:
                    ET.SubElement(e_sd, q("mrc", "MD_Band")).extend(bd)


def _coverage_to_image(r):
    if any(True for _ in r.iter(q("mrc", "MD_ImageDescription"))):
        return
    for c in r:
        if local(c.tag) == "contentInfo" and len(c) and local(c[0].tag) == "MD_CoverageDescription":
            c[0].tag = q("mrc", "MD_ImageDescription")
            break


def normalize_steps(root):
    """Pastikan blok Tahap Proses (stepDateTime -> gco:DateTime dan scope -> Scope) selalu terbaca sistem BIG."""
    _steps(root)
    return root


def to_big(root):
    """Salinan `root` dengan struktur yang dibaca editor BIG."""
    r = copy.deepcopy(root)
    _steps(r)
    _spatial(r)
    _coverage_to_image(r)
    _bands(r)
    return r
