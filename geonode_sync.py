"""Sinkronisasi metadata ke GeoNode — bagian logika murni (tanpa Qt, tanpa jaringan).

Alur (lihat geonode_klien.py & geonode_dialog.py):
  1. ambil detail dataset (/api/v2/datasets/{pk}) → uuid, alternate, links, perms
  2. siapkan_xml(): ekspor ISO 19139 + fileIdentifier = uuid dataset + tautan layanan GeoNode
  3. (mode preserve) PATCH /api/v2/resources/{pk} {"metadata_uploaded_preserve": true} — HARUS sebelum
     unggah: saat memproses unggahan GeoNode memanggil update_csw_metadata; bila preserve masih mati,
     metadata_xml langsung ditimpa XML buatan template GeoNode dan versi itulah yang kemudian dipertahankan
  4. POST /api/v2/uploads/upload (action=resource_metadata_upload, resource_pk) → execution_id
  5. pantau /api/v2/resource-service/execution-status/{execution_id} sampai finished/failed
  6. verifikasi lewat CSW GeoNode: GetRecordById id=uuid (pycsw:Identifier = ResourceBase.uuid,
     pycsw:XML = metadata_xml)
"""
import datetime
import os
import re
import uuid as _uuid
import xml.etree.ElementTree as ET  # nosec B405
from urllib.parse import urlsplit

from . import gmd_exporter
from .gmd_exporter import GCO, GMD, _anak, _build_online_resource_element, _q, _rapikan, _set_char

# Izin GeoNode yang memperbolehkan perubahan metadata dataset (security/permissions.py EDIT_PERMISSIONS)
IZIN_UBAH = ("change_resourcebase_metadata", "change_resourcebase")

ALAMAT = {
    "userinfo": "/api/o/v4/userinfo/",
    "datasets": "/api/v2/datasets",
    "dataset": "/api/v2/datasets/{pk}",
    "resource": "/api/v2/resources/{pk}",
    "unggah": "/api/v2/uploads/upload",
    "status": "/api/v2/resource-service/execution-status/{exec_id}",
    "csw": "/catalogue/csw",
}

# Generasi GeoNode yang didukung — kemampuan diturunkan dari kode sumber GeoNode & geonode-importer per rilis:
#  - unggah XML metadata lewat API: GeoNode 5 (inti), 4.2.3–4.4 (geonode-importer ≥ 1.0.8, handler XML);
#    4.0–4.2.2 belum punya → hanya bisa AMBIL.
#  - dataset tujuan: 5.x `resource_pk` (+ action=resource_metadata_upload); 4.x `dataset_title` = alternate.
#  - metadata_uploaded_preserve lewat API (/api/v2/resources/{pk}): 4.4 & 5.x; 4.0–4.3 tidak dibuka di API
#    (hanya Django admin) — plugin tak bisa membaca/menyalakannya.
VERSI = {
    "5": {"label": "GeoNode 5.x", "unggah": True, "preserve_api": True, "halaman": "/metadata/{pk}"},
    "4.4": {"label": "GeoNode 4.4", "unggah": True, "preserve_api": True, "halaman": "/datasets/{alternate}/metadata"},
    "4.2": {"label": "GeoNode 4.2.3 – 4.3", "unggah": True, "preserve_api": False,
            "halaman": "/datasets/{alternate}/metadata"},
    "4.0": {"label": "GeoNode 4.0 – 4.2.2 (hanya ambil)", "unggah": False, "preserve_api": False,
            "halaman": "/datasets/{alternate}/metadata"},
}


def versi_dari_api(akar, contoh_dataset=None):
    """Generasi GeoNode dari daftar endpoint /api/v2/ (publik, tanpa login) dan satu dataset contoh.
    Nomor rilis persis tidak dipublikasikan GeoNode; yang dideteksi generasinya. Catatan: 4.2.0–4.2.2
    (kolom `extent` sudah ada, handler XML belum) ikut terbaca "4.2" — unggahannya akan ditolak GeoNode.
    None bila tak dapat dipastikan (bukan GeoNode, atau 4.x tanpa dataset yang terlihat)."""
    if not isinstance(akar, dict) or "datasets" not in akar:
        return None
    if "metadata" in akar:
        return "5"
    if "assets" in akar:
        return "4.4"
    if not contoh_dataset:
        return None
    return "4.2" if "extent" in contoh_dataset else "4.0"


def halaman_metadata(versi, dataset):
    """Jalur halaman metadata GeoNode untuk dataset (sumber isian basis data yang diperiksa setelah unggah)."""
    pola = VERSI.get(versi, VERSI["5"])["halaman"]
    return pola.format(pk=dataset.get("pk"), alternate=dataset.get("alternate") or "")


# Kolom pencarian katalog (/api/v2/datasets?search=…&search_fields=…): judul, abstrak, nama layer
KOLOM_CARI = ("title", "abstract", "alternate")

# Protokol tautan sesuai record CSW buatan GeoNode sendiri
PROTOKOL_UNDUH = "WWW:DOWNLOAD-1.0-http--download"
PROTOKOL_TAUTAN = "WWW:LINK-1.0-http--link"


def url_dasar(url):
    """Normalisasi URL GeoNode: tanpa fragmen (#/...), tanpa garis miring di akhir."""
    url = (url or "").strip().split("#", 1)[0].rstrip("/")
    if url and not url.lower().startswith(("https://", "http://")):
        url = "https://" + url
    return url


def boleh_ubah(dataset):
    """`perms` di respons API berisi izin pengguna yang sedang login pada dataset itu."""
    return any(p in (dataset.get("perms") or []) for p in IZIN_UBAH)


def bersihkan_userinfo(info):
    """userinfo GeoNode ikut memuat access_token pengguna — jangan pernah disimpan/ditampilkan."""
    info = dict(info or {})
    info.pop("access_token", None)
    return info


def tautan_dataset(dataset):
    """Daftar (url, protokol, nama, deskripsi, fungsi) tautan layanan GeoNode untuk CI_OnlineResource,
    meniru record CSW buatan GeoNode: OGC:* bernama `alternate` (nama layer), unduhan, halaman dataset."""
    alt = dataset.get("alternate") or dataset.get("name") or ""
    out = []
    for ln in dataset.get("links") or []:
        jenis, url = ln.get("link_type") or "", (ln.get("url") or "").strip()
        if not url:
            continue
        if jenis.startswith("OGC:"):
            out.append((url, jenis, alt, ln.get("name") or "", "information"))
        elif jenis == "data":
            out.append((url, PROTOKOL_UNDUH, ln.get("name") or alt, ln.get("name") or "", "download"))
        elif jenis == "html":
            out.append((url, PROTOKOL_TAUTAN, alt, "Halaman dataset di GeoNode", "information"))
    return out


def _sisipkan_tautan(gmd_root, tautan):
    """Sisipkan tautan yang belum ada. Kunci = (URL, protokol), bukan nama: record CSW GeoNode menamai
    unduhan "layer.zip" sedangkan API "Zipped Shapefile" — dengan nama ikut dibandingkan, URL yang sama
    tersisip dua kali (terjadi pada 8 tautan unduhan dataset #2 staging)."""
    ada = set()
    for ci in gmd_root.iter(_q(GMD, "CI_OnlineResource")):
        ada.add((ci.findtext("%s/%s" % (_q(GMD, "linkage"), _q(GMD, "URL")), default="").strip(),
                 ci.findtext("%s/{%s}CharacterString" % (_q(GMD, "protocol"), GCO), default="").strip()))
    n = 0
    for url, protokol, nama, desk, fungsi in tautan:
        if (url, protokol) in ada:
            continue
        to_el = _anak(gmd_root, "distributionInfo", "MD_Distribution", "transferOptions", "MD_DigitalTransferOptions")
        to_el.append(_build_online_resource_element("onLine", url, protokol, nama, desk, fungsi))
        ada.add((url, protokol))
        n += 1
    return n


def _sisipkan_thumbnail(gmd_root, dataset):
    url = (dataset.get("thumbnail_url") or "").strip()
    data_id = gmd_root.find("%s/%s" % (_q(GMD, "identificationInfo"), _q(GMD, "MD_DataIdentification")))
    if not url or data_id is None or data_id.find(_q(GMD, "graphicOverview")) is not None:
        return False
    bg = _anak(data_id, "graphicOverview", "MD_BrowseGraphic")
    _set_char(bg, "fileName", url)
    _set_char(bg, "fileDescription", "Thumbnail")
    return True


def baca_waktu(teks):
    """Tanggal ISO 8601 ("2026-05-06T05:18:37.261161Z", "2026-05-06") → datetime UTC; None bila tak terbaca."""
    t = (teks or "").strip()
    if not t:
        return None
    try:
        w = datetime.datetime.fromisoformat(t.replace("Z", "+00:00"))
    except ValueError:
        return None
    if w.tzinfo is None:
        w = w.replace(tzinfo=datetime.timezone.utc)
    return w.astimezone(datetime.timezone.utc)


def tanggal_kutipan(md):
    """Tanggal pertama sitasi data (identificationInfo/*/citation/CI_Citation/date) pada gmd:MD_Metadata —
    pada record buatan GeoNode = tanggal dataset (layer.date)."""
    for idf in md.findall(_q(GMD, "identificationInfo")):
        for cd in idf.iter(_q(GMD, "CI_Date")):
            tgl = cd.find(_q(GMD, "date"))
            nilai = [(e.text or "").strip() for e in (tgl if tgl is not None else [])]
            if any(nilai):
                return next(v for v in nilai if v)
    return ""


def atur_datestamp(gmd_root, waktu):
    """dateStamp = `waktu` (UTC). PENTING: parser GeoNode (iso2dict) mengisi tanggal dataset (`date`) dari
    dateStamp — maka pengiriman memakai tanggal dataset GeoNode saat ini agar tanggalnya tidak berubah."""
    ds = gmd_root.find(_q(GMD, "dateStamp"))
    if ds is None:
        ds = ET.SubElement(gmd_root, _q(GMD, "dateStamp"))
    ds.clear()
    ET.SubElement(ds, _q(GCO, "DateTime")).text = waktu.strftime("%Y-%m-%dT%H:%M:%S") + (
        ".%06d" % waktu.microsecond if waktu.microsecond else "") + "Z"


def siapkan_xml(iso3_root, dataset, sisip_tautan=True, catatan=None, tidak_standar=None, waktu=None):
    """XML ISO 19139 siap unggah ke dataset GeoNode `dataset` (respons /api/v2/datasets/{pk}).

    - fileIdentifier = uuid dataset: identifier record CSW GeoNode selalu uuid dataset, sedangkan
      GeoNode tidak mengubah uuid dari XML unggahan; tanpa ini record CSW dan isinya tidak cocok.
    - sisip_tautan (untuk mode preserve): GeoNode tidak lagi menambahkan tautan WMS/WFS/unduhan
      dan thumbnail ke XML yang dipertahankan, jadi plugin menyisipkannya dari API dataset.
    - dateStamp = `waktu`; bawaan: tanggal dataset GeoNode (`date`) agar tanggal dataset tidak berubah
      (GeoNode mengisi `date` dari dateStamp), atau sekarang bila dataset tak punya tanggal.
    """
    if catatan is None:
        catatan = []
    uuid = (dataset.get("uuid") or "").strip()
    if not uuid:
        raise ValueError("Respons dataset GeoNode tidak memuat uuid.")
    g = gmd_exporter.export_to_gmd(iso3_root, catatan=catatan, tidak_standar=tidak_standar)
    fid = g.find(_q(GMD, "fileIdentifier"))
    lama = fid.findtext("{%s}CharacterString" % GCO, default="").strip() if fid is not None else ""
    if fid is None:
        fid = ET.SubElement(g, _q(GMD, "fileIdentifier"))
    for c in list(fid):
        fid.remove(c)
    ET.SubElement(fid, _q(GCO, "CharacterString")).text = uuid
    if lama and lama != uuid:
        catatan.append("fileIdentifier «%s» diganti uuid dataset GeoNode «%s» agar identifier record CSW "
                       "cocok dengan isinya." % (lama, uuid))
    if sisip_tautan:
        _sisipkan_tautan(g, tautan_dataset(dataset))
        _sisipkan_thumbnail(g, dataset)
    atur_datestamp(g, waktu or baca_waktu(dataset.get("date")) or datetime.datetime.now(datetime.timezone.utc))
    _rapikan(g, catatan)
    return g


def xml_bytes(gmd_root):
    gmd_exporter.register_gmd_namespaces()
    if hasattr(ET, "indent"):
        ET.indent(gmd_root, space="  ")
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(gmd_root, encoding="utf-8")


def multipart(fields, files):
    """Body multipart/form-data. files = {nama: (nama_berkas, isi_bytes, content_type)}."""
    batas = "----geomdb-" + _uuid.uuid4().hex
    bagian = []
    for nama, nilai in fields.items():
        bagian.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                       % (batas, nama, nilai)).encode("utf-8"))
    for nama, (berkas, isi, tipe) in files.items():
        bagian.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                       "Content-Type: %s\r\n\r\n" % (batas, nama, berkas, tipe)).encode("utf-8") + isi + b"\r\n")
    bagian.append(("--%s--\r\n" % batas).encode("utf-8"))
    return b"".join(bagian), "multipart/form-data; boundary=%s" % batas


def form_unggah(pk, xml, alternate="", nama_berkas="metadata.xml"):
    """Isian POST /api/v2/uploads/upload untuk mengganti metadata dataset `pk` (layer `alternate`) dengan XML.

    XML dikirim di DUA field, seperti uji bawaan GeoNode (upload/handlers/xml/tests.py): `base_file`
    menentukan handler (XMLFileHandler), sedangkan handler vektor/raster dataset hanya membaca
    `files["xml_file"]` (common/vector.py & raster.py handle_xml_file — sama di geonode-importer 4.x).
    Tanpa `xml_file` XML tidak dibaca sama sekali: metadata_uploaded=False, CSW dibuat ulang dari template.

    Penunjuk dataset dikirim untuk kedua generasi sekaligus — serializer DRF mengabaikan field yang tak
    dikenalnya: GeoNode 5 `resource_pk` + `action`; GeoNode 4.x (MetadataFileSerializer importer)
    `dataset_title` = alternate (wajib).

    Tanpa deklarasi <?xml ... encoding=...?>: GeoNode membaca berkas unggahan sebagai teks (str) lalu
    mem-parse-nya dengan lxml, yang menolak str berdeklarasi encoding ("Unicode strings with encoding
    declaration are not supported") — unggahan gagal & dataset ditandai INVALID. Isi tetap UTF-8 (bawaan XML)."""
    xml = re.sub(rb"^\s*<\?xml[^>]*\?>\s*", b"", xml.lstrip(b"\xef\xbb\xbf"))
    berkas = (nama_berkas, xml, "application/xml")
    isian = {"action": "resource_metadata_upload", "resource_pk": str(pk)}
    if alternate:
        isian["dataset_title"] = alternate
    return multipart(isian, {"base_file": berkas, "xml_file": berkas})


SELESAI, GAGAL = "finished", "failed"


def ringkas_status(st):
    """(status, pesan) dari respons execution-status GeoNode (ready / running / finished / failed)."""
    status = (st or {}).get("status") or ""
    pesan = []
    for k in ("log", "output_params"):
        v = (st or {}).get(k)
        if v:
            pesan.append(v if isinstance(v, str) else str(v))
    return status, "; ".join(pesan)[:1000]


def url_csw_record(base, uuid):
    return "%s%s?service=CSW&version=2.0.2&request=GetRecordById&id=%s&outputSchema=%s&elementSetName=full" % (
        url_dasar(base), ALAMAT["csw"], uuid, GMD)


def _rata(teks):
    return " ".join((teks or "").split())


def _nilai_teks(md):
    """Himpunan nilai teks (dinormalkan) seluruh elemen — sidik isi XML untuk perbandingan."""
    return {_rata(e.text) for e in md.iter() if _rata(e.text)}


def periksa_record_csw(xml_teks, uuid, md_kirim, preserve=False):
    """Pastikan record CSW GeoNode memuat metadata yang baru diunggah (`md_kirim`, gmd:MD_Metadata).
    Mode preserve: CSW harus menyajikan XML GeoMDB apa adanya — bila tidak, GeoNode membuat ulang
    record dari templatenya (XML unggahan tidak terbaca / preserve tidak berlaku). Mengembalikan daftar masalah."""
    masalah = []
    md = ambil_md_metadata(xml_teks)
    if md is None:
        return ["Record dengan uuid %s tidak ditemukan di CSW GeoNode (atau respons bukan XML)." % uuid]
    fid = md.findtext("%s/{%s}CharacterString" % (_q(GMD, "fileIdentifier"), GCO), default="").strip()
    if fid != uuid:
        masalah.append("fileIdentifier di CSW «%s» ≠ uuid dataset «%s»." % (fid, uuid))
    for nama, ambil in (("Judul", judul_xml), ("Abstrak", abstrak_xml)):
        harap, ada = _rata(ambil(md_kirim)), _rata(ambil(md))
        if harap and ada != harap:
            masalah.append("%s di CSW «%s» belum sama dengan yang diunggah «%s»." % (nama, ada[:80], harap[:80]))
    if preserve:
        hilang = sorted(_nilai_teks(md_kirim) - _nilai_teks(md))
        if hilang:
            masalah.append("CSW GeoNode tidak menyajikan XML GeoMDB apa adanya — %d nilai tidak ada, mis. %s. "
                           "GeoNode membuat ulang record dari templatenya." % (
                               len(hilang), ", ".join("«%s»" % h[:40] for h in hilang[:3])))
    return masalah


def periksa_dataset(dataset, md_kirim):
    """Isian basis data GeoNode (sumber halaman /metadata/{pk} & API) setelah unggah: judul & abstrak
    harus terbaca dari XML. Mengembalikan daftar masalah."""
    masalah = []
    judul, harap = _rata(dataset.get("title")), _rata(judul_xml(md_kirim))
    if harap and judul != harap:
        masalah.append("Judul dataset di GeoNode «%s» belum sama dengan yang diunggah «%s»." % (judul[:80], harap[:80]))
    abstrak = _rata(re.sub(r"<[^>]+>", " ", dataset.get("raw_abstract") or dataset.get("abstract") or ""))
    harap = _rata(abstrak_xml(md_kirim))
    if harap and harap[:60] not in abstrak:
        masalah.append("Abstrak dataset di GeoNode belum memuat abstrak yang diunggah («%s…»)." % harap[:60])
    return masalah


def layanan_wms(dataset):
    """(url layanan WMS, nama layer) dataset untuk pratinjau peta — None bila tak punya tautan OGC:WMS."""
    for ln in dataset.get("links") or []:
        if ln.get("link_type") == "OGC:WMS" and (ln.get("url") or "").strip():
            return ln["url"].strip(), dataset.get("alternate") or dataset.get("name") or ""
    return None


def wms_pratinjau(dataset):
    """(url, layer) WMS untuk pratinjau peta. Layanan GeoServer umum (…/geoserver/ows) diganti layanan
    virtual per-layer (…/geoserver/{workspace}/{nama}/ows, nama layer tanpa awalan): GetCapabilities-nya
    hanya memuat layer itu — layanan umum memuat SEMUA layer GeoNode dan lambat bila datanya banyak."""
    w = layanan_wms(dataset)
    if not w:
        return None
    url, layer = w
    ws, sep, nama = layer.partition(":")
    m = re.match(r"^(.*/geoserver)/(?:ows|wms)/?$", url.split("?", 1)[0], re.IGNORECASE)
    if m and sep and ws and nama:
        return "%s/%s/%s/ows" % (m.group(1), ws, nama), nama
    return url.split("?", 1)[0], layer


def host_sama(url, base):
    """Token autentikasi hanya boleh ikut ke host GeoNode itu sendiri (bukan ke CDN/host lain)."""
    a, b = urlsplit(url or ""), urlsplit(url_dasar(base))
    return bool(a.hostname) and (a.scheme, a.hostname, a.port) == (b.scheme, b.hostname, b.port)


def cakupan_dataset(dataset):
    """(minx, miny, maxx, maxy) EPSG:4326 dari `extent` atau `ll_bbox_polygon`; None bila tak ada."""
    ext = dataset.get("extent") or {}
    c = ext.get("coords")
    if c and len(c) == 4 and str(ext.get("srid", "EPSG:4326")).upper().endswith("4326"):
        return tuple(float(v) for v in c)
    poly = (dataset.get("ll_bbox_polygon") or {}).get("coordinates")
    if poly:
        xs = [p[0] for p in poly[0]]
        ys = [p[1] for p in poly[0]]
        return min(xs), min(ys), max(xs), max(ys)
    return None


def ringkas_dataset(dataset):
    """Isian ringkas untuk katalog (kartu/daftar)."""
    pemilik = dataset.get("owner") or {}
    nama = " ".join(x for x in (pemilik.get("first_name"), pemilik.get("last_name")) if x) or pemilik.get("username") or "-"
    return {
        "pk": dataset.get("pk"),
        "judul": dataset.get("title") or dataset.get("alternate") or "(tanpa judul)",
        "layer": dataset.get("alternate") or "",
        "jenis": {"vector": "Vektor", "raster": "Raster"}.get(dataset.get("subtype"), dataset.get("subtype") or "-"),
        "pemilik": nama,
        "tanggal": (dataset.get("date") or "")[:10],
        "kategori": ((dataset.get("category") or {}).get("gn_description") or ""),
        "abstrak": (dataset.get("raw_abstract") or dataset.get("abstract") or "").strip(),
        "boleh_ubah": boleh_ubah(dataset),
        "thumbnail": (dataset.get("thumbnail_url") or "").strip(),
    }


# ------------------------------------------------------------------ pengaman salah-tujuan
def nama_layer(dataset):
    """Nama layer tanpa workspace ("geonode:abc" → "abc") — yang diketik pengguna untuk konfirmasi."""
    return (dataset.get("alternate") or dataset.get("name") or "").split(":", 1)[-1]


def nama_cocok(ketik, dataset):
    k = (ketik or "").strip().lower()
    return bool(k) and k in {(dataset.get("alternate") or "").lower(), nama_layer(dataset).lower()}


def kode_epsg(teks):
    """"EPSG:4326", "4326", "urn:ogc:def:crs:EPSG::4326" → "4326"; None bila tak ada kode."""
    m = re.search(r"(\d{4,6})\s*$", str(teks or ""))
    return m.group(1) if m else None


def cakupan_xml(md):
    """(barat, selatan, timur, utara) EX_GeographicBoundingBox identifikasi pada gmd:MD_Metadata; None bila tak ada."""
    for bb in (b for idf in md.findall(_q(GMD, "identificationInfo")) for b in idf.iter(_q(GMD, "EX_GeographicBoundingBox"))):
        try:
            return tuple(float(bb.findtext("%s/{%s}Decimal" % (_q(GMD, t), GCO)))
                         for t in ("westBoundLongitude", "southBoundLatitude", "eastBoundLongitude", "northBoundLatitude"))
        except (TypeError, ValueError):
            return None
    return None


def crs_xml(md):
    """Kode EPSG dari referenceSystemInfo/*/referenceSystemIdentifier/*/code — hanya elemen `code`: menggabung
    semua teks ("4326 EPSG 6.11" pada record GeoNode) membuat nomor versi terbaca sebagai ujung kode."""
    for rs in md.findall(_q(GMD, "referenceSystemInfo")):
        for kode in rs.iter(_q(GMD, "code")):
            epsg = kode_epsg("".join(kode.itertext()))
            if epsg:
                return epsg
    return None


def bandingkan_cakupan(md_kirim, dataset, toleransi=0.01):
    """Perbedaan cakupan (bbox) & sistem referensi antara XML yang akan dikirim dan GeoNode saat ini
    (mis. data sudah diganti di GeoNode sejak metadata diambil). Kosong bila sama / GeoNode tak punya datanya."""
    beda = []
    gn, form = cakupan_dataset(dataset), cakupan_xml(md_kirim)
    teks = lambda b: "B %.5f, S %.5f, T %.5f, U %.5f" % b  # noqa: E731
    if gn and not form:
        beda.append("Cakupan: formulir kosong; GeoNode %s." % teks(gn))
    elif gn and form:
        rentang = max(gn[2] - gn[0], gn[3] - gn[1], 0)
        if max(abs(a - b) for a, b in zip(form, gn)) > max(1e-4, toleransi * rentang):
            beda.append("Cakupan: formulir %s; GeoNode %s." % (teks(form), teks(gn)))
    crs_gn, crs_form = kode_epsg(dataset.get("srid")), crs_xml(md_kirim)
    if crs_gn and crs_gn != crs_form:
        beda.append("Sistem referensi: formulir %s; GeoNode EPSG:%s." % (
            "EPSG:" + crs_form if crs_form else "kosong", crs_gn))
    return beda


def nama_aman(teks):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", teks or "").strip("_")[:80] or "dataset"


def lokasi_cadangan(base, dataset, waktu):
    """(folder relatif, nama dasar berkas) cadangan metadata dataset sebelum ditimpa."""
    host = urlsplit(url_dasar(base)).hostname or "geonode"
    return (os.path.join(nama_aman(host), "%s-%s" % (dataset.get("pk"), nama_aman(nama_layer(dataset)))),
            waktu.strftime("%Y%m%d-%H%M%S"))


def info_cadangan(base, dataset, versi, waktu):
    """Keterangan pendamping cadangan (JSON) — untuk memulihkan ke dataset yang sama persis."""
    return {"url": url_dasar(base), "pk": dataset.get("pk"), "uuid": dataset.get("uuid"),
            "alternate": dataset.get("alternate"), "title": dataset.get("title"), "versi": versi,
            "date": dataset.get("date"), "metadata_uploaded_preserve": dataset.get("metadata_uploaded_preserve"),
            "waktu": waktu.strftime("%Y-%m-%dT%H:%M:%SZ")}


def cek_cadangan(info, base, dataset):
    """Cadangan hanya boleh dipulihkan ke GeoNode & dataset asalnya (uuid sama). Mengembalikan daftar masalah."""
    masalah = []
    if url_dasar(info.get("url")) != url_dasar(base):
        masalah.append("Cadangan berasal dari %s, bukan %s." % (info.get("url"), url_dasar(base)))
    if not info.get("uuid") or info.get("uuid") != dataset.get("uuid"):
        masalah.append("uuid dataset tidak sama dengan cadangan (dataset #%s mungkin sudah berganti)." % info.get("pk"))
    return masalah


# Bug GeoNode (4.2.5 s.d. master, catalogue/models.py update_csw_metadata): untuk record ber-preserve,
# `etree.tostring()` (bytes) disimpan ke kolom teks metadata_xml → menjadi "b'<gmd:...'" → penyimpanan &
# penyajian CSW berikutnya gagal ("Start tag expected, '<' not found"), CSW ISO record itu HTTP 500.
BUG_PRESERVE = ("GeoNode menyimpan XML ber-preserve sebagai teks rusak (bug GeoNode), sehingga record CSW-nya "
                "tidak bisa dibaca. Preserve dimatikan agar GeoNode membuat ulang record CSW dari templatenya.")

# Alat tambal bug preserve untuk admin server GeoNode (tools/tambal-geonode di repo plugin) — repo publik.
URL_ALAT_TAMBAL = "https://github.com/hariHK1/geonode-tambal-preserve"

SARAN_CSW_RUSAK = ("Biasanya karena metadata dataset ini tersimpan rusak di GeoNode akibat bug preserve GeoNode "
                   "(server belum ditambal) atau unggahan yang gagal. Perbaiki lewat «Kirim ke GeoNode… → Pulihkan "
                   "dari cadangan…»; agar tidak terulang, admin GeoNode perlu menjalankan alat tambal: %s"
                   % URL_ALAT_TAMBAL)


SARAN_BASIC_PRIVAT = ("Dataset ini tidak publik. CSW GeoNode hanya mengenali login OAuth2, sehingga dengan login "
                      "username/password record ISO dataset tidak publik tidak bisa dibaca (ambil, cadangan, dan "
                      "pemeriksaan CSW). Pakai konfigurasi OAuth2 («Buat konfigurasi OAuth2…»), atau publikasikan "
                      "datasetnya dulu.")


def gejala_bug_preserve(pesan):
    """Pesan galat GeoNode yang khas bug preserve: metadata_xml tersimpan sebagai "b'<...'" lalu gagal di-parse."""
    p = pesan or ""
    return "Start tag expected, '<' not found" in p or "b'<gmd:" in p


def dataset_preserve(datasets):
    """Dataset yang preserve-nya aktif (field tersedia di GeoNode 4.4/5.x) — bahan deteksi server belum ditambal."""
    return [d for d in datasets or [] if d.get("metadata_uploaded_preserve") is True]


def pesan_csw(xml_teks):
    """Teks ows:ExceptionReport pada respons CSW (pycsw membalas begini bila record gagal disajikan); "" bila bukan."""
    try:
        root = ET.fromstring(xml_teks.encode("utf-8") if isinstance(xml_teks, str) else xml_teks)  # nosec B314
    except ET.ParseError:
        return ""
    if root.tag.rsplit("}", 1)[-1] != "ExceptionReport":
        return ""
    return " ".join(" ".join((e.text or "").split()) for e in root.iter() if e.tag.endswith("ExceptionText")).strip()


def ambil_md_metadata(xml_teks):
    """gmd:MD_Metadata dari respons CSW GetRecordById (atau dokumen gmd lepas); None bila tak ada."""
    try:
        root = ET.fromstring(xml_teks.encode("utf-8") if isinstance(xml_teks, str) else xml_teks)  # nosec B314
    except ET.ParseError:
        return None
    return root if root.tag == _q(GMD, "MD_Metadata") else root.find(".//" + _q(GMD, "MD_Metadata"))


def judul_formulir(iso3_root):
    """Isian "Judul Data" formulir GeoMDB (pohon ISO 19115-3) — kosong berarti formulir belum diisi."""
    from . import layout
    for s in layout.build(iso3_root)[0]:
        for n in s.nodes:
            if isinstance(n, layout.BField) and n.key == "dataTitle":
                return (n.field.get() or "").strip()
    return ""


def tautan_cocok(tautan, base, pk):
    """Apakah formulir diambil dari dataset `pk` di GeoNode `base` (lihat EditorDialog.muat_dari_geonode)."""
    return bool(tautan) and url_dasar(tautan.get("url")) == url_dasar(base) and str(tautan.get("pk")) == str(pk)


def _teks_identifikasi(md, jalur):
    for idf in md.findall(_q(GMD, "identificationInfo")):
        for kelas in idf:
            t = kelas.findtext("/".join(_q(GMD, j) for j in jalur) + "/{%s}CharacterString" % GCO)
            if t and t.strip():
                return t.strip()
    return ""


def judul_xml(md):
    """Judul data (identificationInfo/*/citation/CI_Citation/title) dari gmd:MD_Metadata."""
    return _teks_identifikasi(md, ("citation", "CI_Citation", "title"))


def abstrak_xml(md):
    """Abstrak (identificationInfo/*/abstract) dari gmd:MD_Metadata."""
    return _teks_identifikasi(md, ("abstract",))
