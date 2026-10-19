"""Logika murni (tanpa Qt): muat XML, bentuk daftar field/blok editable, tambah/hapus blok, simpan."""
import copy
import io
import json
import os
import re
import xml.etree.ElementTree as ET  # nosec B405
from collections import Counter

NS_GCO = "http://standards.iso.org/iso/19115/-3/gco/1.0"

# properti yang boleh berulang per kelas (diturunkan dari XSD ISO 19115-3)
with open(os.path.join(os.path.dirname(__file__), "repeatable.json"), encoding="utf-8") as _fh:
    REPEATABLE = {k: set(v) for k, v in json.load(_fh).items()}

def _load_json(name):
    with open(os.path.join(os.path.dirname(__file__), name), encoding="utf-8") as fh:
        return json.load(fh)


ORDER = _load_json("order.json")          # kelas -> urutan properti menurut XSD
MAXOCC = _load_json("maxocc.json")        # kelas -> {properti: maks kemunculan} (yang terbatas)
NS_GML = "http://www.opengis.net/gml/3.2"

VALUE_TYPES = {"CharacterString", "Date", "DateTime", "Decimal", "Integer", "Real", "Boolean",
               "Distance", "Measure", "Record", "RecordType", "ScopedName", "FileName", "MimeFileType",
               "beginPosition", "endPosition", "timePosition", "pos"}
GML_VALUES = {"name", "identifier"}                # elemen gml berisi teks langsung
ATTR_VALUES = {"ScopedName": "codeSpace", "FileName": "src", "MimeFileType": "type"}
SELF_LABEL = {"beginPosition", "endPosition"}      # nama sendiri dipakai sebagai label
ENUM_TEXT = {"MD_TopicCategoryCode", "MD_ObligationCode", "MD_PixelOrientationCode", "LE_ParameterDirection"}                 # nilai teks langsung (bukan codeListValue)
STRUCTURAL = {"contactInfo", "individual", "party", "thesaurusName"}
MULTILINE = {"abstract", "purpose", "statement", "explanation", "description",
             "useLimitation", "handlingDescription", "userNote", "contactInstructions",
             "measureDescription", "supplementalInformation", "rationale", "otherConstraints",
             "maintenanceNote", "evaluationMethodDescription"}
DATE_PLACEHOLDER = "T00:00:00"


def _w(s):
    return s.split()


CODELISTS = {
    "CI_RoleCode": _w("resourceProvider custodian owner user distributor originator pointOfContact principalInvestigator processor publisher author sponsor coAuthor collaborator editor mediator rightsHolder contributor funder stakeholder"),
    "CI_DateTypeCode": _w("creation publication revision expiry lastUpdate lastRevision nextUpdate unavailable inForce adopted deprecated superseded validityBegins validityExpires released distribution"),
    "CI_PresentationFormCode": _w("documentDigital documentHardcopy imageDigital imageHardcopy mapDigital mapHardcopy modelDigital modelHardcopy profileDigital profileHardcopy tableDigital tableHardcopy videoDigital videoHardcopy audioDigital audioHardcopy multimediaDigital multimediaHardcopy diagramDigital diagramHardcopy"),
    "MD_ScopeCode": _w("attribute attributeType collectionHardware collectionSession dataset series nonGeographicDataset dimensionGroup feature featureType propertyType fieldSession software service model tile initiative stereomate sensor platformSeries sensorSeries productionSeries transferAggregate otherAggregate"),
    "MD_ProgressCode": _w("completed historicalArchive obsolete onGoing planned required underDevelopment final pending retired superseded tentative valid accepted notAccepted withdrawn proposed deprecated"),
    "MD_MaintenanceFrequencyCode": _w("continual daily weekly fortnightly monthly quarterly biannually annually asNeeded irregular notPlanned unknown periodic semimonthly biennially"),
    "MD_RestrictionCode": _w("copyright patent patentPending trademark license intellectualPropertyRights restricted otherRestrictions unrestricted licenceUnrestricted licenceEndUser licenceDistributor private statutory confidential sensitivity"),
    "MD_ClassificationCode": _w("unclassified restricted confidential secret topSecret sensitiveButUnclassified forOfficialUseOnly protected limitedDistribution"),
    "MD_SpatialRepresentationTypeCode": _w("vector grid textTable tin stereoModel video"),
    "MD_TopologyLevelCode": _w("geometryOnly topology1D planarGraph fullPlanarGraph surfaceGraph fullSurfaceGraph topology3D fullTopology3D abstract"),
    "MD_GeometricObjectTypeCode": _w("complex composite curve point solid surface"),
    "MD_KeywordTypeCode": _w("discipline place stratum temporal theme dataCentre featureType instrument platform process project service product subTopicCategory"),
    "DS_AssociationTypeCode": _w("crossReference largerWorkCitation partOfSeamlessDatabase source stereoMate isComposedOf"),
    "CI_OnLineFunctionCode": _w("download information offlineAccess order search completeMetadata browseGraphic upload emailService browsing fileAccess"),
    "CI_TelephoneTypeCode": _w("voice facsimile sms"),
    "DQ_EvaluationMethodTypeCode": _w("directInternal directExternal indirect"),
    "MD_CharacterSetCode": _w("utf8 utf16 usAscii 8859part1 shiftJIS big5 GB2312"),
    "LanguageCode": _w("ind eng"),
    "CountryCode": ["ID"],
    "MD_ObligationCode": _w("mandatory optional conditional"),
    "MD_PixelOrientationCode": _w("centre lowerLeft lowerRight upperRight upperLeft"),
    "LE_ParameterDirection": _w("in out inOut"),
    "MD_CellGeometryCode": _w("point area voxel stratum"),
    "MD_DimensionNameTypeCode": _w("row column vertical track crossTrack line sample time"),
    "MD_CoverageContentTypeCode": _w("image thematicClassification physicalMeasurement auxillaryInformation qualityInformation referenceInformation modelResult coordinate"),
    "MD_ImagingConditionCode": _w("blurredImage cloud degradingObliquity fog heavySmokeOrDust night rain semiDarkness shadow snow terrainMasking"),
    "MI_OperationTypeCode": _w("real simulated synthesized"),
    "MI_PriorityCode": _w("critical highImportance mediumImportance lowImportance"),
    "MI_GeometryTypeCode": _w("point linear areal strip"),
    "MI_ObjectiveTypeCode": _w("instantaneousCollection persistentView survey"),
    "MI_TriggerCode": _w("automatic manual preProgrammed"),
    "MI_ContextCode": _w("acquisition pass wayPoint"),
    "MI_SequenceCode": _w("start end instantaneous"),
    "MD_DatatypeCode": _w("class codelist enumeration codelistElement abstractClass aggregateClass specifiedClass datatypeClass interfaceClass unionClass metaClass typeClass characterString integer association"),
    "MD_TopicCategoryCode": _w("boundaries farming biota climatologyMeteorologyAtmosphere economy elevation environment geoscientificInformation health imageryBaseMapsEarthCover intelligenceMilitary inlandWaters location oceans planningCadastre society structure transportation utilitiesCommunication"),
}

SECTION_NAMES = {
    "metadataIdentifier": "Identifier Metadata", "defaultLocale": "Bahasa & Encoding",
    "parentMetadata": "Metadata Induk", "metadataScope": "Cakupan Metadata",
    "contact": "Kontak Metadata", "dateInfo": "Tanggal Metadata",
    "metadataStandard": "Standar Metadata", "metadataProfile": "Profil Metadata",
    "alternativeMetadataReference": "Rujukan Metadata Alternatif", "otherLocale": "Bahasa Lain",
    "metadataLinkage": "Tautan Metadata", "spatialRepresentationInfo": "Representasi Spasial",
    "referenceSystemInfo": "Sistem Referensi", "metadataExtensionInfo": "Ekstensi Metadata",
    "identificationInfo": "Identifikasi Data", "contentInfo": "Katalog Fitur",
    "distributionInfo": "Distribusi", "dataQualityInfo": "Kualitas Data",
    "resourceLineage": "Lineage", "portrayalCatalogueInfo": "Katalog Portrayal",
    "metadataConstraints": "Batasan Metadata", "applicationSchemaInfo": "Skema Aplikasi",
    "metadataMaintenance": "Pemeliharaan Metadata", "acquisitionInformation": "Informasi Akuisisi",
}


def is_value(el):
    n = local(el.tag)
    return n in VALUE_TYPES or (n in GML_VALUES and isinstance(el.tag, str) and el.tag.startswith("{%s}" % NS_GML))


def local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


# ---------------------------------------------------------------- item model
class Field:
    def __init__(self, trail, el, kind, extra=None):
        self.trail = list(trail)
        self.el = el
        self.kind = kind            # value | code | enum | wrapper | attr | pos
        self.extra = extra          # nama atribut (attr) / indeks komponen (pos)
        self.section = ""
        self.value_name = local(el.tag)

    @property
    def names(self):
        return tuple(re.sub(r"\[\d+\].*", "", t) for t in self.trail)

    @property
    def label(self):
        return " › ".join(self.trail) if self.trail else self.value_name

    @property
    def multiline(self):
        return bool(self.names) and self.names[-1] in MULTILINE

    @property
    def options(self):
        return CODELISTS.get(self.value_name, [])

    def _value_child(self):
        for c in self.el:
            if is_value(c):
                return c
        return None

    def get(self):
        if self.kind == "attr":
            return self.el.attrib.get(self.extra, "")
        if self.kind == "pos":
            parts = (self.el.text or "").split()
            return parts[self.extra] if len(parts) > self.extra else ""
        if self.kind == "code":
            return self.el.attrib.get("codeListValue") or (self.el.text or "").strip()
        if self.kind == "wrapper":
            c = self._value_child()
            return ((c.text if c is not None else self.el.text) or "").strip()
        text = (self.el.text or "").strip()
        if self.value_name in ("Date", "DateTime") and text == DATE_PLACEHOLDER:
            return ""
        return text

    def set(self, text):
        text = text if self.multiline else text.strip()
        if self.kind == "attr":
            self.el.set(self.extra, text)
            return
        if self.kind == "pos":
            parts = (self.el.text or "").split()
            parts += [""] * (2 - len(parts))
            parts[self.extra] = text
            self.el.text = " ".join(parts).strip()
            return
        if self.kind == "code":
            self.el.set("codeListValue", text)
            self.el.text = text
        elif self.kind == "wrapper":
            c = self._value_child()
            if c is None:
                if not text:
                    return
                c = ET.SubElement(self.el, "{%s}CharacterString" % NS_GCO)
            c.text = text
        else:
            self.el.text = text
            if text:
                for k in [k for k in self.el.attrib if local(k) == "nilReason"]:
                    del self.el.attrib[k]


class Block:
    """Judul satu instans dari blok berulang (hanya dibuat bila instans > 1)."""
    def __init__(self, trail, el, parent):
        self.trail, self.el, self.parent = list(trail), el, parent

    @property
    def label(self):
        return " › ".join(self.trail)


class AddBtn:
    """Tombol tambah blok. options = [(nama_kelas, elemen_sumber_klon)]."""
    def __init__(self, name, trail, parent, options):
        self.name, self.trail, self.parent, self.options = name, list(trail), parent, options


class Section:
    def __init__(self, name, idx, count, el, parent, items, options):
        self.name, self.idx, self.count = name, idx, count
        self.el, self.parent, self.items, self.options = el, parent, items, options
        self.repeatable = name in REPEATABLE.get(local(parent.tag), ())

    @property
    def fields(self):
        return [i for i in self.items if isinstance(i, Field)]

    @property
    def base_title(self):
        return SECTION_NAMES.get(self.name, self.name)

    @property
    def title(self):
        return "%s #%d" % (self.base_title, self.idx) if self.idx else self.base_title


def can_add(parent, prop, count):
    mx = MAXOCC.get(local(parent.tag), {}).get(prop)
    return mx is None or count < mx


def _options(group):
    opts = {}
    for g in group:
        opts[local(g[0].tag) if len(g) else ""] = g      # elemen terakhir per kelas
    return list(opts.items())


def collect(el, trail, out):
    rep_props = REPEATABLE.get(local(el.tag), ())
    kids = list(el)
    counts = Counter(k.tag for k in kids)
    groups = {}
    for k in kids:
        groups.setdefault(k.tag, []).append(k)
    seen = Counter()
    for k in kids:
        name = local(k.tag)
        if is_value(k):
            out.append(Field(trail + ([name] if name in SELF_LABEL else []), k, "value"))
        elif "codeListValue" in k.attrib:
            out.append(Field(trail, k, "code"))
        elif name in ENUM_TEXT:
            out.append(Field(trail, k, "enum"))
        elif name[:1].isupper():                 # elemen kelas, mis. CI_Citation
            collect(k, trail, out)
        else:                                    # elemen properti
            seen[k.tag] += 1
            group = groups[k.tag]
            label = name
            if counts[k.tag] > 1:
                label += "[%d]" % seen[k.tag]
                kinds = {local(g[0].tag) if len(g) else "" for g in group}
                if len(kinds) > 1 and len(k):
                    label += " (%s)" % local(k[0].tag)
            rep = name in rep_props
            if rep and counts[k.tag] > 1:
                out.append(Block(trail + [label], k, el))
            if len(k) == 0:
                if name not in STRUCTURAL:
                    out.append(Field(trail + [label], k, "wrapper"))
            else:
                collect(k, trail + [label], out)
            if rep and seen[k.tag] == counts[k.tag] and can_add(el, name, counts[k.tag]):
                out.append(AddBtn(name, trail, el, _options(group)))


def build_sections(root):
    counts = Counter(c.tag for c in root)
    seen = Counter()
    sections = []
    for c in root:
        seen[c.tag] += 1
        name = local(c.tag)
        idx = seen[c.tag] if counts[c.tag] > 1 else 0
        items = []
        collect(c, [], items)
        for i in items:
            if isinstance(i, Field):
                i.section = name
        group = [x for x in root if x.tag == c.tag]
        sections.append(Section(name, idx, counts[c.tag], c, root, items, _options(group)))
    return sections


# ---------------------------------------------------------------- ubah struktur
def _fresh_ids(root, new):
    """Beri gml:id baru yang unik pada `new` agar tidak bentrok dengan id yang sudah ada."""
    used = {v for e in root.iter() for k, v in e.attrib.items() if local(k) == "id"}
    for e in new.iter():
        for k in list(e.attrib):
            if local(k) == "id":
                base = re.sub(r"\d+$", "", e.attrib[k]) or "id"
                i = 1
                while "%s%d" % (base, i) in used:
                    i += 1
                e.attrib[k] = "%s%d" % (base, i)
                used.add(e.attrib[k])


def add_block(root, parent, src):
    """Klon `src`, kosongkan nilainya, sisipkan setelah instans terakhir tag yang sama."""
    new = copy.deepcopy(src)
    for e in new.iter():
        n = local(e.tag)
        if (is_value(e) and n != "Boolean") or n in ENUM_TEXT:
            e.text = ""
            if n in ATTR_VALUES and ATTR_VALUES[n] in e.attrib:
                e.set(ATTR_VALUES[n], "")
    _fresh_ids(root, new)
    kids = list(parent)
    last = max(i for i, k in enumerate(kids) if k.tag == src.tag)
    parent.insert(last + 1, new)
    return new


_SNIPS = {}


def snippet(name):
    """Salinan elemen snippet bernama dari snippets.xml (struktur kosong siap sisip)."""
    if not _SNIPS:
        tree = ET.parse(os.path.join(os.path.dirname(__file__), "snippets.xml"))  # nosec B314
        for sn in tree.getroot():
            _SNIPS[sn.get("name")] = sn[0]
    return copy.deepcopy(_SNIPS[name])


def insert_ordered(container, new):
    """Sisipkan `new` ke `container` pada posisi sesuai urutan skema (XSD)."""
    order = ORDER.get(local(container.tag), [])
    name = local(new.tag)
    idx = order.index(name) if name in order else len(order)
    pos = len(container)
    for i, c in enumerate(container):
        cn = local(c.tag)
        if (order.index(cn) if cn in order else len(order)) > idx:
            pos = i
            break
    container.insert(pos, new)


def add_snippet(root, container, name):
    new = snippet(name)
    _fresh_ids(root, new)
    insert_ordered(container, new)
    return new


def remove_block(parent, el):
    parent.remove(el)


# ---------------------------------------------------------------- muat / simpan
def load(path):
    with open(path, "rb") as fh:
        data = fh.read()
    text = data.decode("utf-8-sig")
    fixes = []
    if "<mdq:>" in text:
        text = text.replace("<mdq:>", "<mdq:DQ_DomainConsistency>").replace(
            "</mdq:>", "</mdq:DQ_DomainConsistency>")
        fixes.append("Tag tidak valid <mdq:> diperbaiki menjadi <mdq:DQ_DomainConsistency>.")
    if "mdq:DQEvaluationMethod" in text:
        text = text.replace("mdq:DQEvaluationMethod", "mdq:DQ_EvaluationMethod")
        fixes.append("mdq:DQEvaluationMethod diperbaiki menjadi mdq:DQ_EvaluationMethod.")
    root = None
    for ev, d in ET.iterparse(io.BytesIO(text.encode("utf-8")), events=("start-ns", "start")):  # nosec B314
        if ev == "start-ns":
            prefix, uri = d
            if prefix:
                try:
                    ET.register_namespace(prefix, uri)
                except ValueError:
                    pass
        elif root is None:
            root = d
    return root, fixes


def save(root, path):
    if hasattr(ET, "indent"):
        ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=False)


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}.*)?$")


def validate(fields):
    """Daftar peringatan untuk nilai yang sudah diisi tetapi formatnya salah."""
    problems = []
    vals = {}
    for f in fields:
        v = f.get()
        vals.setdefault((f.section, f.names), v)
        if not v:
            continue
        try:
            if f.value_name in ("Decimal", "Real", "Distance"):
                float(v)
            elif f.value_name == "Integer":
                int(v)
            elif f.value_name in ("Date", "DateTime", "beginPosition", "endPosition") and not DATE_RE.match(v):
                raise ValueError
        except ValueError:
            problems.append("%s › %s: nilai '%s' tidak valid untuk %s" % (f.section, f.label, v, f.value_name))
    try:
        b = {n: float(vals[("identificationInfo", ("extent", "geographicElement", n))])
             for n in ("westBoundLongitude", "eastBoundLongitude", "southBoundLatitude", "northBoundLatitude")}
        if not (-180 <= b["westBoundLongitude"] <= 180 and -180 <= b["eastBoundLongitude"] <= 180
                and -90 <= b["southBoundLatitude"] <= 90 and -90 <= b["northBoundLatitude"] <= 90):
            problems.append("Ekstensi: koordinat di luar rentang geografis.")
        if b["westBoundLongitude"] > b["eastBoundLongitude"] or b["southBoundLatitude"] > b["northBoundLatitude"]:
            problems.append("Ekstensi: west > east atau south > north.")
    except (KeyError, ValueError):
        pass
    return problems


# ---------------------------------------------------------------- hanya yang terisi
# properti pembeda: tidak cukup sendirian untuk mempertahankan sebuah blok (mis. role tanpa pihak, dateType tanpa tanggal)
WEAK = {"dateType", "numberType", "role", "function", "type", "associationType", "direction", "dimensionName"}


def prune_empty(root):
    """Hapus semua elemen yang tidak berisi nilai (teks/kode terisi). `root` sendiri selalu dipertahankan."""
    def text_ok(el):
        t = (el.text or "").strip()
        return bool(t) and not (local(el.tag) in ("Date", "DateTime") and t == DATE_PLACEHOLDER)

    def walk(el):                      # -> (dipertahankan, mengandung isi kuat)
        n = local(el.tag)
        if is_value(el) or n in ENUM_TEXT:
            ok = text_ok(el)
            return ok, ok
        if "codeListValue" in el.attrib:
            ok = bool(el.attrib["codeListValue"].strip())
            return ok, ok
        strong = False
        for ch in list(el):
            keep, st = walk(ch)
            if keep:
                strong = strong or st
            else:
                el.remove(ch)
        if any(local(k) == "href" and v.strip() for k, v in el.attrib.items()):
            return True, False         # rujukan (xlink:href) ikut dibawa hanya bila blok induknya terisi
        if n in WEAK:
            return len(el) > 0, False
        return strong, strong

    for ch in list(root):
        if not walk(ch)[0]:
            root.remove(ch)
    return root
