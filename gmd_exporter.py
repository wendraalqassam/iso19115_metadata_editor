"""Modul ekspor ISO 19139 (namespace http://www.isotc211.org/2005/gmd).

Mengambil data metadata aktif (ISO 19115-3) dari EditorDialog/model dan
menghasilkan XML berbasis standar ISO 19139 menggunakan template gmd_template.xml.
"""
import copy
import datetime
import json
import os
import re
import xml.etree.ElementTree as ET  # nosec B405

from . import kesesuaian, layout

HERE = os.path.dirname(__file__)
GMD_TEMPLATE = os.path.join(HERE, "gmd_template.xml")

GMD = "http://www.isotc211.org/2005/gmd"
GCO = "http://www.isotc211.org/2005/gco"
# Skema resmi ISO 19139 (gmd 1.0) mengimpor GML 3.2; OWSLib (GeoNode/pycsw) membaca keduanya.
GML = "http://www.opengis.net/gml/3.2"
GTS = "http://www.isotc211.org/2005/gts/"
XLINK = "http://www.w3.org/1999/xlink"
XSI = "http://www.w3.org/2001/XMLSchema-instance"

NS = {
    "gmd": GMD,
    "gco": GCO,
    "gml": GML,
    "gts": GTS,
    "xlink": XLINK,
    "xsi": XSI,
}


def register_gmd_namespaces():
    """Memastikan namespace standar ISO 19139 terdaftar penuh di ElementTree global.
    Ini krusial agar tidak tertimpa oleh namespace ISO 19115-3 (seperti gco 1.0)
    yang dapat menyebabkan tag berubah menjadi ns2:CharacterString."""
    for prefix, uri in NS.items():
        ET.register_namespace(prefix, uri)


register_gmd_namespaces()


def _q(ns, tag):
    return f"{{{ns}}}{tag}"


def _clean_str(text):
    if text is None:
        return ""
    s = str(text).strip()
    # Bersihkan jika ada tag XML yang tertulis mentah
    s = re.sub(r"<[^>]+>", "", s).strip()
    return s


def _set_char(parent, tag_name, text):
    s = _clean_str(text)
    if not s:
        return None
    el = parent.find(_q(GMD, tag_name))
    if el is None:
        el = ET.SubElement(parent, _q(GMD, tag_name))
    cs = el.find(_q(GCO, "CharacterString"))
    if cs is None:
        cs = ET.SubElement(el, _q(GCO, "CharacterString"))
    cs.text = s
    return el


def _set_code(parent, tag_name, code_class, code_value, codelist_uri="./resources/codeList.xml"):
    val = _clean_str(code_value)
    if not val:
        return None
    el = parent.find(_q(GMD, tag_name))
    if el is None:
        el = ET.SubElement(parent, _q(GMD, tag_name))
    cc = el.find(_q(GMD, code_class))
    if cc is None:
        cc = ET.SubElement(el, _q(GMD, code_class))
    cc.set("codeList", f"{codelist_uri}#{code_class}")
    cc.set("codeListValue", val)
    cc.text = val
    return el


def _set_url(parent, tag_name, url_str):
    s = _clean_str(url_str)
    if not s:
        return None
    el = parent.find(_q(GMD, tag_name))
    if el is None:
        el = ET.SubElement(parent, _q(GMD, tag_name))
    for c in list(el):
        el.remove(c)
    u = ET.SubElement(el, _q(GMD, "URL"))
    u.text = s
    return el


def _build_contact_element(tag_name, contact_data):
    """Membangun elemen kontak gmd:CI_ResponsibleParty sesuai standar ISO 19139."""
    wrapper = ET.Element(_q(GMD, tag_name))
    rp = ET.SubElement(wrapper, _q(GMD, "CI_ResponsibleParty"))

    ind = _clean_str(contact_data.get("individual"))
    org = _clean_str(contact_data.get("organization"))
    pos = _clean_str(contact_data.get("position"))
    role = _clean_str(contact_data.get("role")) or "pointOfContact"

    # individualName
    in_el = ET.SubElement(rp, _q(GMD, "individualName"))
    if ind:
        cs = ET.SubElement(in_el, _q(GCO, "CharacterString"))
        cs.text = ind
    else:
        in_el.set(_q(GCO, "nilReason"), "missing")

    # organisationName
    org_el = ET.SubElement(rp, _q(GMD, "organisationName"))
    if org:
        cs = ET.SubElement(org_el, _q(GCO, "CharacterString"))
        cs.text = org
    else:
        org_el.set(_q(GCO, "nilReason"), "missing")

    # positionName
    pos_el = ET.SubElement(rp, _q(GMD, "positionName"))
    if pos:
        cs = ET.SubElement(pos_el, _q(GCO, "CharacterString"))
        cs.text = pos
    else:
        pos_el.set(_q(GCO, "nilReason"), "missing")

    # contactInfo
    ci_wrap = ET.SubElement(rp, _q(GMD, "contactInfo"))
    ci = ET.SubElement(ci_wrap, _q(GMD, "CI_Contact"))

    phone = _clean_str(contact_data.get("phone"))
    fax = _clean_str(contact_data.get("fax"))
    if phone or fax:
        p_el = ET.SubElement(ci, _q(GMD, "phone"))
        tel = ET.SubElement(p_el, _q(GMD, "CI_Telephone"))
        if phone:
            v_el = ET.SubElement(tel, _q(GMD, "voice"))
            cs = ET.SubElement(v_el, _q(GCO, "CharacterString"))
            cs.text = phone
        if fax:
            f_el = ET.SubElement(tel, _q(GMD, "facsimile"))
            cs = ET.SubElement(f_el, _q(GCO, "CharacterString"))
            cs.text = fax

    addr_fields = ["address", "city", "province", "postalCode", "country", "email"]
    if any(contact_data.get(k) for k in addr_fields):
        a_el = ET.SubElement(ci, _q(GMD, "address"))
        addr = ET.SubElement(a_el, _q(GMD, "CI_Address"))
        for k, gmd_tag in (
            ("address", "deliveryPoint"),
            ("city", "city"),
            ("province", "administrativeArea"),
            ("postalCode", "postalCode"),
            ("country", "country"),
            ("email", "electronicMailAddress"),
        ):
            v = _clean_str(contact_data.get(k))
            if v:
                sub = ET.SubElement(addr, _q(GMD, gmd_tag))
                cs = ET.SubElement(sub, _q(GCO, "CharacterString"))
                cs.text = v

    hours = _clean_str(contact_data.get("hours"))
    if hours:
        h_el = ET.SubElement(ci, _q(GMD, "hoursOfService"))
        cs = ET.SubElement(h_el, _q(GCO, "CharacterString"))
        cs.text = hours

    instructions = _clean_str(contact_data.get("instructions"))
    if instructions:
        ins_el = ET.SubElement(ci, _q(GMD, "contactInstructions"))
        cs = ET.SubElement(ins_el, _q(GCO, "CharacterString"))
        cs.text = instructions

    # role
    r_el = ET.SubElement(rp, _q(GMD, "role"))
    rc = ET.SubElement(r_el, _q(GMD, "CI_RoleCode"))
    rc.set("codeList", "./resources/codeList.xml#CI_RoleCode")
    rc.set("codeListValue", role)
    rc.text = role

    return wrapper


def _build_online_resource_element(tag_name, url, protocol="", name="", desc="", function="information"):
    res = ET.Element(_q(GMD, tag_name))
    ci = ET.SubElement(res, _q(GMD, "CI_OnlineResource"))
    if url:
        lk = ET.SubElement(ci, _q(GMD, "linkage"))
        u = ET.SubElement(lk, _q(GMD, "URL"))
        u.text = url
    if protocol:
        pr = ET.SubElement(ci, _q(GMD, "protocol"))
        cs = ET.SubElement(pr, _q(GCO, "CharacterString"))
        cs.text = protocol
    if name:
        nm = ET.SubElement(ci, _q(GMD, "name"))
        cs = ET.SubElement(nm, _q(GCO, "CharacterString"))
        cs.text = name
    if desc:
        ds = ET.SubElement(ci, _q(GMD, "description"))
        cs = ET.SubElement(ds, _q(GCO, "CharacterString"))
        cs.text = desc
    if function:
        fn = ET.SubElement(ci, _q(GMD, "function"))
        fc = ET.SubElement(fn, _q(GMD, "CI_OnLineFunctionCode"))
        fc.set("codeList", "./resources/codeList.xml#CI_OnLineFunctionCode")
        fc.set("codeListValue", function)
        fc.text = function
    return res


def _collect_dict_from_nodes(nodes):
    data = {}
    for n in nodes:
        if isinstance(n, layout.BField):
            v = (n.field.get() or "").strip()
            if v:
                data[n.key] = v
        elif isinstance(n, layout.BOptional) and n.present:
            data.update(_collect_dict_from_nodes(n.nodes))
    return data


def _has_list_data(nodes, path_sub):
    """Mengecek apakah ada instance BList dengan path_sub yang memiliki isian non-kosong."""
    for n in nodes:
        if isinstance(n, layout.BList) and path_sub in getattr(n, "path", ""):
            for inst in n.instances:
                if any(_collect_dict_from_nodes(inst.nodes).values()):
                    return True
    return False


def _lokal(tag):
    return tag.rsplit("}", 1)[-1]


def _bidang_langsung(nodes):
    """Isian BField langsung saja. Berbeda dari _collect_dict_from_nodes, isian bagian opsional di
    dalamnya tidak ikut digabung — di tahap proses, kunci seperti `description` milik bagian
    "Sumber Masukan"/"Hasil Keluaran" akan menimpa deskripsi tahap prosesnya sendiri."""
    out = {}
    for n in nodes:
        if isinstance(n, layout.BField):
            v = (n.field.get() or "").strip()
            if v:
                out[n.key] = v
    return out


def _sumber_lineage(src_d, catatan):
    """gmd:source/LI_Source (ISO 19139: description, sourceReferenceSystem, sourceCitation, ...)."""
    wrap = ET.Element(_q(GMD, "source"))
    li_src = ET.SubElement(wrap, _q(GMD, "LI_Source"))
    _set_char(li_src, "description", src_d.get("description"))
    if src_d.get("referenceSystemCode") or src_d.get("referenceSystemCodeSpace"):
        # ISO 19139: MD_ReferenceSystem/referenceSystemIdentifier bertipe RS_Identifier
        rs_id = _anak(li_src, "sourceReferenceSystem", "MD_ReferenceSystem", "referenceSystemIdentifier", "RS_Identifier")
        _set_char(rs_id, "code", src_d.get("referenceSystemCode"))
        _set_char(rs_id, "codeSpace", src_d.get("referenceSystemCodeSpace"))
    if src_d.get("citationTitle") or src_d.get("citationDate"):
        ci_s = _anak(li_src, "sourceCitation", "CI_Citation")
        _set_char(ci_s, "title", src_d.get("citationTitle"))
        if src_d.get("citationDate"):
            ci_d = ET.SubElement(ET.SubElement(ci_s, _q(GMD, "date")), _q(GMD, "CI_Date"))
            _set_date(ci_d, "date", src_d["citationDate"])
            _set_code(ci_d, "dateType", "CI_DateTypeCode", src_d.get("citationDateType") or "creation")
    if src_d.get("spatialResolution"):
        catatan.append("Resolusi spasial sumber data (meter) tidak punya padanan di LI_Source ISO 19139 — tidak diekspor.")
    if src_d.get("metadataTitle"):
        catatan.append("Metadata sumber (sourceMetadata) tidak punya padanan di ISO 19139 — tidak diekspor.")
    return wrap


# Urutan & kewajiban properti tiap kelas ISO 19139: {kelas: [[properti, minOccurs], ...]},
# diturunkan dari XSD resmi gmd 1.0 (urutan xs:sequence termasuk tipe induk; anggota xs:choice
# dicatat minOccurs 0). Dipakai _rapikan() agar keluaran lolos validasi XSD.
_GMD_ORDER = None


def _gmd_order():
    global _GMD_ORDER
    if _GMD_ORDER is None:
        with open(os.path.join(HERE, "gmd_order.json"), encoding="utf-8") as fh:
            _GMD_ORDER = json.load(fh)
    return _GMD_ORDER


def _kosongkan_nilai(root):
    """Template hanya dipakai sebagai kerangka. Semua nilai bawaannya dibuang supaya field yang
    tidak diisi tidak membawa data contoh/placeholder ke hasil ekspor; sisa kerangka yang tetap
    kosong dipangkas oleh _rapikan()."""
    for el in root.iter():
        if len(el) == 0:
            el.text = None
        if "codeListValue" in el.attrib:
            el.set("codeListValue", "")


def _anak(parent, *tags):
    """Ambil anak gmd berantai, buat yang belum ada: _anak(dq, "scope", "DQ_Scope")."""
    el = parent
    for t in tags:
        nxt = el.find(_q(GMD, t))
        if nxt is None:
            nxt = ET.SubElement(el, _q(GMD, t))
        el = nxt
    return el


def _ganti_semua(parent, tag_name, baru):
    """Ganti semua anak `tag_name` dengan elemen `baru` (posisi akhirnya diatur _rapikan)."""
    for el in parent.findall(_q(GMD, tag_name)):
        parent.remove(el)
    for el in baru:
        parent.append(el)


def _datetime(value):
    """gco:DateTime wajib memuat jam; tanggal saja dilengkapi T00:00:00."""
    v = _clean_str(value)
    return v if not v or "T" in v else v + "T00:00:00"


def _set_date(parent, tag_name, value):
    v = _clean_str(value)
    if not v:
        return None
    el = parent.find(_q(GMD, tag_name))
    if el is None:
        el = ET.SubElement(parent, _q(GMD, tag_name))
    for c in list(el):
        el.remove(c)
    sub = ET.SubElement(el, _q(GCO, "DateTime" if "T" in v else "Date"))
    sub.text = v
    return el


def _set_language(parent, tag_name, value):
    v = _clean_str(value)
    if not v:
        return None
    el = parent.find(_q(GMD, tag_name))
    if el is None:
        el = ET.SubElement(parent, _q(GMD, tag_name))
    for c in list(el):
        el.remove(c)
    lc = ET.SubElement(el, _q(GMD, "LanguageCode"))
    lc.set("codeList", "./resources/codeList.xml#LanguageCode")
    lc.set("codeListValue", v)
    lc.text = v
    return el


def _set_dq_scope(dq, level, timpa=False):
    """DQ_DataQuality wajib punya scope/DQ_Scope/level."""
    sc = _anak(dq, "scope", "DQ_Scope")
    lv = sc.find(f"{_q(GMD, 'level')}/{_q(GMD, 'MD_ScopeCode')}")
    if timpa or lv is None or not lv.get("codeListValue"):
        _set_code(sc, "level", "MD_ScopeCode", level)


def _dq_pertama(gmd_root):
    """DQ_DataQuality pertama (dibuat bila belum ada). Laporan kualitas dan lineage sengaja disatukan
    di sini: OWSLib — yang dipakai GeoNode & pycsw — hanya membaca blok DQ_DataQuality pertama."""
    dq = gmd_root.find(f"{_q(GMD, 'dataQualityInfo')}/{_q(GMD, 'DQ_DataQuality')}")
    if dq is None:
        dq = ET.SubElement(ET.SubElement(gmd_root, _q(GMD, "dataQualityInfo")), _q(GMD, "DQ_DataQuality"))
    return dq


def _set_nilai(parent, tag_name, gco_type, value, **attrib):
    """Properti bernilai tunggal bertipe gco (Integer, Real, Boolean, Measure, Record, ...)."""
    v = _clean_str(value)
    if not v:
        return None
    if gco_type == "Boolean":
        v = v.lower()
    el = ET.SubElement(parent, _q(GMD, tag_name))
    sub = ET.SubElement(el, _q(GCO, gco_type))
    for k, a in attrib.items():
        sub.set(k, a)
    sub.text = v
    return el


def _daftar(nodes, akhiran):
    """Instance BList yang path-nya berakhiran `akhiran` (dicari langsung di `nodes`)."""
    for n in nodes:
        if isinstance(n, layout.BList) and getattr(n, "path", "").endswith(akhiran):
            return n.instances
    return []


def _titik(parent, tag_name, gml_id, lat, lon):
    """gml:Point (GML 3.2: gml:id wajib) dengan posisi "lintang bujur" seperti di formulir."""
    lat, lon = _clean_str(lat), _clean_str(lon)
    if not (lat and lon):
        return None
    el = ET.SubElement(parent, _q(GMD, tag_name))
    pt = ET.SubElement(el, _q(GML, "Point"))
    pt.set(_q(GML, "id"), gml_id)
    ET.SubElement(pt, _q(GML, "pos")).text = f"{lat} {lon}"
    return el


# Ejaan formulir (ISO 19115-3) → enumerasi ISO 19139
_PIKSEL = {"centre": "center"}


def _grid_dasar(el, d, nodes):
    """Properti MD_GridSpatialRepresentation yang dipakai Georectified & Georeferenceable."""
    _set_nilai(el, "numberOfDimensions", "Integer", d.get("rasterNumDimensions"))
    for inst in _daftar(nodes, "axisDimensionProperties"):
        dd = _collect_dict_from_nodes(inst.nodes)
        if not any(dd.values()):
            continue
        dim = ET.SubElement(ET.SubElement(el, _q(GMD, "axisDimensionProperties")), _q(GMD, "MD_Dimension"))
        _set_code(dim, "dimensionName", "MD_DimensionNameTypeCode", dd.get("dimName"))
        _set_nilai(dim, "dimensionSize", "Integer", dd.get("dimSize"))
        _set_nilai(dim, "resolution", "Measure", dd.get("dimRes"), uom="m")  # formulir: resolusi dalam meter
    _set_code(el, "cellGeometry", "MD_CellGeometryCode", d.get("rasterCellGeometry"))
    _set_nilai(el, "transformationParameterAvailability", "Boolean", d.get("rasterTransformationParams"))


def _georectified(opt):
    d = _bidang_langsung(opt.nodes)
    wrap = ET.Element(_q(GMD, "spatialRepresentationInfo"))
    g = ET.SubElement(wrap, _q(GMD, "MD_Georectified"))
    _grid_dasar(g, d, opt.nodes)
    _set_nilai(g, "checkPointAvailability", "Boolean", d.get("rasterCheckPointAvailability"))
    _set_char(g, "checkPointDescription", d.get("rasterCheckPointDescription"))
    for i in (1, 2):
        _titik(g, "cornerPoints", f"georectified-corner-{i}",
               d.get(f"rasterCornerPoint{i}Lat"), d.get(f"rasterCornerPoint{i}Lon"))
    _titik(g, "centerPoint", "georectified-center", d.get("rasterCentrePointLat"), d.get("rasterCentrePointLon"))
    if d.get("rasterPointPixel"):
        px = ET.SubElement(g, _q(GMD, "pointInPixel"))
        ET.SubElement(px, _q(GMD, "MD_PixelOrientationCode")).text = _PIKSEL.get(d["rasterPointPixel"], d["rasterPointPixel"])
    _set_char(g, "transformationDimensionDescription", d.get("rasterTransformationDimensionDescription"))
    for inst in _daftar(opt.nodes, "transformationDimensionMapping")[:2]:  # ISO 19139: maksimal 2
        v = _collect_dict_from_nodes(inst.nodes).get("value")
        if v:
            _set_nilai(g, "transformationDimensionMapping", "CharacterString", v)
    return wrap


def _georeferenceable(opt, catatan):
    d = _bidang_langsung(opt.nodes)
    wrap = ET.Element(_q(GMD, "spatialRepresentationInfo"))
    g = ET.SubElement(wrap, _q(GMD, "MD_Georeferenceable"))
    _grid_dasar(g, d, opt.nodes)
    _set_nilai(g, "controlPointAvailability", "Boolean", d.get("controlPointAvailability"))
    _set_nilai(g, "orientationParameterAvailability", "Boolean", d.get("orientationParameterAvailability"))
    _set_char(g, "orientationParameterDescription", d.get("orientationParameterDescription"))
    _set_nilai(g, "georeferencedParameters", "Record", d.get("georeferencedParameters"))
    gcp = [k for k in d if k.startswith("rasterGCPCollection")] or [
        i for i in _daftar(opt.nodes, "gcp") if any(_collect_dict_from_nodes(i.nodes).values())]
    if gcp:
        catatan.append("Koleksi GCP (geolocationInformation) adalah bagian ISO 19115-2, tidak ada di ISO 19139 — "
                       "tidak diekspor.")
    return wrap


def _band(bd, catatan):
    """dimension/MD_Band ISO 19139 dari satu band formulir."""
    wrap = ET.Element(_q(GMD, "dimension"))
    b = ET.SubElement(wrap, _q(GMD, "MD_Band"))
    nama = bd.get("sequenceId") or bd.get("code")
    if nama:
        mn = ET.SubElement(ET.SubElement(b, _q(GMD, "sequenceIdentifier")), _q(GCO, "MemberName"))
        ET.SubElement(ET.SubElement(mn, _q(GCO, "aName")), _q(GCO, "CharacterString")).text = nama
        ET.SubElement(mn, _q(GCO, "attributeType")).set(_q(GCO, "nilReason"), "missing")
    if bd.get("sequenceId") and (bd.get("code") or bd.get("authority")):
        catatan.append("Identitas band (otoritas/kode) tidak punya padanan di MD_Band ISO 19139 — tidak diekspor.")
    _set_char(b, "descriptor", bd.get("description"))
    for key, tag, tipe in (("maxValue", "maxValue", "Real"), ("minValue", "minValue", "Real"),
                           ("peakResponse", "peakResponse", "Real"), ("bitsPerValue", "bitsPerValue", "Integer"),
                           ("toneGradation", "toneGradation", "Integer"), ("scaleFactor", "scaleFactor", "Real")):
        _set_nilai(b, tag, tipe, bd.get(key))
    if bd.get("boundMin") or bd.get("boundMax"):
        catatan.append("Batas panjang gelombang band (boundMin/boundMax) adalah bagian ISO 19115-2 — tidak diekspor.")
    return wrap


def _deskripsi_cakupan(opt, kelas, catatan):
    """contentInfo/MD_CoverageDescription atau MD_ImageDescription (ISO 19139)."""
    d = _bidang_langsung(opt.nodes)
    wrap = ET.Element(_q(GMD, "contentInfo"))
    c = ET.SubElement(wrap, _q(GMD, kelas))
    _set_nilai(c, "attributeDescription", "RecordType", d.get("coverageAttributeDescription"))
    grup = _daftar(opt.nodes, "attributeGroup")
    # ISO 19139 hanya punya satu contentType per deskripsi; grup atribut formulir digabung
    jenis = [_bidang_langsung(g.nodes).get("contentType") for g in grup]
    jenis = [j for j in jenis if j]
    _set_code(c, "contentType", "MD_CoverageContentTypeCode", jenis[0] if jenis else "")
    if len(set(jenis)) > 1:
        catatan.append("ISO 19139 hanya memuat satu tipe konten per deskripsi cakupan — tipe pertama dipakai.")
    for g in grup:
        for att in _daftar(g.nodes, "attribute"):
            bd = _bidang_langsung(att.nodes)
            if bd:
                c.append(_band(bd, catatan))
            if any(any(_collect_dict_from_nodes(r.nodes).values()) for r in _daftar(att.nodes, "rangeElementDescription")):
                catatan.append("Deskripsi elemen rentang band adalah bagian ISO 19115-2 — tidak diekspor.")
    if d.get("coverageProcessingLevelCode") or d.get("coverageProcessingLevelDescription"):
        if kelas == "MD_ImageDescription":
            plc = _anak(c, "processingLevelCode", "MD_Identifier")
            _set_char(plc, "code", d.get("coverageProcessingLevelCode"))
        if kelas != "MD_ImageDescription" or d.get("coverageProcessingLevelDescription"):
            catatan.append("Deskripsi/kode tingkat pengolahan tidak sepenuhnya punya padanan di ISO 19139 "
                           "(hanya kode, dan hanya pada deskripsi citra) — sebagian tidak diekspor.")
    if kelas == "MD_ImageDescription":
        _set_nilai(c, "illuminationElevationAngle", "Real", d.get("imageIlluminationElevation"))
        _set_nilai(c, "illuminationAzimuthAngle", "Real", d.get("imageIlluminationAzimuth"))
        _set_code(c, "imagingCondition", "MD_ImagingConditionCode", d.get("imageImagingCondition"))
        if d.get("imageQualityCode") or d.get("imageQualityAuthority"):
            iq = _anak(c, "imageQualityCode", "MD_Identifier")
            if d.get("imageQualityAuthority"):
                _set_char(_anak(iq, "authority", "CI_Citation"), "title", d["imageQualityAuthority"])
            _set_char(iq, "code", d.get("imageQualityCode"))
        _set_nilai(c, "cloudCoverPercentage", "Real", d.get("imageCloudCoverPercentage"))
        _set_nilai(c, "compressionGenerationQuantity", "Integer", d.get("imageCompressionGenerationQuantity"))
        for key, tag in (("imageTriangulationIndicator", "triangulationIndicator"),
                         ("imageRadiometricCalibration", "radiometricCalibrationDataAvailability"),
                         ("imageCameraCalibration", "cameraCalibrationInformationAvailability"),
                         ("imageFilmDistortion", "filmDistortionInformationAvailability"),
                         ("imageLensDistortion", "lensDistortionInformationAvailability")):
            _set_nilai(c, tag, "Boolean", d.get(key))
    return wrap


# Kelas laporan ISO 19157 (formulir) yang namanya berbeda di ISO 19139.
_DQ_19139 = {"DQ_NonQuantitativeAttributeCorrectness": "DQ_NonQuantitativeAttributeAccuracy"}


def _laporan_dq(inst, catatan):
    """gmd:report dari satu laporan kualitas formulir, dengan struktur DQ_Element ISO 19139:
    nameOfMeasure, measureDescription, evaluationMethodType, evaluationMethodDescription,
    dateTime, result (DQ_ConformanceResult: specification, explanation, pass)."""
    rep_d = _collect_dict_from_nodes(inst.nodes)
    hasil = []
    for r_node in inst.nodes:
        if isinstance(r_node, layout.BList) and getattr(r_node, "path", "") == "result":
            hasil += [_collect_dict_from_nodes(ri.nodes) for ri in r_node.instances]
    hasil = [h for h in hasil if any(h.values())]
    if not any(rep_d.values()) and not hasil:
        return None

    kelas = next((_lokal(c.tag) for c in inst.el), "DQ_DomainConsistency")
    kelas = _DQ_19139.get(kelas, kelas)
    if kelas not in _gmd_order():
        catatan.append(f"Laporan kualitas jenis {kelas} tidak dikenal ISO 19139 — tidak diekspor.")
        return None

    wrap = ET.Element(_q(GMD, "report"))
    dq_el = ET.SubElement(wrap, _q(GMD, kelas))
    _set_char(dq_el, "nameOfMeasure", rep_d.get("measure"))
    _set_char(dq_el, "measureDescription", rep_d.get("description"))
    _set_code(dq_el, "evaluationMethodType", "DQ_EvaluationMethodTypeCode", rep_d.get("evaluationMethodType"))
    _set_char(dq_el, "evaluationMethodDescription", rep_d.get("evaluationMethodDescription"))
    # ISO 19139 mencatat waktu evaluasi di DQ_Element, bukan di hasil
    waktu = next((h["dateTime"] for h in hasil if h.get("dateTime")), "")
    if waktu:
        dt = ET.SubElement(dq_el, _q(GMD, "dateTime"))
        ET.SubElement(dt, _q(GCO, "DateTime")).text = _datetime(waktu)
    for h in hasil:
        res = ET.SubElement(ET.SubElement(dq_el, _q(GMD, "result")), _q(GMD, "DQ_ConformanceResult"))
        if h.get("specificationTitle") or h.get("specificationAlternate"):
            spec = _anak(res, "specification", "CI_Citation")
            _set_char(spec, "title", h.get("specificationTitle"))
            _set_char(spec, "alternateTitle", h.get("specificationAlternate"))
        _set_char(res, "explanation", h.get("explanation"))
        if h.get("pass"):
            ps = ET.SubElement(res, _q(GMD, "pass"))
            ET.SubElement(ps, _q(GCO, "Boolean")).text = str(h["pass"]).strip().lower()
    return wrap


# Pemetaan properti batasan ISO 19139 → kunci formulir, untuk batasan sumber daya & metadata.
_KUNCI_BATASAN = {
    "resourceConstraints": {
        "useLimitation": "useLimitation", "accessConstraints": "accessConstraints",
        "useConstraints": "useConstraints", "otherConstraints": "otherConstraints",
        "classification": "securityClassification", "userNote": "securityUserNote",
        "classificationSystem": "securitySystem", "handlingDescription": "handlingDescription",
    },
    "metadataConstraints": {
        "useLimitation": "metadataUseLimitation", "accessConstraints": "metadataAccessConstraints",
        "useConstraints": "metadataUseConstraints", "otherConstraints": "metadataOtherConstraints",
        "classification": "metadataSecurityClassification", "userNote": "metadataSecurityUserNote",
        "classificationSystem": "metadataSecuritySystem", "handlingDescription": "metadataHandlingDescription",
    },
}


def _daftar_nilai(nodes, path, kunci):
    """Nilai terisi dari daftar formulir `path` (satu kolom `kunci` per instans), urut & tanpa ganda."""
    out = []
    for n in nodes:
        if isinstance(n, layout.BList) and getattr(n, "path", "") == path:
            for inst in n.instances:
                v = _clean_str(_collect_dict_from_nodes(inst.nodes).get(kunci))
                if v and v not in out:
                    out.append(v)
    return out


def _batasan(tag_name, data, pakai=(), lain=()):
    """Blok batasan (MD_Constraints / MD_LegalConstraints / MD_SecurityConstraints) yang terisi.
    `pakai`/`lain`: daftar useConstraints/otherConstraints (batasan sumber daya bisa lebih dari satu nilai)."""
    v = {prop: _clean_str(data.get(kunci)) for prop, kunci in _KUNCI_BATASAN[tag_name].items()}
    pakai = list(pakai) or ([v["useConstraints"]] if v["useConstraints"] else [])
    lain = list(lain) or ([v["otherConstraints"]] if v["otherConstraints"] else [])
    out = []

    def blok(kelas):
        w = ET.Element(_q(GMD, tag_name))
        out.append(w)
        return ET.SubElement(w, _q(GMD, kelas))

    if v["useLimitation"]:
        _set_char(blok("MD_Constraints"), "useLimitation", v["useLimitation"])
    if v["accessConstraints"] or pakai or lain:
        c = blok("MD_LegalConstraints")
        _set_code(c, "accessConstraints", "MD_RestrictionCode", v["accessConstraints"])
        for kode in pakai:  # _set_code mengisi elemen yang sudah ada; dibuat di wadah sementara agar tiap nilai baru
            c.append(_set_code(ET.Element("_"), "useConstraints", "MD_RestrictionCode", kode))
        for teks in lain:
            ET.SubElement(ET.SubElement(c, _q(GMD, "otherConstraints")), _q(GCO, "CharacterString")).text = teks
    if v["classification"] or v["userNote"] or v["classificationSystem"] or v["handlingDescription"]:
        c = blok("MD_SecurityConstraints")
        _set_code(c, "classification", "MD_ClassificationCode", v["classification"])
        _set_char(c, "userNote", v["userNote"])
        _set_char(c, "classificationSystem", v["classificationSystem"])
        _set_char(c, "handlingDescription", v["handlingDescription"])
    return out


def _rapikan(root, catatan):
    """Rapikan hasil pemetaan agar sah menurut XSD ISO 19139:
    1. properti yang tidak dikenal ISO 19139 di kelasnya dibuang (dicatat),
    2. elemen tanpa nilai dipangkas,
    3. properti wajib yang kosong diberi gco:nilReason="missing",
    4. properti tiap kelas diurutkan menurut xs:sequence.
    """
    order = _gmd_order()
    nil = _q(GCO, "nilReason")
    href = _q(XLINK, "href")

    def kelas(el):
        return el.tag.startswith("{%s}" % GMD) and _lokal(el.tag) in order

    for el in list(root.iter()):
        if kelas(el):
            sah = {p for p, _ in order[_lokal(el.tag)]}
            for c in list(el):
                if not c.tag.startswith("{%s}" % GMD) or _lokal(c.tag) not in sah:
                    el.remove(c)
                    catatan.append(f"Elemen {_lokal(el.tag)}/{_lokal(c.tag)} tidak dikenal ISO 19139 — tidak diekspor.")

    def pangkas(el):
        for c in list(el):
            if not pangkas(c):
                el.remove(c)
        return bool(len(el) or (el.text or "").strip() or el.get(nil) or el.get(href) or el.get("src")
                    or el.get("codeListValue", "").strip())

    for c in list(root):
        if not pangkas(c):
            root.remove(c)

    for el in list(root.iter()):
        if not kelas(el):
            continue
        urutan = order[_lokal(el.tag)]
        for prop, minimal in urutan:
            if minimal and el.find(_q(GMD, prop)) is None:
                ET.SubElement(el, _q(GMD, prop)).set(nil, "missing")
        posisi = {p: i for i, (p, _) in enumerate(urutan)}
        anak = sorted(el, key=lambda c: posisi.get(_lokal(c.tag), len(posisi)))
        for c in list(el):
            el.remove(c)
        el.extend(anak)
    return root


def export_to_gmd(iso3_root, template_path=None, catatan=None, tidak_standar=None):
    """Mengekspor pohon data ISO 19115-3 ke dokumen XML ISO 19139 (gmd).

    `catatan` (opsional, list): diisi pesan untuk isian yang tidak punya padanan di ISO 19139
    sehingga tidak ikut diekspor (tetap tersimpan di berkas ISO 19115-3).
    `tidak_standar` (opsional, list): diisi nilai daftar kode yang diekspor tetapi tidak ada di daftar
    kode ISO 19139 — sah menurut XSD, namun katalog berbasis ISO 19139 bisa tidak mengenalinya."""
    if catatan is None:
        catatan = []
    register_gmd_namespaces()
    tmpl_file = template_path or GMD_TEMPLATE
    if not os.path.exists(tmpl_file):
        raise FileNotFoundError(f"Template GMD tidak ditemukan di: {tmpl_file}")

    tree = ET.parse(tmpl_file)  # nosec B314
    gmd_root = tree.getroot()
    _kosongkan_nilai(gmd_root)

    # Bangun struktur seksi dari form ISO 19115-3
    secs, _ = layout.build(iso3_root)
    sec_map = {s.id: s for s in secs}

    # =========================================================================
    # TAHAP 1: INFORMASI METADATA
    # =========================================================================
    s1 = sec_map.get(1)
    d1 = _collect_dict_from_nodes(s1.nodes) if s1 else {}
    if s1:
        if "metadataIdentifier" in d1 and d1["metadataIdentifier"].strip():
            _set_char(gmd_root, "fileIdentifier", d1["metadataIdentifier"].strip())
        _set_language(gmd_root, "language", d1.get("language"))
        if "characterEncoding" in d1 and d1["characterEncoding"].strip():
            _set_code(gmd_root, "characterSet", "MD_CharacterSetCode", d1["characterEncoding"].strip())
        if d1.get("country"):
            # Negara hanya bisa dimuat lewat gmd:locale/PT_Locale (bersama bahasa & set karakter)
            loc = _anak(gmd_root, "locale", "PT_Locale")
            _set_language(loc, "languageCode", d1.get("language"))
            _set_code(loc, "country", "Country", d1["country"])
            _set_code(loc, "characterEncoding", "MD_CharacterSetCode", d1.get("characterEncoding"))
        _set_char(gmd_root, "parentIdentifier", d1.get("parentMetadata"))
        if "metadataScope" in d1:
            _set_code(gmd_root, "hierarchyLevel", "MD_ScopeCode", d1["metadataScope"])
        if "scopeName" in d1:
            _set_char(gmd_root, "hierarchyLevelName", d1["scopeName"])
        if "metadataStandardTitle" in d1:
            _set_char(gmd_root, "metadataStandardName", d1["metadataStandardTitle"])
        if "metadataStandardEdition" in d1:
            _set_char(gmd_root, "metadataStandardVersion", d1["metadataStandardEdition"])

        # Kontak Metadata (s1) — semua kontak, bukan hanya yang pertama
        for n in s1.nodes:
            if isinstance(n, layout.BList) and getattr(n, "path", "") == "contact":
                kontak = []
                for inst in n.instances:
                    cd = _collect_dict_from_nodes(inst.nodes)
                    if any(cd.values()):
                        kontak.append(_build_contact_element("contact", cd))
                _ganti_semua(gmd_root, "contact", kontak)

            # Tanggal Metadata (dateInfo)
            if isinstance(n, layout.BList) and getattr(n, "path", "") == "dateInfo":
                date_vals = []
                for inst in n.instances:
                    dd = _collect_dict_from_nodes(inst.nodes)
                    dt_val = dd.get("date")
                    if dt_val:
                        date_vals.append(dt_val)
                if date_vals:
                    old_dss = gmd_root.findall(_q(GMD, "dateStamp"))
                    idx = list(gmd_root).index(old_dss[0]) if old_dss else 0
                    for old_ds in old_dss:
                        gmd_root.remove(old_ds)
                    # ISO 19139 hanya mengizinkan 1 dateStamp pada MD_Metadata
                    dv = date_vals[0]
                    new_ds = ET.Element(_q(GMD, "dateStamp"))
                    tag_type = "DateTime" if "T" in dv else "Date"
                    sub_d = ET.SubElement(new_ds, _q(GCO, tag_type))
                    sub_d.text = dv
                    gmd_root.insert(idx, new_ds)

    # =========================================================================
    # TAHAP 2: IDENTITAS DATA
    # =========================================================================
    data_id = gmd_root.find(f"{_q(GMD, 'identificationInfo')}/{_q(GMD, 'MD_DataIdentification')}")
    data_online = None
    if data_id is not None:
        # Formulir (gaya BIG) memakai satu bahasa & set karakter untuk metadata dan data;
        # MD_DataIdentification/language wajib di ISO 19139.
        _set_language(data_id, "language", d1.get("language"))
        _set_code(data_id, "characterSet", "MD_CharacterSetCode", d1.get("characterEncoding"))
    s2 = sec_map.get(2)
    if s2 and data_id is not None:
        d2 = _collect_dict_from_nodes(s2.nodes)

        # Citation
        cit = data_id.find(_q(GMD, "citation"))
        if cit is None:
            cit = ET.SubElement(data_id, _q(GMD, "citation"))
        ci_cit = cit.find(_q(GMD, "CI_Citation"))
        if ci_cit is None:
            ci_cit = ET.SubElement(cit, _q(GMD, "CI_Citation"))

        if "dataTitle" in d2:
            _set_char(ci_cit, "title", d2["dataTitle"])
        if "dataAlternateTitle" in d2:
            _set_char(ci_cit, "alternateTitle", d2["dataAlternateTitle"])
        if "dataEdition" in d2:
            _set_char(ci_cit, "edition", d2["dataEdition"])
        _set_date(ci_cit, "editionDate", d2.get("dataEditionDate"))
        if "presentationForm" in d2:
            _set_code(ci_cit, "presentationForm", "CI_PresentationFormCode", d2["presentationForm"])

        # Tanggal Sitasi (creation, publication, revision)
        for date_key, type_code in (
            ("dataCreationDate", "creation"),
            ("dataPublicationDate", "publication"),
            ("dataRevisionDate", "revision"),
        ):
            if date_key in d2:
                # Perbarui atau sisipkan gmd:date
                val = d2[date_key]
                found = False
                for d_node in ci_cit.findall(_q(GMD, "date")):
                    tc = d_node.findtext(f"{_q(GMD, 'CI_Date')}/{_q(GMD, 'dateType')}/{_q(GMD, 'CI_DateTypeCode')}")
                    if tc == type_code:
                        d_val = d_node.find(f"{_q(GMD, 'CI_Date')}/{_q(GMD, 'date')}")
                        if d_val is not None:
                            d_val.clear()
                            tag_t = "DateTime" if "T" in val else "Date"
                            sub = ET.SubElement(d_val, _q(GCO, tag_t))
                            sub.text = val
                            found = True
                            break
                if not found:
                    d_wrap = ET.SubElement(ci_cit, _q(GMD, "date"))
                    c_date = ET.SubElement(d_wrap, _q(GMD, "CI_Date"))
                    dt_wrap = ET.SubElement(c_date, _q(GMD, "date"))
                    tag_t = "DateTime" if "T" in val else "Date"
                    sub = ET.SubElement(dt_wrap, _q(GCO, tag_t))
                    sub.text = val
                    dt_type = ET.SubElement(c_date, _q(GMD, "dateType"))
                    tc_el = ET.SubElement(dt_type, _q(GMD, "CI_DateTypeCode"))
                    tc_el.set("codeList", "http://www.isotc211.org/2005/resources/Codelist/gmxCodelists.xml#CI_DateTypeCode")
                    tc_el.set("codeListValue", type_code)
                    tc_el.text = type_code

        # Online Resource Data — ISO 19139 tidak punya CI_Citation/onlineResource; tautannya
        # diekspor sebagai distributionInfo/transferOptions/onLine (setelah Tahap 6).
        if "dataOnlineResourceURL" in d2:
            data_online = _build_online_resource_element(
                "onLine",
                d2.get("dataOnlineResourceURL", ""),
                d2.get("dataOnlineResourceProtocol", ""),
                d2.get("dataOnlineResourceName", ""),
                function=d2.get("dataOnlineResourceFunction", "information"),
            )

        # Kontak Sitasi Data (citedResponsibleParty)
        for n in s2.nodes:
            if isinstance(n, layout.BList) and "citedResponsibleParty" in getattr(n, "path", ""):
                for old_crp in ci_cit.findall(_q(GMD, "citedResponsibleParty")):
                    ci_cit.remove(old_crp)
                for inst in n.instances:
                    cd = _collect_dict_from_nodes(inst.nodes)
                    if any(cd.values()):
                        ci_cit.append(_build_contact_element("citedResponsibleParty", cd))

        # Identifier data (mis. DOI)
        idf_baru = []
        if d2.get("dataIdentifier"):
            idf = ET.Element(_q(GMD, "identifier"))
            _set_char(ET.SubElement(idf, _q(GMD, "MD_Identifier")), "code", d2["dataIdentifier"])
            idf_baru.append(idf)
        _ganti_semua(ci_cit, "identifier", idf_baru)

        # Deskripsi umum
        if "dataAbstract" in d2:
            _set_char(data_id, "abstract", d2["dataAbstract"])
        if "dataPurpose" in d2:
            _set_char(data_id, "purpose", d2["dataPurpose"])
        if "dataCredit" in d2:
            _set_char(data_id, "credit", d2["dataCredit"])
        if "dataSupplementalInformation" in d2:
            _set_char(data_id, "supplementalInformation", d2["dataSupplementalInformation"])
        if "dataStatus" in d2:
            _set_code(data_id, "status", "MD_ProgressCode", d2["dataStatus"])

        # Point of Contact (data_id)
        for n in s2.nodes:
            if isinstance(n, layout.BList) and "pointOfContact" in getattr(n, "path", ""):
                # Bersihkan pointOfContact lama
                for old_p in data_id.findall(_q(GMD, "pointOfContact")):
                    data_id.remove(old_p)
                for inst in n.instances:
                    cd = _collect_dict_from_nodes(inst.nodes)
                    if any(cd.values()):
                        data_id.append(_build_contact_element("pointOfContact", cd))

            # Topic Category
            if isinstance(n, layout.BList) and "topicCategory" in getattr(n, "path", ""):
                for old_tc in data_id.findall(_q(GMD, "topicCategory")):
                    data_id.remove(old_tc)
                for inst in n.instances:
                    tcd = _collect_dict_from_nodes(inst.nodes)
                    t_val = tcd.get("topicCategory")
                    if t_val and t_val not in kesesuaian.enumerasi_19139("MD_TopicCategoryCode"):
                        # enumerasi tertutup: nilai baru ISO 19115-3 (mis. disaster) membuat XML tidak valid
                        catatan.append("Kategori topik «%s» hanya ada di ISO 19115-3, bukan di daftar tertutup "
                                       "ISO 19139 — tidak diekspor." % t_val)
                    elif t_val:
                        tc_el = ET.SubElement(data_id, _q(GMD, "topicCategory"))
                        tcc = ET.SubElement(tc_el, _q(GMD, "MD_TopicCategoryCode"))
                        tcc.text = t_val

            # Kata Kunci (descriptiveKeywords)
            if isinstance(n, layout.BList) and "descriptiveKeywords" in getattr(n, "path", ""):
                for old_dk in data_id.findall(_q(GMD, "descriptiveKeywords")):
                    data_id.remove(old_dk)
                for inst in n.instances:
                    kw_type = "theme"
                    words = []
                    for child_node in inst.nodes:
                        if isinstance(child_node, layout.BField) and child_node.key == "type":
                            kw_type = (child_node.field.get() or "theme").strip()
                        elif isinstance(child_node, layout.BList) and getattr(child_node, "path", "") == "keyword":
                            for k_inst in child_node.instances:
                                kd = _collect_dict_from_nodes(k_inst.nodes)
                                if kd.get("value"):
                                    words.append(kd["value"])
                    if words:
                        dk = ET.SubElement(data_id, _q(GMD, "descriptiveKeywords"))
                        md_kws = ET.SubElement(dk, _q(GMD, "MD_Keywords"))
                        for w in words:
                            kw_el = ET.SubElement(md_kws, _q(GMD, "keyword"))
                            cs = ET.SubElement(kw_el, _q(GCO, "CharacterString"))
                            cs.text = w
                        if kw_type:
                            _set_code(md_kws, "type", "MD_KeywordTypeCode", kw_type)

            # Format Data (resourceFormat)
            if isinstance(n, layout.BList) and "resourceFormat" in getattr(n, "path", ""):
                for old_rf in data_id.findall(_q(GMD, "resourceFormat")):
                    data_id.remove(old_rf)
                for inst in n.instances:
                    fd = _collect_dict_from_nodes(inst.nodes)
                    fname = fd.get("formatTitle") or fd.get("formatAlternateTitle")
                    if fname:
                        rf = ET.SubElement(data_id, _q(GMD, "resourceFormat"))
                        mdf = ET.SubElement(rf, _q(GMD, "MD_Format"))
                        _set_char(mdf, "name", fname)
                        if fd.get("formatEdition"):
                            _set_char(mdf, "version", fd["formatEdition"])

            # Penggunaan spesifik (resourceSpecificUsage → MD_Usage)
            if isinstance(n, layout.BList) and "resourceSpecificUsage" in getattr(n, "path", ""):
                usages = []
                for inst in n.instances:
                    ud = _collect_dict_from_nodes(inst.nodes)
                    if not any(ud.values()):
                        continue
                    wrap = ET.Element(_q(GMD, "resourceSpecificUsage"))
                    usage = ET.SubElement(wrap, _q(GMD, "MD_Usage"))
                    _set_char(usage, "specificUsage", ud.get("specificUsage"))
                    if ud.get("userOrganization") or ud.get("userIndividual") or ud.get("userRole"):
                        usage.append(_build_contact_element("userContactInfo", {
                            "organization": ud.get("userOrganization"),
                            "position": ud.get("userIndividual"),  # isian formulir: posisi/jabatan pengguna
                            "role": ud.get("userRole"),
                        }))
                    usages.append(wrap)
                _ganti_semua(data_id, "resourceSpecificUsage", usages)

        # Extent Bounding Box & Temporal
        ext_el = data_id.find(_q(GMD, "extent"))
        if ext_el is None:
            ext_el = ET.SubElement(data_id, _q(GMD, "extent"))
        ex_ext = ext_el.find(_q(GMD, "EX_Extent"))
        if ex_ext is None:
            ex_ext = ET.SubElement(ext_el, _q(GMD, "EX_Extent"))

        if "extentDescription" in d2:
            _set_char(ex_ext, "description", d2["extentDescription"])

        # Bounding box
        bbox = ex_ext.find(f"{_q(GMD, 'geographicElement')}/{_q(GMD, 'EX_GeographicBoundingBox')}")
        if bbox is None:
            geo_el = ET.SubElement(ex_ext, _q(GMD, "geographicElement"))
            bbox = ET.SubElement(geo_el, _q(GMD, "EX_GeographicBoundingBox"))

        for key, tag in (
            ("westBound", "westBoundLongitude"),
            ("eastBound", "eastBoundLongitude"),
            ("southBound", "southBoundLatitude"),
            ("northBound", "northBoundLatitude"),
        ):
            if key in d2:
                b_el = bbox.find(_q(GMD, tag))
                if b_el is None:
                    b_el = ET.SubElement(bbox, _q(GMD, tag))
                b_el.clear()
                dec = ET.SubElement(b_el, _q(GCO, "Decimal"))
                dec.text = d2[key]

        # Temporal Extent
        if "timeBegin" in d2 or "timeEnd" in d2:
            time_el = ex_ext.find(f"{_q(GMD, 'temporalElement')}/{_q(GMD, 'EX_TemporalExtent')}")
            if time_el is None:
                te_wrap = ET.SubElement(ex_ext, _q(GMD, "temporalElement"))
                time_el = ET.SubElement(te_wrap, _q(GMD, "EX_TemporalExtent"))
            ext_t = time_el.find(_q(GMD, "extent"))
            if ext_t is None:
                ext_t = ET.SubElement(time_el, _q(GMD, "extent"))
            tp = ext_t.find(_q(GML, "TimePeriod"))
            if tp is None:
                tp = ET.SubElement(ext_t, _q(GML, "TimePeriod"))
                tp.set(_q(GML, "id"), "temporal-extent-1")
            if "timeBegin" in d2:
                bp = tp.find(_q(GML, "beginPosition"))
                if bp is None:
                    bp = ET.SubElement(tp, _q(GML, "beginPosition"))
                bp.text = d2["timeBegin"]
            if "timeEnd" in d2:
                ep = tp.find(_q(GML, "endPosition"))
                if ep is None:
                    ep = ET.SubElement(tp, _q(GML, "endPosition"))
                ep.text = d2["timeEnd"]

    # =========================================================================
    # TAHAP 3: REPRESENTASI SPASIAL
    # =========================================================================
    s3 = sec_map.get(3)
    if s3:
        d3 = _collect_dict_from_nodes(s3.nodes)
        # Grid / raster: MD_Georectified & MD_Georeferenceable (snippet "grid" / "georef")
        for n in s3.nodes:
            if isinstance(n, layout.BOptional) and n.present and n.snippet in ("grid", "georef"):
                gmd_root.append(_georectified(n) if n.snippet == "grid" else _georeferenceable(n, catatan))
        if data_id is not None and "spatialRepresentationType" in d3:
            _set_code(data_id, "spatialRepresentationType", "MD_SpatialRepresentationTypeCode", d3["spatialRepresentationType"])

        # Vektor
        vec = gmd_root.find(f"{_q(GMD, 'spatialRepresentationInfo')}/{_q(GMD, 'MD_VectorSpatialRepresentation')}")
        if vec is not None:
            if "topologyLevel" in d3:
                _set_code(vec, "topologyLevel", "MD_TopologyLevelCode", d3["topologyLevel"])
            geo_objs = vec.find(_q(GMD, "geometricObjects"))
            if geo_objs is None:
                geo_objs = ET.SubElement(vec, _q(GMD, "geometricObjects"))
            md_geom = geo_objs.find(_q(GMD, "MD_GeometricObjects"))
            if md_geom is None:
                md_geom = ET.SubElement(geo_objs, _q(GMD, "MD_GeometricObjects"))
            if "geometricObjectType" in d3:
                _set_code(md_geom, "geometricObjectType", "MD_GeometricObjectTypeCode", d3["geometricObjectType"])
            if "geometricObjectCount" in d3:
                cnt_el = md_geom.find(_q(GMD, "geometricObjectCount"))
                if cnt_el is None:
                    cnt_el = ET.SubElement(md_geom, _q(GMD, "geometricObjectCount"))
                cnt_el.clear()
                sub_int = ET.SubElement(cnt_el, _q(GCO, "Integer"))
                sub_int.text = str(d3["geometricObjectCount"])

        # Resolusi Spasial
        if data_id is not None:
            if "spatialResolution" in d3:
                srs = data_id.findall(_q(GMD, "spatialResolution"))
                target_sr = None
                for sr in srs:
                    if sr.find(f".//{_q(GMD, 'MD_RepresentativeFraction')}") is not None:
                        target_sr = sr
                        break
                if target_sr is None:
                    target_sr = ET.SubElement(data_id, _q(GMD, "spatialResolution"))
                    res_el = ET.SubElement(target_sr, _q(GMD, "MD_Resolution"))
                    eq_el = ET.SubElement(res_el, _q(GMD, "equivalentScale"))
                    rf_el = ET.SubElement(eq_el, _q(GMD, "MD_RepresentativeFraction"))
                    d_el = ET.SubElement(rf_el, _q(GMD, "denominator"))
                    sub_int = ET.SubElement(d_el, _q(GCO, "Integer"))
                    sub_int.text = str(d3["spatialResolution"])
                else:
                    den = target_sr.find(f".//{_q(GMD, 'denominator')}")
                    if den is not None:
                        den.clear()
                        sub_int = ET.SubElement(den, _q(GCO, "Integer"))
                        sub_int.text = str(d3["spatialResolution"])
            if "spatialResolutionM" in d3:
                srs = data_id.findall(_q(GMD, "spatialResolution"))
                target_sr = None
                for sr in srs:
                    if sr.find(f".//{_q(GMD, 'distance')}") is not None:
                        target_sr = sr
                        break
                if target_sr is None:
                    target_sr = ET.SubElement(data_id, _q(GMD, "spatialResolution"))
                    res_el = ET.SubElement(target_sr, _q(GMD, "MD_Resolution"))
                    dist_el = ET.SubElement(res_el, _q(GMD, "distance"))
                    sub_dist = ET.SubElement(dist_el, _q(GCO, "Distance"))
                    sub_dist.set("uom", "m")
                    sub_dist.text = str(d3["spatialResolutionM"])
                else:
                    dist = target_sr.find(f".//{_q(GMD, 'distance')}")
                    if dist is not None:
                        dist.clear()
                        sub_dist = ET.SubElement(dist, _q(GCO, "Distance"))
                        sub_dist.set("uom", "m")
                        sub_dist.text = str(d3["spatialResolutionM"])

    # =========================================================================
    # TAHAP 4: SISTEM REFERENSI KOORDINAT
    # =========================================================================
    s4 = sec_map.get(4)
    if s4:
        d4 = _collect_dict_from_nodes(s4.nodes)
        ref_sys = gmd_root.find(f"{_q(GMD, 'referenceSystemInfo')}/{_q(GMD, 'MD_ReferenceSystem')}")
        if ref_sys is not None:
            rsi = ref_sys.find(_q(GMD, "referenceSystemIdentifier"))
            if rsi is None:
                rsi = ET.SubElement(ref_sys, _q(GMD, "referenceSystemIdentifier"))
            rs_id = rsi.find(_q(GMD, "RS_Identifier"))
            if rs_id is None:
                old_id = rsi.find(_q(GMD, "MD_Identifier"))
                if old_id is not None:
                    rsi.remove(old_id)
                rs_id = ET.SubElement(rsi, _q(GMD, "RS_Identifier"))
            if "referenceSystemCode" in d4:
                _set_char(rs_id, "code", d4["referenceSystemCode"])
            if "referenceSystemCodeSpace" in d4:
                _set_char(rs_id, "codeSpace", d4["referenceSystemCodeSpace"])
                if "referenceSystemTitle" in d4:
                    auth = rs_id.find(_q(GMD, "authority"))
                    if auth is None:
                        auth = ET.SubElement(rs_id, _q(GMD, "authority"))
                    cit_a = auth.find(_q(GMD, "CI_Citation"))
                    if cit_a is None:
                        cit_a = ET.SubElement(auth, _q(GMD, "CI_Citation"))
                    _set_char(cit_a, "title", d4["referenceSystemTitle"])
                    if "referenceSystemAlternateTitle" in d4:
                        _set_char(cit_a, "alternateTitle", d4["referenceSystemAlternateTitle"])

    # =========================================================================
    # TAHAP 5: INFORMASI KONTEN
    # =========================================================================
    s5 = sec_map.get(5)
    if s5:
        d5 = _collect_dict_from_nodes(s5.nodes)
        ft_names = []
        for n in s5.nodes:
            if isinstance(n, layout.BOptional) and n.present:
                if n.snippet in ("coverage", "image"):
                    kelas = "MD_ImageDescription" if n.snippet == "image" else "MD_CoverageDescription"
                    gmd_root.append(_deskripsi_cakupan(n, kelas, catatan))
                    continue
                for sub_n in n.nodes:
                    if isinstance(sub_n, layout.BList) and getattr(sub_n, "path", "") == "featureTypes":
                        for inst in sub_n.instances:
                            ft_d = _collect_dict_from_nodes(inst.nodes)
                            nama = (ft_d.get("name") or "").strip()
                            # Tanpa nama bukan tipe unsur: kode saja (mis. KAB/KEC bawaan template) tidak diekspor.
                            if nama:
                                # "Kode" di formulir = codeSpace nama unsur (featureTypeName/@codeSpace)
                                ft_names.append((nama, ft_d.get("code") or ""))
        fc_keys = ("featureCatalogueCompliance", "featureCatalogueIncluded", "catalogueTitle",
                   "catalogueAlternateTitle", "catalogueEdition", "catalogueURL")
        if any(k in d5 for k in fc_keys) or ft_names:
            for ci_old in gmd_root.findall(_q(GMD, "contentInfo")):
                if ci_old.find(_q(GMD, "MD_FeatureCatalogueDescription")) is not None:
                    gmd_root.remove(ci_old)
            feat_cat = ET.SubElement(ET.SubElement(gmd_root, _q(GMD, "contentInfo")),
                                     _q(GMD, "MD_FeatureCatalogueDescription"))
            for key, tag in (("featureCatalogueCompliance", "complianceCode"),
                             ("featureCatalogueIncluded", "includedWithDataset")):
                if d5.get(key):
                    b_el = ET.SubElement(feat_cat, _q(GMD, tag))
                    ET.SubElement(b_el, _q(GCO, "Boolean")).text = d5[key].strip().lower()
            # ISO 19139: featureTypes bertipe GenericName → gco:LocalName
            for nama, kode in ft_names:
                ft_el = ET.SubElement(feat_cat, _q(GMD, "featureTypes"))
                ln = ET.SubElement(ft_el, _q(GCO, "LocalName"))
                ln.text = nama
                if kode:
                    ln.set("codeSpace", kode)
            fc_cit = _anak(feat_cat, "featureCatalogueCitation", "CI_Citation")
            _set_char(fc_cit, "title", d5.get("catalogueTitle"))
            _set_char(fc_cit, "alternateTitle", d5.get("catalogueAlternateTitle"))
            _set_char(fc_cit, "edition", d5.get("catalogueEdition"))
            if d5.get("catalogueURL"):
                catatan.append("URL katalog unsur tidak punya padanan di CI_Citation ISO 19139 — tidak diekspor.")

    # =========================================================================
    # TAHAP 6: DISTRIBUSI & AKSES DATA
    # =========================================================================
    dist_info = gmd_root.find(f"{_q(GMD, 'distributionInfo')}/{_q(GMD, 'MD_Distribution')}")
    s6 = sec_map.get(6)
    if s6 and dist_info is not None:
        d6 = _collect_dict_from_nodes(s6.nodes)

        for n in s6.nodes:
            if not isinstance(n, layout.BList):
                continue
            path = getattr(n, "path", "")
            # Distribution Format
            if "distributionFormat" in path:
                formats = []
                for inst in n.instances:
                    df_d = _collect_dict_from_nodes(inst.nodes)
                    df_title = df_d.get("title") or df_d.get("alternateTitle")
                    if df_title:
                        df_el = ET.Element(_q(GMD, "distributionFormat"))
                        mdf = ET.SubElement(df_el, _q(GMD, "MD_Format"))
                        _set_char(mdf, "name", df_title)
                        _set_char(mdf, "version", df_d.get("edition"))
                        formats.append(df_el)
                _ganti_semua(dist_info, "distributionFormat", formats)

            # Distributor Contact — ISO 19139: satu distributorContact per MD_Distributor
            elif "distributorContact" in path:
                distributors = []
                for inst in n.instances:
                    cd = _collect_dict_from_nodes(inst.nodes)
                    if any(cd.values()):
                        dist_el = ET.Element(_q(GMD, "distributor"))
                        md_dist = ET.SubElement(dist_el, _q(GMD, "MD_Distributor"))
                        md_dist.append(_build_contact_element("distributorContact", cd))
                        distributors.append(dist_el)
                _ganti_semua(dist_info, "distributor", distributors)

            # Online Transfer Options
            elif "onLine" in path:
                to_el = _anak(dist_info, "transferOptions", "MD_DigitalTransferOptions")
                online = []
                for inst in n.instances:
                    od = _collect_dict_from_nodes(inst.nodes)
                    if od.get("url"):
                        online.append(_build_online_resource_element(
                            "onLine",
                            od["url"],
                            od.get("protocol", ""),
                            od.get("name", ""),
                            od.get("description", ""),
                            od.get("function", "download"),
                        ))
                _ganti_semua(to_el, "onLine", online)

        if dist_info.find(_q(GMD, "distributionFormat")) is None:
            df_el = ET.SubElement(dist_info, _q(GMD, "distributionFormat"))
            df_el.set(_q(GCO, "nilReason"), "missing")

        # Units and Transfer Size
        to_el = _anak(dist_info, "transferOptions", "MD_DigitalTransferOptions")
        _set_char(to_el, "unitsOfDistribution", d6.get("distributionUnits") or d6.get("unitsOfDistribution"))
        if "transferSize" in d6:
            ts_el = to_el.find(_q(GMD, "transferSize"))
            if ts_el is None:
                ts_el = ET.SubElement(to_el, _q(GMD, "transferSize"))
            ts_el.clear()
            sub_r = ET.SubElement(ts_el, _q(GCO, "Real"))
            sub_r.text = str(d6["transferSize"])

    # Online Resource Data dari Tahap 2 → onLine pertama (bila URL-nya belum ada)
    if data_online is not None:
        to_el = _anak(gmd_root, "distributionInfo", "MD_Distribution", "transferOptions", "MD_DigitalTransferOptions")
        url_baru = data_online.findtext(f"{_q(GMD, 'CI_OnlineResource')}/{_q(GMD, 'linkage')}/{_q(GMD, 'URL')}")
        url_ada = {ol.findtext(f"{_q(GMD, 'CI_OnlineResource')}/{_q(GMD, 'linkage')}/{_q(GMD, 'URL')}")
                   for ol in to_el.findall(_q(GMD, "onLine"))}
        if url_baru not in url_ada:
            to_el.insert(0, data_online)

    # =========================================================================
    # TAHAP 7: KUALITAS DATA
    # =========================================================================
    s7 = sec_map.get(7)
    if s7:
        d7 = _collect_dict_from_nodes(s7.nodes)
        has_reports = _has_list_data(s7.nodes, "report")
        if any(d7.values()) or has_reports:
            dq = _dq_pertama(gmd_root)
            if d7.get("qualityScope"):
                _set_dq_scope(dq, d7["qualityScope"], timpa=True)
            for n in s7.nodes:
                if isinstance(n, layout.BList) and "report" in getattr(n, "path", ""):
                    laporan = [r for r in (_laporan_dq(inst, catatan) for inst in n.instances) if r is not None]
                    _ganti_semua(dq, "report", laporan)

    # =========================================================================
    # TAHAP 8: RIWAYAT DATA (LINEAGE)
    # =========================================================================
    s8 = sec_map.get(8)
    if s8:
        d8 = _collect_dict_from_nodes(s8.nodes)
        has_lineage = bool(d8.get("lineageStatement") or d8.get("lineageScopeLevel"))
        has_steps = _has_list_data(s8.nodes, "processStep")
        has_sources = _has_list_data(s8.nodes, "source")
        if has_lineage or has_steps or has_sources:
            dq = _dq_pertama(gmd_root)
            # ISO 19139 tidak punya LI_Lineage/scope: cakupan lineage menjadi cakupan DQ_DataQuality
            # bila Tahap 7 tidak menetapkannya.
            if d8.get("lineageScopeLevel"):
                _set_dq_scope(dq, d8["lineageScopeLevel"])
            for old_lin in dq.findall(_q(GMD, "lineage")):
                dq.remove(old_lin)
            lin_el = _anak(dq, "lineage", "LI_Lineage")
            _set_char(lin_el, "statement", d8.get("lineageStatement"))

            for n in s8.nodes:
                if isinstance(n, layout.BList) and getattr(n, "path", "").endswith("processStep"):
                    for inst in n.instances:
                        ps_d = _bidang_langsung(inst.nodes)
                        opsional = [o for o in inst.nodes if isinstance(o, layout.BOptional) and o.present]
                        if not ps_d and not opsional:
                            continue
                        li_ps = ET.SubElement(ET.SubElement(lin_el, _q(GMD, "processStep")), _q(GMD, "LI_ProcessStep"))
                        _set_char(li_ps, "description", ps_d.get("description"))
                        _set_char(li_ps, "rationale", ps_d.get("rationale"))
                        if ps_d.get("stepDateTime"):
                            dt_wrap = ET.SubElement(li_ps, _q(GMD, "dateTime"))
                            ET.SubElement(dt_wrap, _q(GCO, "DateTime")).text = _datetime(ps_d["stepDateTime"])
                        if ps_d.get("processorName"):
                            li_ps.append(_build_contact_element("processor", {
                                "organization": ps_d["processorName"],
                                "role": ps_d.get("processorRole", "processor"),
                            }))
                        if ps_d.get("referenceTitle"):
                            catatan.append("Referensi tahap proses (\"%s\") tidak punya padanan di ISO 19139 — "
                                           "tidak diekspor." % ps_d["referenceTitle"])
                        for opt in opsional:
                            if opt.label.startswith("Sumber"):
                                src_d = _collect_dict_from_nodes(opt.nodes)
                                if any(src_d.values()):
                                    li_ps.append(_sumber_lineage(src_d, catatan))
                            else:
                                catatan.append(f"Bagian tahap proses \"{opt.label}\" (ISO 19115-2) tidak didukung "
                                               "ISO 19139 — tidak diekspor.")

                elif isinstance(n, layout.BList) and getattr(n, "path", "").endswith("source"):
                    for inst in n.instances:
                        src_d = _collect_dict_from_nodes(inst.nodes)
                        if any(src_d.values()):
                            lin_el.append(_sumber_lineage(src_d, catatan))

    # Setiap DQ_DataQuality wajib punya cakupan; bawaannya dataset.
    for dq in gmd_root.findall(f"{_q(GMD, 'dataQualityInfo')}/{_q(GMD, 'DQ_DataQuality')}"):
        _set_dq_scope(dq, "dataset")

    # =========================================================================
    # TAHAP 9: KATALOG PENYAJIAN (PORTRAYAL)
    # =========================================================================
    s9 = sec_map.get(9)
    if s9:
        d9 = _collect_dict_from_nodes(s9.nodes)
        has_crp = _has_list_data(s9.nodes, "citedResponsibleParty")
        if any(d9.values()) or has_crp:
            pc_el = gmd_root.find(f"{_q(GMD, 'portrayalCatalogueInfo')}/{_q(GMD, 'MD_PortrayalCatalogueReference')}")
            if pc_el is None:
                pc_wrap = ET.SubElement(gmd_root, _q(GMD, "portrayalCatalogueInfo"))
                pc_el = ET.SubElement(pc_wrap, _q(GMD, "MD_PortrayalCatalogueReference"))

            pcc = pc_el.find(_q(GMD, "portrayalCatalogueCitation"))
            if pcc is None:
                pcc = ET.SubElement(pc_el, _q(GMD, "portrayalCatalogueCitation"))
            ci_pc = pcc.find(_q(GMD, "CI_Citation"))
            if ci_pc is None:
                ci_pc = ET.SubElement(pcc, _q(GMD, "CI_Citation"))

            if "portrayalCatalogueTitle" in d9:
                _set_char(ci_pc, "title", d9["portrayalCatalogueTitle"])
            if "portrayalCatalogueAlternateTitle" in d9:
                _set_char(ci_pc, "alternateTitle", d9["portrayalCatalogueAlternateTitle"])
            if d9.get("portrayalCatalogueURL"):
                catatan.append("URL katalog penyajian tidak punya padanan di CI_Citation ISO 19139 — tidak diekspor.")

            for n in s9.nodes:
                if isinstance(n, layout.BList) and "citedResponsibleParty" in getattr(n, "path", ""):
                    for old_crp in ci_pc.findall(_q(GMD, "citedResponsibleParty")):
                        ci_pc.remove(old_crp)
                    for inst in n.instances:
                        cd = _collect_dict_from_nodes(inst.nodes)
                        if any(cd.values()):
                            ci_pc.append(_build_contact_element("citedResponsibleParty", cd))

    # =========================================================================
    # TAHAP 10: BATASAN & KEAMANAN
    # =========================================================================
    s10 = sec_map.get(10)
    if s10 and data_id is not None:
        d10 = _collect_dict_from_nodes(s10.nodes)
        # Dibuat dari isian (template tidak memuat blok batasan, jadi dulu tak pernah terekspor)
        _ganti_semua(data_id, "resourceConstraints", _batasan(
            "resourceConstraints", d10,
            _daftar_nilai(s10.nodes, layout.PATH_USE_CONSTRAINTS, "useConstraints"),
            _daftar_nilai(s10.nodes, layout.PATH_OTHER_CONSTRAINTS, "otherConstraints")))
        _ganti_semua(gmd_root, "metadataConstraints", _batasan("metadataConstraints", d10))

    # =========================================================================
    # TAHAP 11: SKEMA APLIKASI
    # =========================================================================
    s11 = sec_map.get(11)
    if s11:
        d11 = _collect_dict_from_nodes(s11.nodes)
        kunci11 = ("schemaName", "schemaAlternateTitle", "schemaLanguage", "schemaConstraintLanguage",
                   "schemaAscii", "schemaGraphicsURL")
        if any(d11.get(k) for k in kunci11):
            # Dibuat dari isian (template tidak memuat blok skema aplikasi)
            for old_as in gmd_root.findall(_q(GMD, "applicationSchemaInfo")):
                gmd_root.remove(old_as)
            app_schema = _anak(gmd_root, "applicationSchemaInfo", "MD_ApplicationSchemaInformation")
            nm_cit = _anak(app_schema, "name", "CI_Citation")
            _set_char(nm_cit, "title", d11.get("schemaName"))
            _set_char(nm_cit, "alternateTitle", d11.get("schemaAlternateTitle"))
            _set_char(app_schema, "schemaLanguage", d11.get("schemaLanguage"))
            _set_char(app_schema, "constraintLanguage", d11.get("schemaConstraintLanguage"))
            _set_char(app_schema, "schemaAscii", d11.get("schemaAscii"))
            if d11.get("schemaGraphicsURL"):
                gf = ET.SubElement(app_schema, _q(GMD, "graphicsFile"))
                ET.SubElement(gf, _q(GCO, "Binary")).set("src", _clean_str(d11["schemaGraphicsURL"]))
            if d11.get("schemaGraphicsName"):
                catatan.append("Nama berkas grafik skema tidak punya padanan di ISO 19139 (hanya tautan "
                               "berkasnya) — tidak diekspor.")

    # =========================================================================
    # TAHAP 12: PEMELIHARAAN DATA & METADATA
    # =========================================================================
    s12 = sec_map.get(12)
    if s12 and data_id is not None:
        d12 = _collect_dict_from_nodes(s12.nodes)

        # Pemeliharaan Data (resourceMaintenance)
        for n in s12.nodes:
            if isinstance(n, layout.BList) and "resourceMaintenance" in getattr(n, "path", ""):
                for old_rm in data_id.findall(_q(GMD, "resourceMaintenance")):
                    data_id.remove(old_rm)
                for inst in n.instances:
                    rm_d = _collect_dict_from_nodes(inst.nodes)
                    rm_wrap = ET.SubElement(data_id, _q(GMD, "resourceMaintenance"))
                    md_maint = ET.SubElement(rm_wrap, _q(GMD, "MD_MaintenanceInformation"))

                    if rm_d.get("maintenanceFrequency"):
                        _set_code(md_maint, "maintenanceAndUpdateFrequency", "MD_MaintenanceFrequencyCode", rm_d["maintenanceFrequency"])

                    # Tanggal Pemeliharaan / Update Data
                    if rm_d.get("maintenanceDate"):
                        dt_val = rm_d["maintenanceDate"].split("T")[0]
                        dnu = md_maint.find(_q(GMD, "dateOfNextUpdate"))
                        if dnu is None:
                            dnu = ET.SubElement(md_maint, _q(GMD, "dateOfNextUpdate"))
                        dnu.clear()
                        d_sub = ET.SubElement(dnu, _q(GCO, "Date"))
                        d_sub.text = dt_val

                    if rm_d.get("maintenanceScopeLevel"):
                        _set_code(md_maint, "updateScope", "MD_ScopeCode", rm_d["maintenanceScopeLevel"])
                    if rm_d.get("maintenanceNote"):
                        _set_char(md_maint, "maintenanceNote", rm_d["maintenanceNote"])

                    # Kontak Pemeliharaan
                    for c_node in inst.nodes:
                        if isinstance(c_node, layout.BList) and "contact" in getattr(c_node, "path", ""):
                            for c_inst in c_node.instances:
                                cd = _collect_dict_from_nodes(c_inst.nodes)
                                if any(cd.values()):
                                    md_maint.append(_build_contact_element("contact", cd))

        # Pemeliharaan Metadata
        meta_maint = gmd_root.find(f"{_q(GMD, 'metadataMaintenance')}/{_q(GMD, 'MD_MaintenanceInformation')}")
        if meta_maint is not None:
            if "metadataMaintenanceFrequency" in d12:
                _set_code(meta_maint, "maintenanceAndUpdateFrequency", "MD_MaintenanceFrequencyCode", d12["metadataMaintenanceFrequency"])
            if "metadataMaintenanceDate" in d12:
                dt_val = d12["metadataMaintenanceDate"].split("T")[0]
                dnu = meta_maint.find(_q(GMD, "dateOfNextUpdate"))
                if dnu is None:
                    dnu = ET.SubElement(meta_maint, _q(GMD, "dateOfNextUpdate"))
                dnu.clear()
                d_sub = ET.SubElement(dnu, _q(GCO, "Date"))
                d_sub.text = dt_val
            if "metadataMaintenanceScopeLevel" in d12:
                _set_code(meta_maint, "updateScope", "MD_ScopeCode", d12["metadataMaintenanceScopeLevel"])
            if "metadataMaintenanceNote" in d12:
                _set_char(meta_maint, "maintenanceNote", d12["metadataMaintenanceNote"])

            # Kontak Pemeliharaan Metadata
            for n in s12.nodes:
                if isinstance(n, layout.BList) and "metadataMaintenance/contact" in getattr(n, "path", ""):
                    for old_mc in meta_maint.findall(_q(GMD, "contact")):
                        meta_maint.remove(old_mc)
                    for inst in n.instances:
                        cd = _collect_dict_from_nodes(inst.nodes)
                        if any(cd.values()):
                            meta_maint.append(_build_contact_element("contact", cd))

    # =========================================================================
    # TAHAP 13: EKSTENSI METADATA
    # =========================================================================
    s13 = sec_map.get(13)
    if s13:
        d13 = _collect_dict_from_nodes(s13.nodes)
        on_keys = ["extensionOnlineURL", "extensionOnlineProtocol", "extensionOnlineApplicationProfile",
                   "extensionOnlineName", "extensionOnlineDescription", "extensionOnlineFunction"]
        elem_keys = [
            ("extendedElementName", "name"),
            ("extendedElementDefinition", "definition"),
            ("extendedElementObligation", "obligation"),
            ("extendedElementCondition", "condition"),
            ("extendedElementDataType", "dataType"),
            ("extendedElementMaxOccurrence", "maximumOccurrence"),
            ("extendedElementDomainValue", "domainValue"),
            ("extendedElementParentEntity", "parentEntity"),
            ("extendedElementRule", "rule"),
            ("extendedElementRationale", "rationale"),
        ]
        if any(k in d13 for k in on_keys) or any(k in d13 for k, _ in elem_keys):
            ext_el = gmd_root.find(f"{_q(GMD, 'metadataExtensionInfo')}/{_q(GMD, 'MD_MetadataExtensionInformation')}")
            if ext_el is None:
                ext_wrap = ET.SubElement(gmd_root, _q(GMD, "metadataExtensionInfo"))
                ext_el = ET.SubElement(ext_wrap, _q(GMD, "MD_MetadataExtensionInformation"))

            if any(k in d13 for k in on_keys):
                ol_wrap = ext_el.find(_q(GMD, "extensionOnLineResource"))
                if ol_wrap is None:
                    ol_wrap = ET.SubElement(ext_el, _q(GMD, "extensionOnLineResource"))
                ci_ol = ol_wrap.find(_q(GMD, "CI_OnlineResource"))
                if ci_ol is None:
                    ci_ol = ET.SubElement(ol_wrap, _q(GMD, "CI_OnlineResource"))
                if "extensionOnlineURL" in d13:
                    _set_url(ci_ol, "linkage", d13["extensionOnlineURL"])
                if "extensionOnlineProtocol" in d13:
                    _set_char(ci_ol, "protocol", d13["extensionOnlineProtocol"])
                if "extensionOnlineApplicationProfile" in d13:
                    _set_char(ci_ol, "applicationProfile", d13["extensionOnlineApplicationProfile"])
                if "extensionOnlineName" in d13:
                    _set_char(ci_ol, "name", d13["extensionOnlineName"])
                if "extensionOnlineDescription" in d13:
                    _set_char(ci_ol, "description", d13["extensionOnlineDescription"])
                if "extensionOnlineFunction" in d13:
                    _set_code(ci_ol, "function", "CI_OnLineFunctionCode", d13["extensionOnlineFunction"])

            if any(k in d13 for k, _ in elem_keys):
                eei_wrap = ext_el.find(_q(GMD, "extendedElementInformation"))
                if eei_wrap is None:
                    eei_wrap = ET.SubElement(ext_el, _q(GMD, "extendedElementInformation"))
                md_eei = eei_wrap.find(_q(GMD, "MD_ExtendedElementInformation"))
                if md_eei is None:
                    md_eei = ET.SubElement(eei_wrap, _q(GMD, "MD_ExtendedElementInformation"))

                for k, tag in elem_keys:
                    if k in d13:
                        if tag == "obligation":
                            # MD_ObligationCode di ISO 19139 adalah enumerasi (teks), bukan codelist
                            ob = _anak(md_eei, "obligation", "MD_ObligationCode")
                            ob.text = _clean_str(d13[k])
                        elif tag == "dataType":
                            _set_code(md_eei, "dataType", "MD_DatatypeCode", d13[k])
                        else:
                            _set_char(md_eei, tag, d13[k])

    # Bersihkan sisa tag XML yang tidak sengaja terbawa pada teks CharacterString
    for el in gmd_root.iter():
        if el.text and ("<" in el.text or "&lt;" in el.text):
            el.text = _clean_str(el.text)

    _rapikan(gmd_root, catatan)
    # Pesan yang sama (mis. dari beberapa tahap proses) cukup sekali
    catatan[:] = list(dict.fromkeys(catatan))
    if tidak_standar is not None:
        tidak_standar.extend(kesesuaian.kode_tidak_standar(gmd_root, "19139"))
    return gmd_root


def save_gmd_to_file(gmd_root, output_path):
    """Menyimpan berkas XML ISO 19139 tanpa deklarasi <?xml...?> agar kompatibel dengan CSW Transaction pycsw/Palapa."""
    register_gmd_namespaces()
    # Indentasi rapi
    if hasattr(ET, "indent"):
        ET.indent(gmd_root, space="  ")
    raw = ET.tostring(gmd_root, encoding="utf-8")
    text = raw.decode("utf-8")
    # Hapus deklarasi <?xml ...?> jika ada agar saat diunggah ke Palapa / pycsw tidak menimbulkan error sintaks
    text = re.sub(r"<\?xml[^>]*\?>\s*", "", text).strip() + "\n"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    return output_path
