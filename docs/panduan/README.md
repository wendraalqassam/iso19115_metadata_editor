# Panduan GeoMDB – Metadata Editor

Panduan lengkap plugin QGIS **GeoMDB – Metadata Editor** versi **1.1.0**, mulai dari pemasangan sampai contoh
pengisian metadata pada berbagai kondisi data. Setiap fitur dibahas dalam satu **sesi** yang bisa dipelajari
terpisah, misalnya sebagai materi bimbingan teknis.

**Untuk siapa:**

- **Produsen data** (OPD/unit kerja): membuat dan melengkapi metadata data spasial yang dihasilkannya.
- **Walidata / pengelola simpul jaringan**: memeriksa metadata, mendistribusikan data, dan mengelola GeoNode.
- **Admin server GeoNode**: mengatur izin akun dan memasang tambalan server (sesi 14–16).

## Daftar sesi

| Sesi | Judul | Isi | Terutama untuk |
|---|---|---|---|
| 01 | [Instalasi & pembaruan](01-instalasi.md) | Pasang dari repositori atau ZIP, buka, perbarui, hapus | Semua |
| 02 | [Mengenal editor](02-mengenal-editor.md) | Bagian layar, jenis kolom, 13 tahapan, mode tampilan | Semua |
| 03 | [Memulai metadata](03-memulai-metadata.md) | Template kosong, contoh, buka XML, ambil dari layer | Produsen |
| 04 | [Kontak tersimpan](04-kontak-tersimpan.md) | Simpan, panggil, dan kelola kontak; memilih peran | Produsen |
| 05 | [Tahap 1 – Informasi Metadata](05-tahap-1-informasi-metadata.md) | Identifier, bahasa, tanggal, standar, kontak metadata | Produsen |
| 06 | [Tahap 2 – Identitas Data](06-tahap-2-identitas-data.md) | Judul, abstrak, kontak, cakupan, kata kunci, format | Produsen |
| 07 | [Tahap 3–5 – Representasi, CRS & Konten](07-tahap-3-5-representasi-crs-konten.md) | Vektor, raster, sistem koordinat, katalog unsur, band | Produsen |
| 08 | [Tahap 6 – Distribusi & Akses Data](08-tahap-6-distribusi.md) | Format, distributor, WMS/WFS/unduhan | Produsen, Walidata |
| 09 | [Tahap 7 – Kualitas Data](09-tahap-7-kualitas-data.md) | Laporan kualitas, jenis hasil, contoh ukuran | Produsen |
| 10 | [Tahap 8 – Riwayat Data](10-tahap-8-riwayat-data.md) | Lineage, sumber data, tahap proses | Produsen |
| 11 | [Tahap 9–13 – Batasan, Pemeliharaan & lainnya](11-tahap-9-13-lainnya.md) | Katalog penyajian, batasan & keamanan, skema, pemeliharaan, ekstensi | Produsen, Walidata |
| 12 | [Validasi & simpan](12-validasi-dan-simpan.md) | Validasi isian, draf, opsi simpan, catatan kesesuaian | Semua |
| 13 | [Ekspor XML](13-ekspor-xml.md) | ISO 19139 untuk Palapa/CSW atau GeoNode, ISO 19115-3 | Semua |
| 14 | [Unggah metadata lewat web GeoNode](14-unggah-lewat-web-geonode.md) | Download ISO → lengkapi → Upload Metadata | Produsen, Walidata |
| 15 | [Login & ambil dari GeoNode](15-login-dan-ambil-dari-geonode.md) | Login, katalog dataset, ambil ke formulir | Produsen, Admin |
| 16 | [Kirim ke GeoNode](16-kirim-ke-geonode.md) | Perbarui metadata, mode preserve, pengaman, pulihkan | Produsen, Admin |
| 17 | [Studi kasus berbagai kondisi](17-studi-kasus.md) | Sembilan skenario dari awal sampai selesai | Semua |
| 18 | [Pemecahan masalah](18-pemecahan-masalah.md) | Gejala, penyebab, dan solusinya | Semua |

## Alur kerja singkat

```
Data spasial di QGIS / XML lama / dataset GeoNode
        │
        ▼
GeoMDB: mulai metadata (sesi 03) → isi 13 tahapan (sesi 04–11) → Validasi Isian
        │
        ├─► Simpan / Simpan Sebagai ......... berkas kerja ISO 19115-3 (sesi 12)
        ├─► Export ISO 19139 untuk Palapa/CSW  (sesi 13)
        ├─► Export ISO 19139 untuk GeoNode ... Upload Metadata lewat web (sesi 14)
        └─► Kirim ke GeoNode ................ langsung dari QGIS (sesi 15–16)
```

## Contoh yang dipakai

Contoh dan tangkapan layar memakai data latihan **Batas Wilayah Administrasi Desa/Kelurahan Kabupaten Belitung**
(50 poligon, sumber data batas desa/kelurahan BIG skala 1:10.000). Nama petugas, email, dan alamat GeoNode di
panduan ini adalah **contoh**; ganti dengan data instansi Anda.

## Konvensi penulisan

- **Teks tebal** = nama tombol, menu, tahapan, atau kolom persis seperti di layar.
- `Teks kode` = nilai yang diketik, nama berkas, atau kode (mis. `ind`, `EPSG`).
- Menu QGIS ditulis berurutan dengan tanda ›, misalnya **Plugins › Manage and Install Plugins…**.
- Blok "**Kondisi:**" menjelaskan langkah yang berbeda untuk keadaan tertentu.
