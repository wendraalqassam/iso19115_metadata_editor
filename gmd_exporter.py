"""Modul ekspor ISO 19139 (namespace http://www.isotc211.org/2005/gmd).

Mengambil data metadata aktif (ISO 19115-3) dari EditorDialog/model dan
menghasilkan XML berbasis standar ISO 19139 menggunakan template gmd_template.xml.
"""
import copy
import datetime
import os
import re
import xml.etree.ElementTree as ET  # nosec B405

from . import layout

HERE = os.path.dirname(__file__)
GMD_TEMPLATE = os.path.join(HERE, "gmd_template.xml")

GMD = "http://www.isotc211.org/2005/gmd"
GCO = "http://www.isotc211.org/2005/gco"
GML = "http://www.opengis.net/gml"
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


def export_to_gmd(iso3_root, template_path=None):
    """Mengekspor pohon data ISO 19115-3 ke dokumen XML ISO 19139 (gmd)."""
    register_gmd_namespaces()
    tmpl_file = template_path or GMD_TEMPLATE
    if not os.path.exists(tmpl_file):
        raise FileNotFoundError(f"Template GMD tidak ditemukan di: {tmpl_file}")

    tree = ET.parse(tmpl_file)  # nosec B314
    gmd_root = tree.getroot()

    # Bangun struktur seksi dari form ISO 19115-3
    secs, _ = layout.build(iso3_root)
    sec_map = {s.id: s for s in secs}

    # =========================================================================
    # TAHAP 1: INFORMASI METADATA
    # =========================================================================
    s1 = sec_map.get(1)
    if s1:
        d1 = _collect_dict_from_nodes(s1.nodes)
        if "metadataIdentifier" in d1 and d1["metadataIdentifier"].strip():
            _set_char(gmd_root, "fileIdentifier", d1["metadataIdentifier"].strip())
        if "language" in d1 and d1["language"].strip():
            lang_val = d1["language"].strip()
            lang_el = gmd_root.find(_q(GMD, "language"))
            if lang_el is None:
                lang_el = ET.SubElement(gmd_root, _q(GMD, "language"))
            for c in list(lang_el):
                lang_el.remove(c)
            lc = ET.SubElement(lang_el, _q(GMD, "LanguageCode"))
            lc.set("codeList", "./resources/codeList.xml#LanguageCode")
            lc.set("codeListValue", lang_val)
            lc.text = lang_val
        if "characterEncoding" in d1 and d1["characterEncoding"].strip():
            _set_code(gmd_root, "characterSet", "MD_CharacterSetCode", d1["characterEncoding"].strip())
        p_val = _clean_str(d1.get("parentMetadata", ""))
        pi_el = gmd_root.find(_q(GMD, "parentIdentifier"))
        if pi_el is None:
            pi_el = ET.SubElement(gmd_root, _q(GMD, "parentIdentifier"))
        for c in list(pi_el):
            pi_el.remove(c)
        cs = ET.SubElement(pi_el, _q(GCO, "CharacterString"))
        cs.text = p_val
        if "metadataScope" in d1:
            _set_code(gmd_root, "hierarchyLevel", "MD_ScopeCode", d1["metadataScope"])
        if "scopeName" in d1:
            _set_char(gmd_root, "hierarchyLevelName", d1["scopeName"])
        if "metadataStandardTitle" in d1:
            _set_char(gmd_root, "metadataStandardName", d1["metadataStandardTitle"])
        if "metadataStandardEdition" in d1:
            _set_char(gmd_root, "metadataStandardVersion", d1["metadataStandardEdition"])

        # Kontak Metadata (s1)
        for n in s1.nodes:
            if isinstance(n, layout.BList) and getattr(n, "path", "") == "contact":
                for inst in n.instances:
                    cd = _collect_dict_from_nodes(inst.nodes)
                    if any(cd.values()):
                        # Ganti atau perbarui gmd:contact
                        old_c = gmd_root.find(_q(GMD, "contact"))
                        new_c = _build_contact_element("contact", cd)
                        if old_c is not None:
                            idx = list(gmd_root).index(old_c)
                            gmd_root.remove(old_c)
                            gmd_root.insert(idx, new_c)
                        else:
                            gmd_root.append(new_c)
                        break

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

        # Online Resource Data
        if "dataOnlineResourceURL" in d2:
            old_on = ci_cit.find(_q(GMD, "onlineResource"))
            new_on = _build_online_resource_element(
                "onlineResource",
                d2.get("dataOnlineResourceURL", ""),
                d2.get("dataOnlineResourceProtocol", ""),
                d2.get("dataOnlineResourceName", ""),
                function=d2.get("dataOnlineResourceFunction", "information"),
            )
            if old_on is not None:
                idx = list(ci_cit).index(old_on)
                ci_cit.remove(old_on)
                ci_cit.insert(idx, new_on)
            else:
                ci_cit.append(new_on)

        # Kontak Sitasi Data (citedResponsibleParty)
        for n in s2.nodes:
            if isinstance(n, layout.BList) and "citedResponsibleParty" in getattr(n, "path", ""):
                for old_crp in ci_cit.findall(_q(GMD, "citedResponsibleParty")):
                    ci_cit.remove(old_crp)
                for inst in n.instances:
                    cd = _collect_dict_from_nodes(inst.nodes)
                    if any(cd.values()):
                        ci_cit.append(_build_contact_element("citedResponsibleParty", cd))

        # Deskripsi umum
        if "dataAbstract" in d2:
            _set_char(data_id, "abstract", d2["dataAbstract"])
        if "dataPurpose" in d2:
            _set_char(data_id, "purpose", d2["dataPurpose"])
        if "dataCredit" in d2:
            _set_char(data_id, "credit", d2["dataCredit"])
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
                    if t_val:
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
    feat_cat = gmd_root.find(f"{_q(GMD, 'contentInfo')}/{_q(GMD, 'MD_FeatureCatalogueDescription')}")
    if s5 and feat_cat is not None:
        d5 = _collect_dict_from_nodes(s5.nodes)
        if "featureCatalogueCompliance" in d5:
            comp_el = feat_cat.find(_q(GMD, "complianceCode"))
            if comp_el is None:
                comp_el = ET.SubElement(feat_cat, _q(GMD, "complianceCode"))
            comp_el.clear()
            b_sub = ET.SubElement(comp_el, _q(GCO, "Boolean"))
            b_sub.text = d5["featureCatalogueCompliance"]
        if "featureCatalogueIncluded" in d5:
            inc_el = feat_cat.find(_q(GMD, "includedWithDataset"))
            if inc_el is None:
                inc_el = ET.SubElement(feat_cat, _q(GMD, "includedWithDataset"))
            inc_el.clear()
            b_sub = ET.SubElement(inc_el, _q(GCO, "Boolean"))
            b_sub.text = d5["featureCatalogueIncluded"]

        # Feature Types
        for n in s5.nodes:
            if isinstance(n, layout.BOptional) and n.present:
                for sub_n in n.nodes:
                    if isinstance(sub_n, layout.BList) and getattr(sub_n, "path", "") == "featureTypes":
                        for old_ft in feat_cat.findall(_q(GMD, "featureTypes")):
                            feat_cat.remove(old_ft)
                        for inst in sub_n.instances:
                            ft_d = _collect_dict_from_nodes(inst.nodes)
                            ft_name = ft_d.get("name")
                            if ft_name:
                                ft_el = ET.SubElement(feat_cat, _q(GMD, "featureTypes"))
                                cs = ET.SubElement(ft_el, _q(GCO, "CharacterString"))
                                cs.text = ft_name

        fc_cit = feat_cat.find(f"{_q(GMD, 'featureCatalogueCitation')}/{_q(GMD, 'CI_Citation')}")
        if fc_cit is not None:
            if "catalogueTitle" in d5:
                _set_char(fc_cit, "title", d5["catalogueTitle"])
            if "catalogueAlternateTitle" in d5:
                _set_char(fc_cit, "alternateTitle", d5["catalogueAlternateTitle"])
            if "catalogueEdition" in d5:
                _set_char(fc_cit, "edition", d5["catalogueEdition"])
            if "catalogueURL" in d5:
                ol = fc_cit.find(_q(GMD, "onlineResource"))
                if ol is None:
                    ol = ET.SubElement(fc_cit, _q(GMD, "onlineResource"))
                ci_ol = ol.find(_q(GMD, "CI_OnlineResource"))
                if ci_ol is None:
                    ci_ol = ET.SubElement(ol, _q(GMD, "CI_OnlineResource"))
                _set_url(ci_ol, "linkage", d5["catalogueURL"])

    # =========================================================================
    # TAHAP 6: DISTRIBUSI & AKSES DATA
    # =========================================================================
    dist_info = gmd_root.find(f"{_q(GMD, 'distributionInfo')}/{_q(GMD, 'MD_Distribution')}")
    s6 = sec_map.get(6)
    if s6 and dist_info is not None:
        d6 = _collect_dict_from_nodes(s6.nodes)

        # Distribution Format
        for n in s6.nodes:
            if isinstance(n, layout.BList) and "distributionFormat" in getattr(n, "path", ""):
                for old_df in dist_info.findall(_q(GMD, "distributionFormat")):
                    dist_info.remove(old_df)
                for inst in n.instances:
                    df_d = _collect_dict_from_nodes(inst.nodes)
                    df_title = df_d.get("title") or df_d.get("alternateTitle")
                    if df_title:
                        df_el = ET.SubElement(dist_info, _q(GMD, "distributionFormat"))
                        mdf = ET.SubElement(df_el, _q(GMD, "MD_Format"))
                        _set_char(mdf, "name", df_title)
                        if df_d.get("edition"):
                            _set_char(mdf, "version", df_d["edition"])
        if dist_info.find(_q(GMD, "distributionFormat")) is None:
            df_el = ET.SubElement(dist_info, _q(GMD, "distributionFormat"))
            df_el.set(_q(GCO, "nilReason"), "missing")

            # Distributor Contact
            if isinstance(n, layout.BList) and "distributorContact" in getattr(n, "path", ""):
                dist_el = dist_info.find(_q(GMD, "distributor"))
                if dist_el is None:
                    dist_el = ET.SubElement(dist_info, _q(GMD, "distributor"))
                md_dist = dist_el.find(_q(GMD, "MD_Distributor"))
                if md_dist is None:
                    md_dist = ET.SubElement(dist_el, _q(GMD, "MD_Distributor"))
                for inst in n.instances:
                    cd = _collect_dict_from_nodes(inst.nodes)
                    if any(cd.values()):
                        old_dc = md_dist.find(_q(GMD, "distributorContact"))
                        new_dc = _build_contact_element("distributorContact", cd)
                        if old_dc is not None:
                            idx = list(md_dist).index(old_dc)
                            md_dist.remove(old_dc)
                            md_dist.insert(idx, new_dc)
                        else:
                            md_dist.append(new_dc)
                        break

            # Online Transfer Options
            if isinstance(n, layout.BList) and "onLine" in getattr(n, "path", ""):
                to_el = dist_info.find(f"{_q(GMD, 'transferOptions')}/{_q(GMD, 'MD_DigitalTransferOptions')}")
                if to_el is not None:
                    for old_ol in to_el.findall(_q(GMD, "onLine")):
                        to_el.remove(old_ol)
                    for inst in n.instances:
                        od = _collect_dict_from_nodes(inst.nodes)
                        if od.get("url"):
                            to_el.append(_build_online_resource_element(
                                "onLine",
                                od["url"],
                                od.get("protocol", ""),
                                od.get("name", ""),
                                od.get("description", ""),
                                od.get("function", "download"),
                            ))

        # Units and Transfer Size
        to_el = dist_info.find(f"{_q(GMD, 'transferOptions')}/{_q(GMD, 'MD_DigitalTransferOptions')}")
        if to_el is not None:
            if "unitsOfDistribution" in d6:
                _set_char(to_el, "unitsOfDistribution", d6["unitsOfDistribution"])
            if "transferSize" in d6:
                ts_el = to_el.find(_q(GMD, "transferSize"))
                if ts_el is None:
                    ts_el = ET.SubElement(to_el, _q(GMD, "transferSize"))
                ts_el.clear()
                sub_r = ET.SubElement(ts_el, _q(GCO, "Real"))
                sub_r.text = str(d6["transferSize"])

    # =========================================================================
    # TAHAP 7: KUALITAS DATA
    # =========================================================================
    s7 = sec_map.get(7)
    if s7:
        d7 = _collect_dict_from_nodes(s7.nodes)
        has_reports = _has_list_data(s7.nodes, "report")
        if any(d7.values()) or has_reports:
            dq_report = None
            for dq_el in gmd_root.findall(f"{_q(GMD, 'dataQualityInfo')}/{_q(GMD, 'DQ_DataQuality')}"):
                if dq_el.find(_q(GMD, "lineage")) is None:
                    dq_report = dq_el
                    break
            if dq_report is None:
                dqi = ET.SubElement(gmd_root, _q(GMD, "dataQualityInfo"))
                dq_report = ET.SubElement(dqi, _q(GMD, "DQ_DataQuality"))

            if "qualityScope" in d7:
                sc_el = dq_report.find(f"{_q(GMD, 'scope')}/{_q(GMD, 'DQ_Scope')}")
                if sc_el is None:
                    sc_wrap = ET.SubElement(dq_report, _q(GMD, "scope"))
                    sc_el = ET.SubElement(sc_wrap, _q(GMD, "DQ_Scope"))
                _set_code(sc_el, "level", "MD_ScopeCode", d7["qualityScope"])

            for n in s7.nodes:
                if isinstance(n, layout.BList) and "report" in getattr(n, "path", ""):
                    for old_rep in dq_report.findall(_q(GMD, "report")):
                        dq_report.remove(old_rep)
                    for inst in n.instances:
                        rep_d = _collect_dict_from_nodes(inst.nodes)
                        rep_wrap = ET.SubElement(dq_report, _q(GMD, "report"))
                        dq_elem = ET.SubElement(rep_wrap, _q(GMD, "DQ_DomainConsistency"))

                        if rep_d.get("measure") or rep_d.get("description"):
                            md_wrap = ET.SubElement(dq_elem, _q(GMD, "measureDescription"))
                            md_inner = ET.SubElement(md_wrap, _q(GMD, "measureDescription"))
                            if rep_d.get("measure"):
                                _set_char(md_inner, "nameOfMeasure", rep_d["measure"])
                            if rep_d.get("description"):
                                _set_char(md_inner, "measureDescription", rep_d["description"])

                        if rep_d.get("evaluationMethodDescription") or rep_d.get("evaluationMethodType"):
                            emd_wrap = ET.SubElement(dq_elem, _q(GMD, "evaluationMethodDescription"))
                            emd_inner = ET.SubElement(emd_wrap, _q(GMD, "evaluationMethodDescription"))
                            emd_deep = ET.SubElement(emd_inner, _q(GMD, "evaluationMethodDescription"))
                            if rep_d.get("evaluationMethodDescription"):
                                _set_char(emd_deep, "evaluationMethodDescription", rep_d["evaluationMethodDescription"])
                            if rep_d.get("evaluationMethodType"):
                                _set_code(emd_deep, "evaluationMethodType", "DQ_EvaluationMethodTypeCode", rep_d["evaluationMethodType"], "./resources/codeList.xml#DQ_EvaluationMethodTypeCode")

                        for r_node in inst.nodes:
                            if isinstance(r_node, layout.BList) and getattr(r_node, "path", "") == "result":
                                for r_inst in r_node.instances:
                                    res_d = _collect_dict_from_nodes(r_inst.nodes)
                                    res_wrap = ET.SubElement(dq_elem, _q(GMD, "result"))
                                    conf_res = ET.SubElement(res_wrap, _q(GMD, "DQ_ConformanceResult"))
                                    if res_d.get("dateTime"):
                                        dt_wrap = ET.SubElement(conf_res, _q(GMD, "dateTime"))
                                        sub_dt = ET.SubElement(dt_wrap, _q(GCO, "DateTime"))
                                        sub_dt.text = res_d["dateTime"]
                                    if res_d.get("resultScope"):
                                        rsc_wrap = ET.SubElement(conf_res, _q(GMD, "resultScope"))
                                        rsc_dq = ET.SubElement(rsc_wrap, _q(GMD, "DQ_Scope"))
                                        _set_code(rsc_dq, "level", "MD_ScopeCode", res_d["resultScope"])
                                    if res_d.get("specificationTitle") or res_d.get("specificationAlternate"):
                                        sp_wrap = ET.SubElement(conf_res, _q(GMD, "specification"))
                                        ci_sp = ET.SubElement(sp_wrap, _q(GMD, "CI_Citation"))
                                        if res_d.get("specificationTitle"):
                                            _set_char(ci_sp, "title", res_d["specificationTitle"])
                                        if res_d.get("specificationAlternate"):
                                            _set_char(ci_sp, "alternateTitle", res_d["specificationAlternate"])
                                        # date wajib di CI_Citation spesifikasi
                                        if ci_sp.find(_q(GMD, "date")) is None:
                                            d_sub = ET.SubElement(ci_sp, _q(GMD, "date"))
                                            ci_d = ET.SubElement(d_sub, _q(GMD, "CI_Date"))
                                            dt_sub = ET.SubElement(ci_d, _q(GMD, "date"))
                                            dt_sub.set(_q(GCO, "nilReason"), "missing")
                                            dt_type = ET.SubElement(ci_d, _q(GMD, "dateType"))
                                            tc = ET.SubElement(dt_type, _q(GMD, "CI_DateTypeCode"))
                                            tc.set("codeList", "./resources/codeList.xml#CI_DateTypeCode")
                                            tc.set("codeListValue", "publication")
                                            tc.text = "publication"
                                    if res_d.get("explanation"):
                                        _set_char(conf_res, "explanation", res_d["explanation"])
                                    if res_d.get("pass"):
                                        p_el = ET.SubElement(conf_res, _q(GMD, "pass"))
                                        b_sub = ET.SubElement(p_el, _q(GCO, "Boolean"))
                                        b_sub.text = str(res_d["pass"]).lower()

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
            dq_lineage = None
            for dq_el in gmd_root.findall(f"{_q(GMD, 'dataQualityInfo')}/{_q(GMD, 'DQ_DataQuality')}"):
                if dq_el.find(_q(GMD, "lineage")) is not None:
                    dq_lineage = dq_el
                    break
            if dq_lineage is None:
                dqi = ET.SubElement(gmd_root, _q(GMD, "dataQualityInfo"))
                dq_lineage = ET.SubElement(dqi, _q(GMD, "DQ_DataQuality"))
                sc = ET.SubElement(dq_lineage, _q(GMD, "scope"))
                dqs = ET.SubElement(sc, _q(GMD, "DQ_Scope"))
                lvl = ET.SubElement(dqs, _q(GMD, "level"))
                sc_code = ET.SubElement(lvl, _q(GMD, "MD_ScopeCode"))
                sc_code.set("codeList", "./resources/codeList.xml#MD_ScopeCode")
                sc_code.set("codeListValue", "dataset")
                sc_code.text = "dataset"
                lin_wrap = ET.SubElement(dq_lineage, _q(GMD, "lineage"))
                ET.SubElement(lin_wrap, _q(GMD, "LI_Lineage"))

            lin_el = dq_lineage.find(f"{_q(GMD, 'lineage')}/{_q(GMD, 'LI_Lineage')}")
            if lin_el is not None:
                if "lineageStatement" in d8:
                    _set_char(lin_el, "statement", d8["lineageStatement"])

                if "lineageScopeLevel" in d8:
                    sc_el = lin_el.find(_q(GMD, "scope"))
                    if sc_el is None:
                        sc_el = ET.SubElement(lin_el, _q(GMD, "scope"))
                    _set_code(sc_el, "level", "MD_ScopeCode", d8["lineageScopeLevel"])

                for n in s8.nodes:
                    if isinstance(n, layout.BList) and getattr(n, "path", "").endswith("processStep"):
                        for old_ps in lin_el.findall(_q(GMD, "processStep")):
                            lin_el.remove(old_ps)
                        for inst in n.instances:
                            ps_d = _collect_dict_from_nodes(inst.nodes)
                            if not any(ps_d.values()):
                                continue
                            ps_wrap = ET.SubElement(lin_el, _q(GMD, "processStep"))
                            li_ps = ET.SubElement(ps_wrap, _q(GMD, "LI_ProcessStep"))
                            if ps_d.get("description"):
                                _set_char(li_ps, "description", ps_d["description"])
                            if ps_d.get("rationale"):
                                _set_char(li_ps, "rationale", ps_d["rationale"])
                            if ps_d.get("stepDateTime"):
                                dt_wrap = ET.SubElement(li_ps, _q(GMD, "dateTime"))
                                sub_dt = ET.SubElement(dt_wrap, _q(GCO, "DateTime"))
                                sub_dt.text = ps_d["stepDateTime"]
                            if ps_d.get("processorName"):
                                proc_data = {
                                    "organization": ps_d["processorName"],
                                    "role": ps_d.get("processorRole", "processor"),
                                }
                                li_ps.append(_build_contact_element("processor", proc_data))
                            if ps_d.get("referenceTitle"):
                                ps_src = ET.SubElement(li_ps, _q(GMD, "source"))
                                ci_ps = ET.SubElement(ps_src, _q(GMD, "CI_Citation"))
                                _set_char(ci_ps, "title", ps_d["referenceTitle"])
                            if ps_d.get("scopeLevel"):
                                sc_ps = ET.SubElement(li_ps, _q(GMD, "scope"))
                                _set_code(sc_ps, "level", "MD_ScopeCode", ps_d["scopeLevel"])

                    elif isinstance(n, layout.BList) and getattr(n, "path", "").endswith("source"):
                        for old_src in lin_el.findall(_q(GMD, "source")):
                            lin_el.remove(old_src)
                        for inst in n.instances:
                            src_d = _collect_dict_from_nodes(inst.nodes)
                            if not any(src_d.values()):
                                continue
                            src_wrap = ET.SubElement(lin_el, _q(GMD, "source"))
                            li_src = ET.SubElement(src_wrap, _q(GMD, "LI_Source"))
                            if src_d.get("description"):
                                _set_char(li_src, "description", src_d["description"])
                            if src_d.get("spatialResolution"):
                                sr_wrap = ET.SubElement(li_src, _q(GMD, "sourceSpatialResolution"))
                                md_res = ET.SubElement(sr_wrap, _q(GMD, "MD_Resolution"))
                                dist_el = ET.SubElement(md_res, _q(GMD, "distance"))
                                sub_dist = ET.SubElement(dist_el, _q(GCO, "Distance"))
                                sub_dist.set("uom", "m")
                                sub_dist.text = str(src_d["spatialResolution"])
                            if src_d.get("referenceSystemCode") or src_d.get("referenceSystemCodeSpace"):
                                srs_wrap = ET.SubElement(li_src, _q(GMD, "sourceReferenceSystem"))
                                md_rs = ET.SubElement(srs_wrap, _q(GMD, "MD_ReferenceSystem"))
                                rs_id = ET.SubElement(md_rs, _q(GMD, "referenceSystemIdentifier"))
                                md_id = ET.SubElement(rs_id, _q(GMD, "MD_Identifier"))
                                if src_d.get("referenceSystemCode"):
                                    _set_char(md_id, "code", src_d["referenceSystemCode"])
                                if src_d.get("referenceSystemCodeSpace"):
                                    _set_char(md_id, "codeSpace", src_d["referenceSystemCodeSpace"])
                            if src_d.get("citationTitle") or src_d.get("citationDate"):
                                cit_s = ET.SubElement(li_src, _q(GMD, "sourceCitation"))
                                ci_s = ET.SubElement(cit_s, _q(GMD, "CI_Citation"))
                                if src_d.get("citationTitle"):
                                    _set_char(ci_s, "title", src_d["citationTitle"])
                                if src_d.get("citationDate"):
                                    d_wrap = ET.SubElement(ci_s, _q(GMD, "date"))
                                    ci_d = ET.SubElement(d_wrap, _q(GMD, "CI_Date"))
                                    dt_wrap = ET.SubElement(ci_d, _q(GMD, "date"))
                                    tag_t = "DateTime" if "T" in src_d["citationDate"] else "Date"
                                    sub_dt = ET.SubElement(dt_wrap, _q(GCO, tag_t))
                                    sub_dt.text = src_d["citationDate"]
                                    dt_type = ET.SubElement(ci_d, _q(GMD, "dateType"))
                                    tc_el = ET.SubElement(dt_type, _q(GMD, "CI_DateTypeCode"))
                                    tc_el.set("codeList", "./resources/codeList.xml#CI_DateTypeCode")
                                    tc_val = src_d.get("citationDateType") or "creation"
                                    tc_el.set("codeListValue", tc_val)
                                    tc_el.text = tc_val
                            if src_d.get("metadataTitle"):
                                sm_s = ET.SubElement(li_src, _q(GMD, "sourceMetadata"))
                                ci_sm = ET.SubElement(sm_s, _q(GMD, "CI_Citation"))
                                _set_char(ci_sm, "title", src_d["metadataTitle"])
                            if src_d.get("scopeLevel"):
                                sc_s = ET.SubElement(li_src, _q(GMD, "scope"))
                                _set_code(sc_s, "level", "MD_ScopeCode", src_d["scopeLevel"])

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
            if "portrayalCatalogueURL" in d9:
                ol_wrap = ci_pc.find(_q(GMD, "onlineResource"))
                if ol_wrap is None:
                    ol_wrap = ET.SubElement(ci_pc, _q(GMD, "onlineResource"))
                ci_ol = ol_wrap.find(_q(GMD, "CI_OnlineResource"))
                if ci_ol is None:
                    ci_ol = ET.SubElement(ol_wrap, _q(GMD, "CI_OnlineResource"))
                _set_url(ci_ol, "linkage", d9["portrayalCatalogueURL"])

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
        for rc in data_id.findall(f"{_q(GMD, 'resourceConstraints')}/{_q(GMD, 'MD_Constraints')}"):
            if "useLimitation" in d10:
                _set_char(rc, "useLimitation", d10["useLimitation"])
        for rc in data_id.findall(f"{_q(GMD, 'resourceConstraints')}/{_q(GMD, 'MD_LegalConstraints')}"):
            if "accessConstraints" in d10:
                _set_code(rc, "accessConstraints", "MD_RestrictionCode", d10["accessConstraints"])
            if "useConstraints" in d10:
                _set_code(rc, "useConstraints", "MD_RestrictionCode", d10["useConstraints"])
            if "otherConstraints" in d10:
                _set_char(rc, "otherConstraints", d10["otherConstraints"])
        for rc in data_id.findall(f"{_q(GMD, 'resourceConstraints')}/{_q(GMD, 'MD_SecurityConstraints')}"):
            if "securityClassification" in d10:
                _set_code(rc, "classification", "MD_ClassificationCode", d10["securityClassification"])
            if "securityUserNote" in d10:
                _set_char(rc, "userNote", d10["securityUserNote"])
            if "securitySystem" in d10:
                _set_char(rc, "classificationSystem", d10["securitySystem"])

        # Metadata Constraints (di root)
        for mc in gmd_root.findall(f"{_q(GMD, 'metadataConstraints')}/{_q(GMD, 'MD_Constraints')}"):
            if "metadataUseLimitation" in d10:
                _set_char(mc, "useLimitation", d10["metadataUseLimitation"])
        for mc in gmd_root.findall(f"{_q(GMD, 'metadataConstraints')}/{_q(GMD, 'MD_LegalConstraints')}"):
            if "metadataOtherConstraints" in d10:
                _set_char(mc, "otherConstraints", d10["metadataOtherConstraints"])
        for mc in gmd_root.findall(f"{_q(GMD, 'metadataConstraints')}/{_q(GMD, 'MD_SecurityConstraints')}"):
            if "metadataSecurityClassification" in d10:
                _set_code(mc, "classification", "MD_ClassificationCode", d10["metadataSecurityClassification"])
            if "metadataSecurityUserNote" in d10:
                _set_char(mc, "userNote", d10["metadataSecurityUserNote"])

    # =========================================================================
    # TAHAP 11: SKEMA APLIKASI
    # =========================================================================
    s11 = sec_map.get(11)
    app_schema = gmd_root.find(f"{_q(GMD, 'applicationSchemaInfo')}/{_q(GMD, 'MD_ApplicationSchemaInformation')}")
    if s11 and app_schema is not None:
        d11 = _collect_dict_from_nodes(s11.nodes)
        if "schemaName" in d11:
            nm_cit = app_schema.find(f"{_q(GMD, 'name')}/{_q(GMD, 'CI_Citation')}")
            if nm_cit is not None:
                _set_char(nm_cit, "title", d11["schemaName"])
        if "schemaLanguage" in d11:
            _set_char(app_schema, "schemaLanguage", d11["schemaLanguage"])
        if "schemaConstraintLanguage" in d11:
            _set_char(app_schema, "constraintLanguage", d11["schemaConstraintLanguage"])
        if "schemaAscii" in d11:
            _set_char(app_schema, "schemaAscii", d11["schemaAscii"])

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
                    _set_code(ci_ol, "function", "CI_OnLineFunctionCode", d13["extensionOnlineFunction"], "./resources/codeList.xml#CI_OnLineFunctionCode")

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
                            _set_code(md_eei, "obligation", "MD_ObligationCode", d13[k], "./resources/codeList.xml#MD_ObligationCode")
                        elif tag == "dataType":
                            _set_code(md_eei, "dataType", "MD_DatatypeCode", d13[k], "./resources/codeList.xml#MD_DatatypeCode")
                        else:
                            _set_char(md_eei, tag, d13[k])

    # Bersihkan sisa tag XML yang tidak sengaja terbawa pada teks CharacterString
    for el in gmd_root.iter():
        if el.text and ("<" in el.text or "&lt;" in el.text):
            el.text = _clean_str(el.text)

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
