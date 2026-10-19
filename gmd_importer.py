"""Modul impor XML berstandar ISO 19139 (namespace http://www.isotc211.org/2005/gmd)
ke struktur model ISO 19115-3 internal GeoMDB.

Mendukung konversi otomatis saat pengguna membuka berkas XML ISO 19139 (gmd)
melalui tombol 'Buka XML Metadata...', sehingga seluruh form (Tahap 1-13)
terisi penuh tanpa ada isian yang hilang/kosong.
"""
import copy
import datetime
import os
import re
import xml.etree.ElementTree as ET

from . import layout, model

GMD = "http://www.isotc211.org/2005/gmd"
GCO = "http://www.isotc211.org/2005/gco"
GML = "http://www.opengis.net/gml"
GTS = "http://www.isotc211.org/2005/gts/"

ID = layout.ID


def _q(ns, tag):
    return f"{{{ns}}}{tag}"


def is_gmd(root_or_path):
    """Memeriksa apakah berkas/elemen merupakan dokumen ISO 19139 (gmd)."""
    if isinstance(root_or_path, str):
        if not os.path.exists(root_or_path):
            return False
        try:
            with open(root_or_path, "rb") as f:
                head = f.read(2048).decode("utf-8-sig", errors="ignore")
                return ("http://www.isotc211.org/2005/gmd" in head and "MD_Metadata" in head)
        except Exception:
            return False
    if hasattr(root_or_path, "tag"):
        tag = root_or_path.tag
        return (tag == _q(GMD, "MD_Metadata") or
                (tag.endswith("MD_Metadata") and "2005/gmd" in str(tag)))
    return False


def get_text(parent, path):
    if parent is None:
        return ""
    el = parent.find(path)
    if el is None:
        return ""
    cs = el.find(_q(GCO, "CharacterString"))
    if cs is not None and cs.text:
        return cs.text.strip()
    for child in el:
        if child.text and child.text.strip():
            return child.text.strip()
    return (el.text or "").strip()


def get_code(parent, path):
    if parent is None:
        return ""
    el = parent.find(path)
    if el is None:
        return ""
    for child in el:
        if "codeListValue" in child.attrib:
            return child.attrib["codeListValue"].strip()
        if child.text and child.text.strip():
            return child.text.strip()
    return (el.text or "").strip()


def parse_contact(rp):
    if rp is None:
        return {}
    ind = get_text(rp, _q(GMD, "individualName"))
    org = get_text(rp, _q(GMD, "organisationName"))
    pos = get_text(rp, _q(GMD, "positionName"))
    role = get_code(rp, _q(GMD, "role")) or "pointOfContact"

    ci = rp.find(f"{_q(GMD, 'contactInfo')}/{_q(GMD, 'CI_Contact')}")
    if ci is None:
        nested_rp = rp.find(f"{_q(GMD, 'contactInfo')}/{_q(GMD, 'CI_ResponsibleParty')}")
        if nested_rp is not None:
            if not org:
                org = get_text(nested_rp, _q(GMD, "name"))
            if not ind:
                ind = get_text(nested_rp, f"{_q(GMD, 'individual')}/{_q(GMD, 'individualName')}/{_q(GMD, 'name')}")
            if not pos:
                pos = get_text(nested_rp, f"{_q(GMD, 'individual')}/{_q(GMD, 'positionName')}")
            ci = nested_rp.find(f"{_q(GMD, 'contactInfo')}/{_q(GMD, 'CI_Contact')}")

    phone, fax, email = "", "", ""
    addr, city, prov, pcode, country = "", "", "", "", ""
    hours, instrs = "", ""
    if ci is not None:
        for tel in ci.findall(f"{_q(GMD, 'phone')}/{_q(GMD, 'CI_Telephone')}"):
            v = get_text(tel, _q(GMD, "voice"))
            f = get_text(tel, _q(GMD, "facsimile"))
            if v and not phone:
                phone = v
            if f and not fax:
                fax = f
        ad_el = ci.find(f"{_q(GMD, 'address')}/{_q(GMD, 'CI_Address')}")
        if ad_el is not None:
            addr = get_text(ad_el, _q(GMD, "deliveryPoint"))
            city = get_text(ad_el, _q(GMD, "city"))
            prov = get_text(ad_el, _q(GMD, "administrativeArea"))
            pcode = get_text(ad_el, _q(GMD, "postalCode"))
            country = get_text(ad_el, _q(GMD, "country"))
            email = get_text(ad_el, _q(GMD, "electronicMailAddress"))
        hours = get_text(ci, _q(GMD, "hoursOfService"))
        instrs = get_text(ci, _q(GMD, "contactInstructions"))

    res = {
        "role": role,
        "organization": org,
        "individual": ind,
        "position": pos,
        "phone": phone,
        "fax": fax,
        "email": email,
        "address": addr,
        "city": city,
        "province": prov,
        "postalCode": pcode,
        "country": country,
        "hours": hours,
        "instructions": instrs,
    }
    return {k: v for k, v in res.items() if v}


def parse_online(res_el):
    if res_el is None:
        return {}
    ci = res_el.find(_q(GMD, "CI_OnlineResource"))
    if ci is None:
        ci = res_el
    return {
        "url": get_text(ci, _q(GMD, "linkage")),
        "protocol": get_text(ci, _q(GMD, "protocol")),
        "name": get_text(ci, _q(GMD, "name")),
        "description": get_text(ci, _q(GMD, "description")),
        "function": get_code(ci, _q(GMD, "function")) or "information",
    }


def extract_gmd_plan(gmd_root_or_path):
    """Mengekstrak seluruh nilai elemen dari berkas/akar XML ISO 19139 ke format Plan GeoMDB."""
    if isinstance(gmd_root_or_path, str):
        gmd_root = ET.parse(gmd_root_or_path).getroot()
    else:
        gmd_root = gmd_root_or_path

    plan = {"fields": [], "optionals": [], "lists": [], "contacts": [], "notes": []}
    F = plan["fields"].append
    OPT = plan["optionals"].append
    LST = plan["lists"].append

    # --- TAHAP 1: INFORMASI METADATA ---
    fid = get_text(gmd_root, _q(GMD, "fileIdentifier"))
    if fid:
        F((1, "metadataIdentifier", fid))
    lang = get_text(gmd_root, _q(GMD, "language"))
    if lang:
        F((1, "language", lang))
    cs = get_code(gmd_root, _q(GMD, "characterSet"))
    if cs:
        F((1, "characterEncoding", cs))
    country = get_code(gmd_root, f"{_q(GMD, 'locale')}/{_q(GMD, 'PT_Locale')}/{_q(GMD, 'country')}") or get_text(gmd_root, f"{_q(GMD, 'locale')}/{_q(GMD, 'PT_Locale')}/{_q(GMD, 'country')}")
    if country:
        F((1, "country", country))
    pid = get_text(gmd_root, _q(GMD, "parentIdentifier"))
    if pid:
        F((1, "parentMetadata", pid))
    hl = get_code(gmd_root, _q(GMD, "hierarchyLevel"))
    if hl:
        F((1, "metadataScope", hl))
    hln = get_text(gmd_root, _q(GMD, "hierarchyLevelName"))
    if hln:
        F((1, "scopeName", hln))
    date_stamps = []
    for ds_el in gmd_root.findall(_q(GMD, "dateStamp")):
        val = get_text(ds_el, f"{_q(GCO, 'DateTime')}") or get_text(ds_el, f"{_q(GCO, 'Date')}") or get_text(ds_el, ".")
        if val:
            dtype = "creation" if len(date_stamps) == 0 else "revision"
            date_stamps.append({"date": val, "type": dtype})
    if date_stamps:
        LST((1, "dateInfo", date_stamps))
    msn = get_text(gmd_root, _q(GMD, "metadataStandardName"))
    if msn:
        F((1, "metadataStandardTitle", msn))
    msv = get_text(gmd_root, _q(GMD, "metadataStandardVersion"))
    if msv:
        F((1, "metadataStandardEdition", msv))

    # Kontak root (Tahap 1)
    root_contacts = []
    for c_el in gmd_root.findall(_q(GMD, "contact")):
        cd = parse_contact(c_el.find(_q(GMD, "CI_ResponsibleParty")))
        if cd:
            root_contacts.append(cd)
            if cd.get("organization") or cd.get("individual"):
                plan["contacts"].append((cd.get("organization") or cd.get("individual"), cd))
    if root_contacts:
        LST((1, "contact", root_contacts))

    # --- TAHAP 2: IDENTITAS DATA ---
    data_id = gmd_root.find(f"{_q(GMD, 'identificationInfo')}/{_q(GMD, 'MD_DataIdentification')}")
    if data_id is not None:
        cit = data_id.find(f"{_q(GMD, 'citation')}/{_q(GMD, 'CI_Citation')}")
        if cit is not None:
            t = get_text(cit, _q(GMD, "title"))
            if t:
                F((2, "dataTitle", t))
            at = get_text(cit, _q(GMD, "alternateTitle"))
            if at:
                F((2, "dataAlternateTitle", at))
            ed = get_text(cit, _q(GMD, "edition"))
            if ed:
                F((2, "dataEdition", ed))
            ed_d = get_text(cit, _q(GMD, "editionDate"))
            if ed_d:
                F((2, "dataEditionDate", ed_d))
            pf = get_code(cit, _q(GMD, "presentationForm"))
            if pf:
                F((2, "presentationForm", pf))

            for d_el in cit.findall(_q(GMD, "date")):
                tc = get_code(d_el, f"{_q(GMD, 'CI_Date')}/{_q(GMD, 'dateType')}")
                val = get_text(d_el, f"{_q(GMD, 'CI_Date')}/{_q(GMD, 'date')}")
                if val:
                    if tc == "creation":
                        F((2, "dataCreationDate", val))
                    elif tc == "publication":
                        F((2, "dataPublicationDate", val))
                    elif tc == "revision":
                        F((2, "dataRevisionDate", val))

            ol = cit.find(_q(GMD, "onlineResource"))
            if ol is not None:
                od = parse_online(ol)
                if od.get("url"):
                    F((2, "dataOnlineResourceURL", od["url"]))
                    if od.get("name"):
                        F((2, "dataOnlineResourceName", od["name"]))
                    if od.get("protocol"):
                        F((2, "dataOnlineResourceProtocol", od["protocol"]))
                    if od.get("function"):
                        F((2, "dataOnlineResourceFunction", od["function"]))

            cited_p = []
            for cp in cit.findall(_q(GMD, "citedResponsibleParty")):
                cd = parse_contact(cp.find(_q(GMD, "CI_ResponsibleParty")))
                if cd:
                    cited_p.append(cd)
            if cited_p:
                LST((2, ID + "citation/citedResponsibleParty", cited_p))

        ab = get_text(data_id, _q(GMD, "abstract"))
        if ab:
            F((2, "dataAbstract", ab))
        pu = get_text(data_id, _q(GMD, "purpose"))
        if pu:
            F((2, "dataPurpose", pu))
        cr = get_text(data_id, _q(GMD, "credit"))
        if cr:
            F((2, "dataCredit", cr))
        st = get_code(data_id, _q(GMD, "status"))
        if st:
            F((2, "dataStatus", st))

        poc_list = []
        for p_el in data_id.findall(_q(GMD, "pointOfContact")):
            cd = parse_contact(p_el.find(_q(GMD, "CI_ResponsibleParty")))
            if cd:
                poc_list.append(cd)
                if cd.get("organization") or cd.get("individual"):
                    plan["contacts"].append((cd.get("organization") or cd.get("individual"), cd))
        if poc_list:
            LST((2, ID + "pointOfContact", poc_list))

        topics = []
        for tc_el in data_id.findall(_q(GMD, "topicCategory")):
            t_val = (tc_el.findtext(_q(GMD, "MD_TopicCategoryCode")) or tc_el.text or "").strip()
            if t_val:
                topics.append({"topicCategory": t_val})
        if topics:
            LST((2, ID + "topicCategory", topics))

        kw_groups = []
        for dk_el in data_id.findall(_q(GMD, "descriptiveKeywords")):
            md_kws = dk_el.find(_q(GMD, "MD_Keywords"))
            if md_kws is not None:
                t_val = get_code(md_kws, _q(GMD, "type")) or "theme"
                words = []
                for kw_el in md_kws.findall(_q(GMD, "keyword")):
                    w = get_text(kw_el, ".")
                    if w:
                        words.append({"value": w})
                if words:
                    kw_groups.append({"type": t_val, "__lists__": {"keyword": words}})
        if kw_groups:
            LST((2, ID + "descriptiveKeywords", kw_groups))

        formats = []
        for rf_el in data_id.findall(_q(GMD, "resourceFormat")):
            mdf = rf_el.find(_q(GMD, "MD_Format"))
            if mdf is not None:
                fn = get_text(mdf, _q(GMD, "name"))
                fv = get_text(mdf, _q(GMD, "version"))
                if fn:
                    formats.append({"formatTitle": fn, "formatAlternateTitle": fn, "formatEdition": fv})
        if formats:
            LST((2, ID + "resourceFormat", formats))

        usages = []
        for us_el in data_id.findall(_q(GMD, "resourceSpecificUsage")):
            mdu = us_el.find(_q(GMD, "MD_Usage"))
            if mdu is not None:
                su = get_text(mdu, _q(GMD, "specificUsage"))
                uc = mdu.find(f"{_q(GMD, 'userContactInfo')}/{_q(GMD, 'CI_ResponsibleParty')}")
                cd = parse_contact(uc) if uc is not None else {}
                usages.append({
                    "specificUsage": su,
                    "userRole": cd.get("role", "user"),
                    "userOrganization": cd.get("organization", ""),
                    "userIndividual": cd.get("individual", ""),
                })
        if usages:
            LST((2, ID + "resourceSpecificUsage", usages))

        # Extent
        ext = data_id.find(f"{_q(GMD, 'extent')}/{_q(GMD, 'EX_Extent')}")
        if ext is not None:
            ed = get_text(ext, _q(GMD, "description"))
            if ed:
                F((2, "extentDescription", ed))
            bbox = ext.find(f"{_q(GMD, 'geographicElement')}/{_q(GMD, 'EX_GeographicBoundingBox')}")
            if bbox is not None:
                w = get_text(bbox, _q(GMD, "westBoundLongitude"))
                e = get_text(bbox, _q(GMD, "eastBoundLongitude"))
                s = get_text(bbox, _q(GMD, "southBoundLatitude"))
                n = get_text(bbox, _q(GMD, "northBoundLatitude"))
                if w:
                    F((2, "westBound", w))
                if e:
                    F((2, "eastBound", e))
                if s:
                    F((2, "southBound", s))
                if n:
                    F((2, "northBound", n))
            tp = ext.find(f"{_q(GMD, 'temporalElement')}/{_q(GMD, 'EX_TemporalExtent')}/{_q(GMD, 'extent')}/{_q(GML, 'TimePeriod')}")
            if tp is not None:
                tb = get_text(tp, _q(GML, "beginPosition"))
                te = get_text(tp, _q(GML, "endPosition"))
                if tb:
                    F((2, "timeBegin", tb))
                if te:
                    F((2, "timeEnd", te))

    # --- TAHAP 3: REPRESENTASI SPASIAL ---
    if data_id is not None:
        srt = get_code(data_id, _q(GMD, "spatialRepresentationType"))
        if srt:
            F((3, "spatialRepresentationType", srt))
        for sr in data_id.findall(_q(GMD, "spatialResolution")):
            den = get_text(sr, f"{_q(GMD, 'MD_Resolution')}/{_q(GMD, 'equivalentScale')}/{_q(GMD, 'MD_RepresentativeFraction')}/{_q(GMD, 'denominator')}") or get_text(sr, f".//{_q(GMD, 'denominator')}")
            dist = get_text(sr, f"{_q(GMD, 'MD_Resolution')}/{_q(GMD, 'distance')}") or get_text(sr, f".//{_q(GMD, 'distance')}")
            if den:
                F((3, "spatialResolution", den))
            if dist:
                F((3, "spatialResolutionM", dist))

    vec = gmd_root.find(f"{_q(GMD, 'spatialRepresentationInfo')}/{_q(GMD, 'MD_VectorSpatialRepresentation')}")
    if vec is not None:
        OPT((3, "vector"))
        tl = get_code(vec, _q(GMD, "topologyLevel"))
        if tl:
            F((3, "topologyLevel", tl))
        gobj = vec.find(f"{_q(GMD, 'geometricObjects')}/{_q(GMD, 'MD_GeometricObjects')}")
        if gobj is not None:
            got = get_code(gobj, _q(GMD, "geometricObjectType"))
            if got:
                F((3, "geometricObjectType", got))
            goc = get_text(gobj, _q(GMD, "geometricObjectCount"))
            if goc:
                F((3, "geometricObjectCount", goc))

    # --- TAHAP 4: SISTEM REFERENSI KOORDINAT ---
    rs_id = gmd_root.find(f"{_q(GMD, 'referenceSystemInfo')}/{_q(GMD, 'MD_ReferenceSystem')}/{_q(GMD, 'referenceSystemIdentifier')}")
    if rs_id is not None:
        r_el = rs_id.find(_q(GMD, "RS_Identifier")) or rs_id.find(_q(GMD, "MD_Identifier"))
        if r_el is not None:
            code = get_text(r_el, _q(GMD, "code"))
            cs = get_text(r_el, _q(GMD, "codeSpace"))
            title = get_text(r_el, f"{_q(GMD, 'authority')}/{_q(GMD, 'CI_Citation')}/{_q(GMD, 'title')}")
            atitle = get_text(r_el, f"{_q(GMD, 'authority')}/{_q(GMD, 'CI_Citation')}/{_q(GMD, 'alternateTitle')}")
            if code:
                F((4, "referenceSystemCode", code))
            if cs:
                F((4, "referenceSystemCodeSpace", cs))
            if title:
                F((4, "referenceSystemTitle", title))
            if atitle:
                F((4, "referenceSystemAlternateTitle", atitle))
            F((4, "referenceSystemType", "geodeticGeographic2D" if code == "4326" else "projected"))

    # --- TAHAP 5: INFORMASI KONTEN ---
    fc = gmd_root.find(f"{_q(GMD, 'contentInfo')}/{_q(GMD, 'MD_FeatureCatalogueDescription')}")
    if fc is not None:
        OPT((5, "featurecat"))
        comp = get_text(fc, _q(GMD, "complianceCode"))
        if comp:
            F((5, "featureCatalogueCompliance", comp))
        inc = get_text(fc, _q(GMD, "includedWithDataset"))
        if inc:
            F((5, "featureCatalogueIncluded", inc))
        ft_list = []
        for ft_el in fc.findall(_q(GMD, "featureTypes")):
            ft_name = get_text(ft_el, ".")
            if ft_name:
                ft_list.append({"name": ft_name})
        if ft_list:
            LST((5, "featureTypes", ft_list))
        fc_cit = fc.find(f"{_q(GMD, 'featureCatalogueCitation')}/{_q(GMD, 'CI_Citation')}")
        if fc_cit is not None:
            ct = get_text(fc_cit, _q(GMD, "title"))
            if ct:
                F((5, "catalogueTitle", ct))
            cat = get_text(fc_cit, _q(GMD, "alternateTitle"))
            if cat:
                F((5, "catalogueAlternateTitle", cat))
            ced = get_text(fc_cit, _q(GMD, "edition"))
            if ced:
                F((5, "catalogueEdition", ced))
            curl = get_text(fc_cit, f"{_q(GMD, 'onlineResource')}/{_q(GMD, 'CI_OnlineResource')}/{_q(GMD, 'linkage')}")
            if curl:
                F((5, "catalogueURL", curl))

    # --- TAHAP 6: DISTRIBUSI & AKSES DATA ---
    dist = gmd_root.find(f"{_q(GMD, 'distributionInfo')}/{_q(GMD, 'MD_Distribution')}")
    if dist is not None:
        df_list = []
        for df_el in dist.findall(_q(GMD, "distributionFormat")):
            mdf = df_el.find(_q(GMD, "MD_Format"))
            if mdf is not None:
                fn = get_text(mdf, _q(GMD, "name"))
                fv = get_text(mdf, _q(GMD, "version"))
                if fn:
                    df_list.append({"title": fn, "alternateTitle": fn, "edition": fv})
        if df_list:
            LST((6, "distributionInfo/distributionFormat", df_list))

        dc_list = []
        for dist_el in dist.findall(_q(GMD, "distributor")):
            md_dist = dist_el.find(_q(GMD, "MD_Distributor"))
            if md_dist is not None:
                for c_el in md_dist.findall(_q(GMD, "distributorContact")):
                    cd = parse_contact(c_el.find(_q(GMD, "CI_ResponsibleParty")))
                    if cd:
                        dc_list.append(cd)
        if dc_list:
            LST((6, "distributionInfo/distributor/distributorContact", dc_list))

        to = dist.find(f"{_q(GMD, 'transferOptions')}/{_q(GMD, 'MD_DigitalTransferOptions')}")
        if to is not None:
            u = get_text(to, _q(GMD, "unitsOfDistribution"))
            if u:
                F((6, "distributionUnits", u))
            sz = get_text(to, _q(GMD, "transferSize"))
            if sz:
                F((6, "transferSize", sz))
            ol_list = []
            for ol_el in to.findall(_q(GMD, "onLine")):
                od = parse_online(ol_el)
                if od.get("url"):
                    ol_list.append(od)
            if ol_list:
                LST((6, "distributionInfo/transferOptions/onLine", ol_list))

    # --- TAHAP 7 & 8: KUALITAS DATA & LINEAGE ---
    for dq in gmd_root.findall(f"{_q(GMD, 'dataQualityInfo')}/{_q(GMD, 'DQ_DataQuality')}"):
        lin = dq.find(f"{_q(GMD, 'lineage')}/{_q(GMD, 'LI_Lineage')}")
        if lin is not None:
            stmt = get_text(lin, _q(GMD, "statement"))
            if stmt:
                F((8, "lineageStatement", stmt))
            lsc = get_code(lin, f"{_q(GMD, 'scope')}/{_q(GMD, 'level')}")
            if lsc:
                F((8, "lineageScopeLevel", lsc))

            steps = []
            for ps in lin.findall(f"{_q(GMD, 'processStep')}/{_q(GMD, 'LI_ProcessStep')}"):
                desc = get_text(ps, _q(GMD, "description"))
                rat = get_text(ps, _q(GMD, "rationale"))
                dt = get_text(ps, _q(GMD, "dateTime")) or get_text(ps, _q(GMD, "stepDateTime"))
                psc = get_code(ps, f"{_q(GMD, 'scope')}/{_q(GMD, 'level')}")
                proc_rp = ps.find(f"{_q(GMD, 'processor')}/{_q(GMD, 'CI_ResponsibleParty')}")
                pcd = parse_contact(proc_rp)
                ref_t = get_text(ps, f"{_q(GMD, 'source')}/{_q(GMD, 'CI_Citation')}/{_q(GMD, 'title')}")
                steps.append({
                    "description": desc,
                    "rationale": rat,
                    "stepDateTime": dt,
                    "processorName": pcd.get("organization") or pcd.get("individual", ""),
                    "processorRole": pcd.get("role", "processor"),
                    "referenceTitle": ref_t,
                    "scopeLevel": psc or "dataset",
                })
            if steps:
                LST((8, "resourceLineage/processStep", steps))

            sources = []
            for src in lin.findall(f"{_q(GMD, 'source')}/{_q(GMD, 'LI_Source')}"):
                sd = get_text(src, _q(GMD, "description"))
                sres = get_text(src, f"{_q(GMD, 'sourceSpatialResolution')}/{_q(GMD, 'MD_Resolution')}/{_q(GMD, 'distance')}") or get_text(src, f"{_q(GMD, 'sourceSpatialResolution')}/{_q(GMD, 'distance')}")
                sref_c = get_text(src, f"{_q(GMD, 'sourceReferenceSystem')}/{_q(GMD, 'MD_ReferenceSystem')}/{_q(GMD, 'referenceSystemIdentifier')}/{_q(GMD, 'MD_Identifier')}/{_q(GMD, 'code')}") or get_text(src, f".//{_q(GMD, 'sourceReferenceSystem')}//{_q(GMD, 'code')}")
                sref_cs = get_text(src, f"{_q(GMD, 'sourceReferenceSystem')}/{_q(GMD, 'MD_ReferenceSystem')}/{_q(GMD, 'referenceSystemIdentifier')}/{_q(GMD, 'MD_Identifier')}/{_q(GMD, 'codeSpace')}") or get_text(src, f".//{_q(GMD, 'sourceReferenceSystem')}//{_q(GMD, 'codeSpace')}")
                scit = get_text(src, f"{_q(GMD, 'sourceCitation')}/{_q(GMD, 'CI_Citation')}/{_q(GMD, 'title')}")
                scit_d = get_text(src, f"{_q(GMD, 'sourceCitation')}/{_q(GMD, 'CI_Citation')}/{_q(GMD, 'date')}/{_q(GMD, 'CI_Date')}/{_q(GMD, 'date')}")
                scit_dt = get_code(src, f"{_q(GMD, 'sourceCitation')}/{_q(GMD, 'CI_Citation')}/{_q(GMD, 'date')}/{_q(GMD, 'CI_Date')}/{_q(GMD, 'dateType')}")
                smeta = get_text(src, f"{_q(GMD, 'sourceMetadata')}/{_q(GMD, 'CI_Citation')}/{_q(GMD, 'title')}")
                ssc = get_code(src, f"{_q(GMD, 'scope')}/{_q(GMD, 'level')}")
                sources.append({
                    "description": sd,
                    "spatialResolution": sres,
                    "referenceSystemCode": sref_c,
                    "referenceSystemCodeSpace": sref_cs,
                    "citationTitle": scit,
                    "citationDate": scit_d,
                    "citationDateType": scit_dt or "creation",
                    "metadataTitle": smeta,
                    "scopeLevel": ssc or "dataset",
                })
            if sources:
                LST((8, "resourceLineage/source", sources))
        else:
            # Data Quality Report (Tahap 7)
            qsc = get_code(dq, f"{_q(GMD, 'scope')}/{_q(GMD, 'DQ_Scope')}/{_q(GMD, 'level')}") or get_code(dq, f".//{_q(GMD, 'level')}")
            if qsc:
                F((7, "qualityScope", qsc))
            reports = []
            for rep_wrap in dq.findall(_q(GMD, "report")):
                for rep in rep_wrap:
                    meas = get_text(rep, f".//{_q(GMD, 'nameOfMeasure')}") or get_text(rep, _q(GMD, "measureDescription"))
                    desc = get_text(rep, f".//{_q(GMD, 'measureDescription')}/{_q(GMD, 'measureDescription')}") or meas
                    eval_desc = ""
                    for emd in rep.findall(f".//{_q(GMD, 'evaluationMethodDescription')}"):
                        cs = emd.find(f"{{{GCO}}}CharacterString")
                        if cs is not None and cs.text and cs.text.strip():
                            eval_desc = cs.text.strip()
                            break
                    eval_type = get_code(rep, f".//{_q(GMD, 'evaluationMethodType')}")
                    res_list = []
                    for res_wrap in rep.findall(_q(GMD, "result")):
                        for res in res_wrap:
                            r_dt = get_text(res, f".//{_q(GMD, 'dateTime')}")
                            r_sc = get_code(res, f".//{_q(GMD, 'resultScope')}/{_q(GMD, 'DQ_Scope')}/{_q(GMD, 'level')}")
                            spec_t = get_text(res, f".//{_q(GMD, 'specification')}/{_q(GMD, 'CI_Citation')}/{_q(GMD, 'title')}")
                            spec_at = get_text(res, f".//{_q(GMD, 'specification')}/{_q(GMD, 'CI_Citation')}/{_q(GMD, 'alternateTitle')}")
                            exp = get_text(res, f".//{_q(GMD, 'explanation')}")
                            pass_v = get_text(res, f".//{_q(GMD, 'pass')}")
                            res_item = {
                                "dateTime": r_dt,
                                "resultScope": r_sc,
                                "specificationTitle": spec_t,
                                "specificationAlternate": spec_at,
                                "explanation": exp,
                                "pass": pass_v
                            }
                            res_list.append({k: v for k, v in res_item.items() if v})
                    rep_item = {
                        "measure": meas,
                        "description": desc,
                        "evaluationMethodDescription": eval_desc,
                        "evaluationMethodType": eval_type
                    }
                    if res_list:
                        rep_item["__lists__"] = {"result": res_list}
                    reports.append({k: v for k, v in rep_item.items() if v})
            if reports:
                LST((7, "dataQualityInfo/report", reports))

    # --- TAHAP 9: KATALOG PENYAJIAN ---
    pc = gmd_root.find(_q(GMD, "portrayalCatalogueInfo"))
    if pc is not None:
        cit = pc.find(f"{_q(GMD, 'MD_PortrayalCatalogueReference')}/{_q(GMD, 'portrayalCatalogueCitation')}/{_q(GMD, 'CI_Citation')}")
        if cit is not None:
            pct = get_text(cit, _q(GMD, "title"))
            pcat = get_text(cit, _q(GMD, "alternateTitle"))
            pcurl = get_text(cit, f"{_q(GMD, 'onlineResource')}/{_q(GMD, 'CI_OnlineResource')}/{_q(GMD, 'linkage')}")
            if pct:
                F((9, "portrayalCatalogueTitle", pct))
            if pcat:
                F((9, "portrayalCatalogueAlternateTitle", pcat))
            if pcurl:
                F((9, "portrayalCatalogueURL", pcurl))
            pc_contacts = []
            for crp in cit.findall(_q(GMD, "citedResponsibleParty")):
                cd = parse_contact(crp.find(_q(GMD, "CI_ResponsibleParty")))
                if cd:
                    pc_contacts.append(cd)
            if pc_contacts:
                LST((9, "portrayalCatalogueInfo/portrayalCatalogueCitation/citedResponsibleParty", pc_contacts))

    # --- TAHAP 10: BATASAN & KEAMANAN ---
    if data_id is not None:
        for rc in data_id.findall(_q(GMD, "resourceConstraints")):
            mc = rc.find(_q(GMD, "MD_Constraints"))
            if mc is not None:
                ul = get_text(mc, _q(GMD, "useLimitation"))
                if ul:
                    F((10, "useLimitation", ul))
            lc = rc.find(_q(GMD, "MD_LegalConstraints"))
            if lc is not None:
                ac = get_code(lc, _q(GMD, "accessConstraints"))
                uc = get_code(lc, _q(GMD, "useConstraints"))
                oc = get_text(lc, _q(GMD, "otherConstraints"))
                if ac:
                    F((10, "accessConstraints", ac))
                if uc:
                    F((10, "useConstraints", uc))
                if oc:
                    F((10, "otherConstraints", oc))
            sc = rc.find(_q(GMD, "MD_SecurityConstraints"))
            if sc is not None:
                cl = get_code(sc, _q(GMD, "classification"))
                un = get_text(sc, _q(GMD, "userNote"))
                csys = get_text(sc, _q(GMD, "classificationSystem"))
                hd = get_text(sc, _q(GMD, "handlingDescription"))
                if cl:
                    F((10, "securityClassification", cl))
                if un:
                    F((10, "securityUserNote", un))
                if csys:
                    F((10, "securitySystem", csys))
                if hd:
                    F((10, "handlingDescription", hd))

    for mc in gmd_root.findall(_q(GMD, "metadataConstraints")):
        c = mc.find(_q(GMD, "MD_Constraints"))
        if c is not None:
            ul = get_text(c, _q(GMD, "useLimitation"))
            if ul:
                F((10, "metadataUseLimitation", ul))
        lc = mc.find(_q(GMD, "MD_LegalConstraints"))
        if lc is not None:
            oc = get_text(lc, _q(GMD, "otherConstraints"))
            if oc:
                F((10, "metadataOtherConstraints", oc))
        sc = mc.find(_q(GMD, "MD_SecurityConstraints"))
        if sc is not None:
            cl = get_code(sc, _q(GMD, "classification"))
            un = get_text(sc, _q(GMD, "userNote"))
            csys = get_text(sc, _q(GMD, "classificationSystem"))
            if cl:
                F((10, "metadataSecurityClassification", cl))
            if un:
                F((10, "metadataSecurityUserNote", un))
            if csys:
                F((10, "metadataSecuritySystem", csys))

    # --- TAHAP 11: SKEMA APLIKASI ---
    app_schema = gmd_root.find(f"{_q(GMD, 'applicationSchemaInfo')}/{_q(GMD, 'MD_ApplicationSchemaInformation')}")
    if app_schema is not None:
        sn = get_text(app_schema, f"{_q(GMD, 'name')}/{_q(GMD, 'CI_Citation')}/{_q(GMD, 'title')}")
        sat = get_text(app_schema, f"{_q(GMD, 'name')}/{_q(GMD, 'CI_Citation')}/{_q(GMD, 'alternateTitle')}")
        sl = get_text(app_schema, _q(GMD, "schemaLanguage"))
        scl = get_text(app_schema, _q(GMD, "constraintLanguage"))
        sa = get_text(app_schema, _q(GMD, "schemaAscii"))
        gf = app_schema.find(_q(GMD, "graphicsFile"))
        if sn:
            F((11, "schemaName", sn))
        if sat:
            F((11, "schemaAlternateTitle", sat))
        if sl:
            F((11, "schemaLanguage", sl))
        if scl:
            F((11, "schemaConstraintLanguage", scl))
        if sa:
            F((11, "schemaAscii", sa))
        if gf is not None:
            g_url = get_text(gf, f"{_q(GMD, 'CI_OnlineResource')}/{_q(GMD, 'linkage')}")
            g_nm = get_text(gf, f"{_q(GMD, 'CI_OnlineResource')}/{_q(GMD, 'name')}")
            if g_url:
                F((11, "schemaGraphicsURL", g_url))
            if g_nm:
                F((11, "schemaGraphicsName", g_nm))

    # --- TAHAP 12: PEMELIHARAAN ---
    if data_id is not None:
        maint_list = []
        for rm in data_id.findall(f"{_q(GMD, 'resourceMaintenance')}/{_q(GMD, 'MD_MaintenanceInformation')}"):
            freq = get_code(rm, _q(GMD, "maintenanceAndUpdateFrequency"))
            ud_date = get_text(rm, f"{_q(GMD, 'userDefinedMaintenanceFrequency')}/{_q(GTS, 'TM_PeriodDuration')}/{_q(GMD, 'CI_Date')}/{_q(GMD, 'date')}")
            sc_val = get_code(rm, _q(GMD, "updateScope"))
            note = get_text(rm, _q(GMD, "maintenanceNote"))
            c_rp = rm.find(f"{_q(GMD, 'contact')}/{_q(GMD, 'CI_ResponsibleParty')}")
            c_list = [parse_contact(c_rp)] if c_rp is not None else []
            m_item = {
                "maintenanceFrequency": freq,
                "maintenanceDate": ud_date,
                "maintenanceScopeLevel": sc_val,
                "maintenanceNote": note,
            }
            if c_list and any(c_list[0].values()):
                m_item["__lists__"] = {"contact": c_list}
            maint_list.append(m_item)
        if maint_list:
            LST((12, ID + "resourceMaintenance", maint_list))

    mm = gmd_root.find(f"{_q(GMD, 'metadataMaintenance')}/{_q(GMD, 'MD_MaintenanceInformation')}")
    if mm is not None:
        mf = get_code(mm, _q(GMD, "maintenanceAndUpdateFrequency"))
        md = get_text(mm, f"{_q(GMD, 'userDefinedMaintenanceFrequency')}/{_q(GTS, 'TM_PeriodDuration')}/{_q(GMD, 'CI_Date')}/{_q(GMD, 'date')}")
        msc = get_code(mm, _q(GMD, "updateScope"))
        mn = get_text(mm, _q(GMD, "maintenanceNote"))
        if mf:
            F((12, "metadataMaintenanceFrequency", mf))
        if md:
            F((12, "metadataMaintenanceDate", md))
        if msc:
            F((12, "metadataMaintenanceScopeLevel", msc))
        if mn:
            F((12, "metadataMaintenanceNote", mn))
        mc_rp = mm.find(f"{_q(GMD, 'contact')}/{_q(GMD, 'CI_ResponsibleParty')}")
        if mc_rp is not None:
            mcd = parse_contact(mc_rp)
            if mcd:
                LST((12, "metadataMaintenance/contact", [mcd]))

    # --- TAHAP 13: EKSTENSI METADATA ---
    ext_info = gmd_root.find(f"{_q(GMD, 'metadataExtensionInfo')}/{_q(GMD, 'MD_MetadataExtensionInformation')}")
    if ext_info is not None:
        e_ol = ext_info.find(_q(GMD, "extensionOnLineResource"))
        if e_ol is not None:
            eod = parse_online(e_ol)
            if eod.get("url"):
                F((13, "extensionOnlineURL", eod["url"]))
            if eod.get("protocol"):
                F((13, "extensionOnlineProtocol", eod["protocol"]))
            app_prof = get_text(e_ol, f".//{_q(GMD, 'applicationProfile')}")
            if app_prof:
                F((13, "extensionOnlineApplicationProfile", app_prof))
            if eod.get("name"):
                F((13, "extensionOnlineName", eod["name"]))
            if eod.get("description"):
                F((13, "extensionOnlineDescription", eod["description"]))
            if eod.get("function"):
                F((13, "extensionOnlineFunction", eod["function"]))
        el_inf = ext_info.find(_q(GMD, "extendedElementInformation"))
        if el_inf is not None:
            for k, tag in (
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
            ):
                v = get_code(el_inf, f".//{_q(GMD, tag)}") or get_text(el_inf, f".//{_q(GMD, tag)}") or get_text(el_inf, _q(GMD, tag))
                if v:
                    F((13, k, v))

    return plan


def convert_gmd_to_iso3(gmd_root_or_path, template_path):
    """Mengonversi dokumen gmd:MD_Metadata ke mdb:MD_Metadata (ISO 19115-3)

    berbasis template.xml sehingga dapat langsung dimuat ke EditorDialog GeoMDB.
    """
    if isinstance(gmd_root_or_path, str):
        gmd_root = ET.parse(gmd_root_or_path).getroot()
    else:
        gmd_root = gmd_root_or_path

    iso3_root, _ = model.load(template_path)
    plan = extract_gmd_plan(gmd_root)

    # Terapkan plan ke struktur iso3_root
    def _find_node(nodes, pred):
        for n in nodes:
            if pred(n):
                return n
            if isinstance(n, layout.BOptional) and n.present:
                r = _find_node(n.nodes, pred)
                if r is not None:
                    return r
        return None

    def _find_list(nodes, path):
        return _find_node(nodes, lambda n: isinstance(n, layout.BList) and getattr(n, "path", None) == path)

    def _find_field(nodes, key):
        return _find_node(nodes, lambda n: isinstance(n, layout.BField) and n.key == key and n.field is not None)

    def _stages():
        return {s.id: s for s in layout.build(iso3_root)[0]}

    def _ensure_count(bl, n):
        prop = bl.path.split("/")[-1]
        count = len(bl.instances)
        while count < n and bl.options and model.can_add(bl.container, prop, count):
            src = bl.options[0][1]
            if isinstance(src, tuple):
                model.add_snippet(iso3_root, bl.container, src[1])
            else:
                model.add_block(iso3_root, bl.container, src)
            count += 1

    # 1) Aktifkan blok opsional
    for sid, snip in plan["optionals"]:
        st = _stages().get(sid)
        bo = st and _find_node(st.nodes, lambda n: isinstance(n, layout.BOptional) and n.snippet == snip)
        if bo is not None and not bo.present:
            model.add_snippet(iso3_root, bo.container, bo.snippet)

    # 2) Tambah entri daftar tingkat atas
    for sid, path, insts in plan["lists"]:
        st = _stages().get(sid)
        bl = st and _find_list(st.nodes, path)
        if bl is not None:
            _ensure_count(bl, len(insts))

    # 3) Tambah entri daftar bersarang
    for sid, path, insts in plan["lists"]:
        st = _stages().get(sid)
        bl = st and _find_list(st.nodes, path)
        if bl is None:
            continue
        for ip, inst in zip(insts, bl.instances):
            for npath, sub in ip.get("__lists__", {}).items():
                nbl = _find_list(inst.nodes, npath)
                if nbl is not None:
                    _ensure_count(nbl, len(sub))

    # 4) Tulis nilai ke field
    secs = _stages()

    def put(bf, val):
        txt = str(val).strip() if val is not None else ""
        if txt:
            bf.field.set(txt)

    for sid, key, val in plan["fields"]:
        st = secs.get(sid)
        bf = st and _find_field(st.nodes, key)
        if bf is not None:
            put(bf, val)

    for sid, path, insts in plan["lists"]:
        st = secs.get(sid)
        bl = st and _find_list(st.nodes, path)
        if bl is None:
            continue
        for ip, inst in zip(insts, bl.instances):
            for key, val in ip.items():
                if key == "__lists__":
                    continue
                bf = _find_field(inst.nodes, key)
                if bf is not None:
                    put(bf, val)
            for npath, sub in ip.get("__lists__", {}).items():
                nbl = _find_list(inst.nodes, npath)
                if nbl is None:
                    continue
                for sp_, sinst in zip(sub, nbl.instances):
                    for key, val in sp_.items():
                        bf = _find_field(sinst.nodes, key)
                        if bf is not None:
                            put(bf, val)

    return iso3_root
