"""Ekstraksi properti layer vektor QGIS menjadi rencana pengisian form GeoMDB.

Modul ini tidak menyentuh widget: hanya membaca layer dan menghasilkan `plan`
yang kemudian diterapkan oleh EditorDialog ke pohon XML.

Struktur plan:
    fields    : [(sid, key, value)]                 field tunggal (boleh di dalam blok opsional)
    optionals : [(sid, snippet)]                    blok opsional yang harus diaktifkan
    lists     : [(sid, path, [inst, ...])]          daftar berulang; inst = {key: value,
                                                    "__lists__": {path: [inst, ...]}}
    contacts  : [(nama_profil, data_kontak)]        disimpan ke Kontak Tersimpan
    notes     : [str]                               catatan informasi
Nilai tanggal boleh berupa datetime.date / datetime.datetime; diformat saat diterapkan.
"""
import datetime
import os
import re

from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject, QgsWkbTypes

from . import layout

ID = layout.ID

TOPICS = [o["value"] for o in layout.OPTS.get("topicCategoryOptions", [])]
ROLES = [o["value"] for o in layout.OPTS.get("roleOptions", [])]
KW_TYPES = [o["value"] for o in layout.OPTS.get("keywordTypeOptions", []) if o["value"]]

LANG = {"ind": "ind", "id": "ind", "indonesia": "ind", "indonesian": "ind", "bahasaindonesia": "ind",
        "eng": "eng", "en": "eng", "english": "eng", "inggris": "eng",
        "msa": "msa", "ms": "msa", "malay": "msa", "melayu": "msa"}
ENC = {"utf8": "utf8", "utf16": "utf16", "utf32": "utf32", "iso88591": "iso8859-1", "latin1": "iso8859-1"}

FORMATS = {  # storageType provider -> (nama singkat, nama lengkap)
    "esri shapefile": ("SHP", "ESRI Shapefile"),
    "gpkg": ("GPKG", "OGC GeoPackage"),
    "geojson": ("GeoJSON", "GeoJSON"),
    "kml": ("KML", "Keyhole Markup Language"),
    "libkml": ("KML", "Keyhole Markup Language"),
    "csv": ("CSV", "Comma Separated Values"),
    "gml": ("GML", "Geography Markup Language"),
    "filegdb": ("GDB", "ESRI File Geodatabase"),
    "openfilegdb": ("GDB", "ESRI File Geodatabase"),
    "sqlite": ("SQLite", "SQLite / SpatiaLite"),
    "mapinfo file": ("TAB", "MapInfo File"),
    "dxf": ("DXF", "AutoCAD DXF"),
    "postgresql database with postgis extension": ("PostGIS", "PostgreSQL / PostGIS"),
}
SHP_SIDECARS = (".shp", ".shx", ".dbf", ".prj", ".cpg", ".qix", ".sbn", ".sbx", ".shp.xml", ".qmd")


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _match(value, options):
    n = _norm(value)
    for o in options:
        if _norm(o) == n:
            return o
    return None


def _enum_int(v):
    try:
        return int(v)
    except TypeError:
        return getattr(v, "value", None)


def _qdt(qdt):
    """QDateTime/QDate -> datetime (None bila tidak valid)."""
    if qdt is None or not qdt.isValid():
        return None
    if hasattr(qdt, "date") and hasattr(qdt, "time"):
        d, t = qdt.date(), qdt.time()
        return datetime.datetime(d.year(), d.month(), d.day(), t.hour(), t.minute(), t.second())
    return datetime.date(qdt.year(), qdt.month(), qdt.day())


def _source_path(layer):
    uri = layer.dataProvider().dataSourceUri() if layer.dataProvider() else layer.source()
    path = uri.split("|")[0].strip()
    return path if os.path.isfile(path) else None


def _size_mb(path):
    if not path:
        return None
    total = 0
    if path.lower().endswith(".shp"):
        stem = path[:-4]
        for ext in SHP_SIDECARS:
            for cand in (stem + ext, stem + ext.upper()):
                if os.path.isfile(cand):
                    total += os.path.getsize(cand)
                    break
    else:
        total = os.path.getsize(path)
    return total / (1024.0 * 1024.0)


def extract_vector(layer):
    plan = {"fields": [], "optionals": [], "lists": [], "contacts": [], "notes": []}
    F, OPT, LST = plan["fields"].append, plan["optionals"].append, plan["lists"].append
    md = layer.metadata()
    prov = layer.dataProvider()

    # ---------------- Tahap 1: Informasi Metadata ----------------
    if md.identifier().strip():
        F((1, "metadataIdentifier", md.identifier().strip()))
    if md.parentIdentifier().strip():
        F((1, "parentMetadata", md.parentIdentifier().strip()))
    lang = LANG.get(_norm(md.language()))
    if lang:
        F((1, "language", lang))
    enc = ENC.get(_norm(md.encoding())) or ENC.get(_norm(prov.encoding() if prov else ""))
    if enc:
        F((1, "characterEncoding", enc))
    F((1, "metadataScope", "dataset"))
    LST((1, "dateInfo", [{"date": datetime.datetime.now().replace(microsecond=0), "type": "creation"}]))

    # ---------------- Tahap 2: Identifikasi ----------------
    title = md.title().strip() or layer.name()
    F((2, "dataTitle", title))
    abstract = md.abstract().strip()
    if not abstract:
        try:
            abstract = layer.serverProperties().abstract().strip()
        except Exception:
            abstract = ""
    if abstract:
        F((2, "dataAbstract", abstract))

    try:
        from qgis.core import Qgis
        DT = Qgis.MetadataDateType
        for key, dtype in (("dataCreationDate", DT.Created), ("dataPublicationDate", DT.Published),
                           ("dataRevisionDate", DT.Revised)):
            v = _qdt(md.dateTime(dtype))
            if v:
                F((2, key, v.date() if isinstance(v, datetime.datetime) else v))
    except Exception:
        pass

    ext = layer.extent()
    if not ext.isNull() and not ext.isEmpty():
        if layer.crs().isValid() and layer.crs().authid() != "EPSG:4326":
            tr = QgsCoordinateTransform(layer.crs(), QgsCoordinateReferenceSystem("EPSG:4326"), QgsProject.instance())
            ext = tr.transformBoundingBox(ext)
        for key, v in (("westBound", ext.xMinimum()), ("eastBound", ext.xMaximum()),
                       ("southBound", ext.yMinimum()), ("northBound", ext.yMaximum())):
            F((2, key, "%.6f" % v))

    begin = end = None
    try:
        rngs = md.extent().temporalExtents()
        if rngs:
            begin, end = _qdt(rngs[0].begin()), _qdt(rngs[0].end())
    except Exception:
        pass
    if not (begin or end):
        try:
            tp = layer.temporalProperties()
            if tp.isActive() and hasattr(tp, "fixedTemporalRange"):
                r = tp.fixedTemporalRange()
                begin, end = _qdt(r.begin()), _qdt(r.end())
        except Exception:
            pass
    if begin:
        F((2, "timeBegin", begin.date() if isinstance(begin, datetime.datetime) else begin))
    if end:
        F((2, "timeEnd", end.date() if isinstance(end, datetime.datetime) else end))

    topics = []
    for c in md.categories():
        t = _match(c, TOPICS)
        if t and t not in topics:
            topics.append(t)
    if topics:
        LST((2, ID + "topicCategory", [{"topicCategory": t} for t in topics]))

    groups = []
    for vocab, words in md.keywords().items():
        if _norm(vocab) in ("gmdtopiccategory", "isotopiccategory") or not words:
            continue
        groups.append({"type": _match(vocab, KW_TYPES) or "theme",
                       "__lists__": {"keyword": [{"value": w} for w in words if w.strip()]}})
    if groups:
        LST((2, ID + "descriptiveKeywords", groups))

    fmt = None
    st = (prov.storageType() if prov else "") or ""
    fmt = FORMATS.get(st.lower().strip())
    if fmt is None and st and st.lower() not in ("memory storage",):
        fmt = (st, st)
    if fmt:
        LST((2, ID + "resourceFormat", [{"formatTitle": fmt[0], "formatAlternateTitle": fmt[1]}]))

    contacts = []
    for c in md.contacts():
        data = {"role": _match(c.role, ROLES) or "pointOfContact"}
        for key, v in (("organization", c.organization), ("individual", c.name), ("position", c.position),
                       ("phone", c.voice), ("fax", c.fax), ("email", c.email)):
            if (v or "").strip():
                data[key] = v.strip()
        if c.addresses:
            a = c.addresses[0]
            for key, v in (("address", a.address), ("city", a.city), ("province", a.administrativeArea),
                           ("postalCode", a.postalCode), ("country", a.country)):
                if (v or "").strip():
                    data[key] = v.strip()
        if len(data) > 1:
            contacts.append(data)
            plan["contacts"].append((data.get("organization") or data.get("individual"), data))
    if contacts:
        LST((2, ID + "pointOfContact", contacts))

    # ---------------- Tahap 3: Representasi Spasial ----------------
    F((3, "spatialRepresentationType", "vector"))
    OPT((3, "vector"))
    F((3, "topologyLevel", "geometryOnly"))
    kind = {0: "point", 1: "curve", 2: "surface"}.get(_enum_int(QgsWkbTypes.geometryType(layer.wkbType())))
    if kind:
        F((3, "geometricObjectType", kind))
    n = layer.featureCount()
    if n is not None and n >= 0:
        F((3, "geometricObjectCount", str(int(n))))

    # ---------------- Tahap 4: Sistem Referensi ----------------
    crs = layer.crs() if layer.crs().isValid() else md.crs()
    auth = crs.authid() if crs.isValid() else ""
    if ":" in auth:
        space, code = auth.split(":", 1)
        F((4, "referenceSystemTitle", space))
        F((4, "referenceSystemAlternateTitle",
           "European Petroleum Survey Group" if space.upper() == "EPSG" else crs.description()))
        F((4, "referenceSystemCode", code))
        F((4, "referenceSystemCodeSpace", space))
        F((4, "referenceSystemType", "geodeticGeographic2D" if crs.isGeographic() else "projected"))

    # ---------------- Tahap 5: Katalog Unsur (satu entri per layer) ----------------
    OPT((5, "featurecat"))
    F((5, "featureCatalogueIncluded", "true"))
    LST((5, "featureTypes", [{"name": layer.name()}]))
    flds = layer.fields()
    if flds.count():
        plan["notes"].append("Layer memiliki %d atribut: %s" % (
            flds.count(), ", ".join(f.name() for f in flds)[:300]))

    # ---------------- Tahap 6: Distribusi ----------------
    if fmt:
        LST((6, "distributionInfo/distributionFormat", [{"title": fmt[0], "alternateTitle": fmt[1]}]))
    size = _size_mb(_source_path(layer))
    if size is not None:
        F((6, "transferSize", ("%.3f" % size).rstrip("0").rstrip(".") or "0"))
    links = []
    for lk in md.links():
        if not (lk.url or "").strip():
            continue
        inst = {"url": lk.url.strip()}
        for key, v in (("protocol", lk.type), ("name", lk.name), ("description", lk.description)):
            if (v or "").strip():
                inst[key] = v.strip()
        if "download" in (lk.type or "").lower():
            inst["function"] = "download"
        links.append(inst)
    if links:
        LST((6, "distributionInfo/transferOptions/onLine", links))

    # ---------------- Tahap 8: Riwayat ----------------
    hist = [h.strip() for h in md.history() if h.strip()]
    if hist:
        F((8, "lineageStatement", "\n".join(hist)))

    # ---------------- Tahap 10: Batasan ----------------
    if md.fees().strip():
        F((10, "useLimitation", md.fees().strip()))
    other = [c.constraint.strip() for c in md.constraints() if (c.constraint or "").strip()]
    other += [x.strip() for x in list(md.licenses()) + list(md.rights()) if x.strip()]
    if other:
        F((10, "otherConstraints", "\n".join(other)))

    return plan
