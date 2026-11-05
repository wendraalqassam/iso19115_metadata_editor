"""Penyesuaian struktur XML agar dapat dibaca penuh oleh BIG Metadata Editor.

Editor BIG membaca XML dengan selector turunan (descendant) pada struktur miliknya sendiri, yang pada beberapa
blok TIDAK sama dengan skema ISO 19115-3 resmi (mis. MD_Georectified di dalam MD_GridSpatialRepresentation,
`mrl:Scope`, `mrl:processParameter`, `gml:GM_Point`). Fungsi `to_big` menghasilkan salinan XML dengan struktur
tersebut. Hasilnya dimaksudkan untuk diimpor ke editor BIG, bukan untuk validasi XSD ketat.
"""
import copy
import xml.etree.ElementTree as ET  # nosec B405

from .model import local, urutkan

NS = {
    "mdb": "http://standards.iso.org/iso/19115/-3/mdb/2.0",
    "msr": "http://standards.iso.org/iso/19115/-3/msr/2.0",
    "mrc": "http://standards.iso.org/iso/19115/-3/mrc/2.0",
    "mrl": "http://standards.iso.org/iso/19115/-3/mrl/2.0",
    "gco": "http://standards.iso.org/iso/19115/-3/gco/1.0",
    "gml": "http://www.opengis.net/gml/3.2",
    "mri": "http://standards.iso.org/iso/19115/-3/mri/1.0",
    "lan": "http://standards.iso.org/iso/19115/-3/lan/1.0",
}


def q(p, n):
    return "{%s}%s" % (NS[p], n)


def _first_text(el, name):
    for e in el.iter():
        if local(e.tag) == name:
            return "".join(e.itertext()).strip()
    return ""


def _catat(catatan, teks):
    if catatan is not None and teks not in catatan:
        catatan.append(teks)


def _steps(r, catatan=None):
    for ps in r.iter(q("mrl", "LE_ProcessStep")):
        for c in list(ps):
            n = local(c.tag)
            if n == "stepDateTime":
                _catat(catatan, "Waktu tahap proses ditulis gco:DateTime (standar ISO 19115-3: gml:TimeInstant).")
                txt = _first_text(c, "timePosition") or _first_text(c, "DateTime")
                for k in list(c):
                    c.remove(k)
                if txt and "T" not in txt:
                    txt += "T00:00:00"
                ET.SubElement(c, q("gco", "DateTime")).text = txt
            elif n == "scope":
                c.tag = q("mrl", "Scope")
                _catat(catatan, "Cakupan tahap proses ditulis mrl:Scope (standar: mrl:scope).")
            elif n == "source":
                for cls in c:
                    if local(cls.tag) == "LI_Source":
                        cls.tag = q("mrl", "LE_Source")
            elif n == "output":
                for cls in c:
                    for sub in cls:
                        if local(sub.tag) == "sourceCitation":
                            sub.tag = q("mrl", "OutputCitation")
                            _catat(catatan, "Sitasi keluaran proses ditulis mrl:OutputCitation (standar: mrl:sourceCitation).")
                    for nom in cls.iter(q("mrl", "LE_NominalResolution")):
                        if nom.find(q("mrl", "scanningResolution")) is None:
                            g = nom.find(q("mrl", "groundResolution"))
                            if g is not None:
                                sc = copy.deepcopy(g)
                                sc.tag = q("mrl", "scanningResolution")
                                nom.insert(0, sc)
                                _catat(catatan, "Resolusi keluaran proses ditulis ganda (scanningResolution + "
                                                "groundResolution); standar hanya mengizinkan salah satu.")
        for rt in ps.iter(q("mrl", "runTimeParameters")):
            txt = _first_text(rt, "CharacterString") or _first_text(rt, "Record")
            for k in list(rt):
                rt.remove(k)
            ET.SubElement(rt, q("gco", "Record")).text = txt
            _catat(catatan, "Parameter runtime ditulis gco:Record (standar: gco:CharacterString).")
        for prm in ps.iter(q("mrl", "parameter")):
            prm.tag = q("mrl", "processParameter")
            _catat(catatan, "Parameter pengolahan ditulis mrl:processParameter dengan LE_ParameterDirectionCode "
                            "(standar: mrl:parameter, LE_ParameterDirection).")
            for d in prm.iter(q("mrl", "LE_ParameterDirection")):
                d.tag = q("mrl", "LE_ParameterDirectionCode")
                d.set("codeListValue", (d.text or "").strip())


def _gpoint(el):
    for p in el.iter(q("gml", "Point")):
        p.tag = q("gml", "GM_Point")


def _spatial(r, catatan=None):
    infos = [c for c in r if local(c.tag) == "spatialRepresentationInfo" and len(c)]
    gr = next((c for c in infos if local(c[0].tag) == "MD_Georectified"), None)
    gf = next((c for c in infos if local(c[0].tag) == "MI_Georeferenceable"), None)
    if gr is None and gf is None:
        return
    src = (gr if gr is not None else gf)[0]
    _catat(catatan, "Grid/raster: MD_Georectified bersarang di dalam MD_GridSpatialRepresentation dan titik ditulis "
                    "gml:GM_Point (standar: MD_Georectified/MI_Georeferenceable langsung, gml:Point). Bagian ini tidak "
                    "terbaca utuh bila berkas dibuka kembali di GeoMDB — simpan juga versi tanpa mode BIG.")
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


def _bands(r, catatan=None):
    for att in r.iter(q("mrc", "attribute")):
        for band in [c for c in att if local(c.tag) == "MD_Band"]:
            rd, sd, bd = [], [], []
            for ch in list(band):
                n = local(ch.tag)
                (rd if n in RANGE else sd if n in SAMPLE else bd).append(ch)
            att.remove(band)
            _catat(catatan, "Band dipecah menjadi MD_RangeDimension › MD_SampleDimension › MD_Band (standar: MD_Band). "
                            "Bagian ini tidak terbaca utuh bila berkas dibuka kembali di GeoMDB.")
            e_rd = ET.SubElement(att, q("mrc", "MD_RangeDimension"))
            e_rd.extend(rd)
            if sd or bd:
                e_sd = ET.SubElement(e_rd, q("mrc", "MD_SampleDimension"))
                e_sd.extend(sd)
                if bd:
                    ET.SubElement(e_sd, q("mrc", "MD_Band")).extend(bd)


def _coverage_to_image(r, catatan=None):
    if any(True for _ in r.iter(q("mrc", "MD_ImageDescription"))):
        return
    for c in r:
        if local(c.tag) == "contentInfo" and len(c) and local(c[0].tag) == "MD_CoverageDescription":
            c[0].tag = q("mrc", "MD_ImageDescription")
            _catat(catatan, "Deskripsi cakupan (MD_CoverageDescription) ditulis sebagai MD_ImageDescription.")
            break


def normalize_steps(root, catatan=None):
    """Pastikan blok Tahap Proses (stepDateTime -> gco:DateTime dan scope -> Scope) selalu terbaca sistem BIG.
    `catatan` (opsional, list) diisi penyimpangan dari ISO 19115-3 yang benar-benar diterapkan."""
    _steps(root, catatan)
    return root


def to_big(root, catatan=None):
    """Salinan `root` dengan struktur yang dibaca editor BIG. `catatan` (opsional, list) diisi
    penyimpangan dari ISO 19115-3 yang benar-benar diterapkan."""
    r = copy.deepcopy(root)
    _steps(r, catatan)
    _spatial(r, catatan)
    _coverage_to_image(r, catatan)
    _bands(r, catatan)
    return r


def ke_standar(root):
    """Kebalikan penyesuaian BIG pada tahap proses & titik grid — dari berkas BIG atau simpanan lama
    plugin — lalu urutkan properti menurut XSD, agar hasil simpan sesuai ISO 19115-3. Dipakai saat
    opsi "Kompatibel Sistem BIG" tidak dicentang."""
    n = 0
    for ps in list(root.iter(q("mrl", "LE_ProcessStep"))) + list(root.iter(q("mrl", "LI_ProcessStep"))):
        for c in list(ps):
            nama = local(c.tag)
            if nama == "stepDateTime":
                dt = next((k for k in c if local(k.tag) == "DateTime"), None)
                if dt is not None:
                    txt = (dt.text or "").strip()
                    c.remove(dt)
                    if txt:
                        n += 1
                        ti = ET.SubElement(c, q("gml", "TimeInstant"))
                        ti.set(q("gml", "id"), "stepDateTime-%d" % n)
                        ET.SubElement(ti, q("gml", "timePosition")).text = txt
            elif nama == "Scope":
                c.tag = q("mrl", "scope")
        for oc in ps.iter(q("mrl", "OutputCitation")):
            oc.tag = q("mrl", "sourceCitation")
        for nom in ps.iter(q("mrl", "LE_NominalResolution")):
            sc, gr = nom.find(q("mrl", "scanningResolution")), nom.find(q("mrl", "groundResolution"))
            if sc is not None and gr is not None:  # salinan groundResolution buatan mode BIG
                nom.remove(sc)
    for rt in root.iter(q("mrl", "runTimeParameters")):
        for k in rt:
            if local(k.tag) == "Record":
                k.tag = q("gco", "CharacterString")
    for prm in root.iter(q("mrl", "processParameter")):
        prm.tag = q("mrl", "parameter")
        for d in prm.iter(q("mrl", "LE_ParameterDirectionCode")):
            d.tag = q("mrl", "LE_ParameterDirection")
            for a in ("codeList", "codeListValue"):
                d.attrib.pop(a, None)
    for pt in root.iter(q("gml", "GM_Point")):
        pt.tag = q("gml", "Point")
    # Band dengan boundMin/boundMax wajib punya boundUnits (Schematron rule.mrc.bandunit). Formulir
    # menetapkan satuannya nanometer (label "Bound Min/Max (nm)") tanpa isian tersendiri.
    for i, band in enumerate(root.iter(q("mrc", "MD_Band")), 1):
        batas = [band.find(q("mrc", t)) for t in ("boundMin", "boundMax")]
        if not any(b is not None and "".join(b.itertext()).strip() for b in batas):
            continue
        bu = band.find(q("mrc", "boundUnits"))
        if bu is not None and "".join(bu.itertext()).strip():
            continue
        if bu is None:
            bu = ET.SubElement(band, q("mrc", "boundUnits"))
        for k in list(bu):
            bu.remove(k)
        ud = ET.SubElement(bu, q("gml", "UnitDefinition"))
        ud.set(q("gml", "id"), "satuan-batas-band-%d" % i)
        idf = ET.SubElement(ud, q("gml", "identifier"))
        idf.set("codeSpace", "http://www.opengis.net/def/uom/UCUM/")
        idf.text = "nm"
    _warisi_locale_data(root)
    urutkan(root)
    return root


def _kode_locale(loc, prop):
    el = loc.find("%s/*" % q("lan", prop)) if loc is not None else None
    return (el.get("codeListValue") or (el.text or "")).strip() if el is not None else ""


def _warisi_locale_data(root):
    """Formulir gaya BIG memakai satu bahasa untuk metadata & data (exporter ISO 19139 juga begitu), tanpa
    kolom bahasa data tersendiri. Bila bahasa data kosong, warisi locale metadata — Schematron ISO 19115-3
    (rule.mri.defaultlocalewhenhastext) mewajibkan bahasa sumber daya; dulu formulir dari Template Kosong
    atau hasil impor GeoNode gagal di sini."""
    meta = root.find("%s/%s" % (q("mdb", "defaultLocale"), q("lan", "PT_Locale")))
    if not _kode_locale(meta, "language"):
        return
    for di in root.iter(q("mri", "MD_DataIdentification")):
        dl = di.find(q("mri", "defaultLocale"))
        if _kode_locale(dl.find(q("lan", "PT_Locale")) if dl is not None else None, "language"):
            continue
        if dl is not None:
            di.remove(dl)
        dl = ET.SubElement(di, q("mri", "defaultLocale"))  # posisinya diatur urutkan()
        dl.append(copy.deepcopy(meta))
