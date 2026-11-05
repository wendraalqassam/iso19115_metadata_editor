"""Pemeriksaan kesesuaian standar untuk pemberitahuan ke pengguna (logika murni, tanpa Qt).

Nilai daftar kode dibandingkan dengan daftar resmi ISO di daftar_kode.json — diturunkan dari
gmxCodelists.xml (ISO 19139), codelists.xml tiap paket ISO 19115-3, dan xs:enumeration XSD gmd.
"""
import json
import os

HERE = os.path.dirname(__file__)
_TABEL = None

LABEL = {"19139": "ISO 19139 (2003)", "19115-3": "ISO 19115-3"}

# Tipe nilai yang tidak boleh kosong menurut XSD (gco:CharacterString kosong masih sah).
_NILAI_WAJIB_ISI = {"Date", "DateTime", "Decimal", "Integer", "Real", "Boolean", "Distance", "Measure",
                    "Angle", "Scale", "Length", "timePosition", "beginPosition", "endPosition", "pos"}


def _tabel():
    global _TABEL
    if _TABEL is None:
        with open(os.path.join(HERE, "daftar_kode.json"), encoding="utf-8") as fh:
            _TABEL = json.load(fh)
    return _TABEL


def _lokal(tag):
    return tag.rsplit("}", 1)[-1]


def daftar_kode(standar, kelas):
    """Nilai sah daftar kode `kelas` menurut `standar` ("19139" / "19115-3"), atau None bila tak dikenal."""
    return _tabel()[standar].get(kelas) if kelas else None


def enumerasi_19139(kelas):
    """Nilai sah enumerasi tertutup ISO 19139 (mis. MD_TopicCategoryCode), atau None."""
    return _tabel()["enumerasi_19139"].get(kelas)


def kode_tidak_standar(root, standar):
    """Pesan untuk nilai codeListValue di luar daftar kode resmi `standar` ("19139" / "19115-3").
    Nilai seperti ini tetap lolos XSD, tetapi katalog lain bisa tidak mengenalinya."""
    daftar = _tabel()[standar]
    temuan = {}
    for el in root.iter():
        v = (el.get("codeListValue") or "").strip()
        sah = daftar.get(_lokal(el.tag)) if v else None
        if sah is not None and v not in sah:
            temuan.setdefault(_lokal(el.tag), set()).add(v)
    return ["%s: %s — tidak ada di daftar kode %s." % (kelas, ", ".join("«%s»" % v for v in sorted(nilai)), LABEL[standar])
            for kelas, nilai in sorted(temuan.items())]


def isian_kosong(root):
    """Jumlah elemen nilai yang kosong padahal XSD mewajibkan isinya (berkas draf)."""
    n = 0
    for el in root.iter():
        if len(el) == 0 and not (el.text or "").strip():
            if _lokal(el.tag) in _NILAI_WAJIB_ISI or el.get("codeListValue") == "":
                n += 1
    return n


def html(kelompok, escape):
    """Susun pesan HTML berkelompok: kelompok = [(judul, [pesan, ...]), ...]; kelompok kosong dilewati."""
    bagian = []
    for judul, pesan in kelompok:
        if pesan:
            bagian.append("<b>%s</b><ul>%s</ul>" % (escape(judul), "".join("<li>%s</li>" % escape(p) for p in pesan)))
    return "".join(bagian)
