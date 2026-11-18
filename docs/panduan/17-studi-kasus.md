# Sesi 17 – Studi kasus berbagai kondisi

**Tujuan:** mempraktikkan alur lengkap dari awal sampai berkas/portal untuk kondisi data yang berbeda-beda.
**Waktu:** ±15–30 menit per kasus.

| Kasus | Kondisi | Hasil akhir |
|---|---|---|
| [A](#a-data-vektor-baru-dari-berkas) | Data vektor baru (Shapefile/GeoPackage) | Arsip ISO 19115-3 + XML untuk Palapa/CSW |
| [B](#b-melengkapi-metadata-dataset-geonode-lewat-web) | Dataset sudah diunggah ke GeoNode, metadatanya minim | Metadata lengkap di GeoNode lewat web |
| [C](#c-memperbarui-metadata-dataset-geonode-dari-qgis) | Dataset GeoNode sudah terbit, Anda punya izin ubah | Metadata diperbarui langsung dari QGIS |
| [D](#d-data-raster-dem-atau-citra) | Data raster (DEM atau citra) | Metadata raster lengkap |
| [E](#e-data-deret-waktu) | Data deret waktu (beberapa tahun) | Cakupan waktu & pemeliharaan yang benar |
| [F](#f-metadata-dari-arcgis) | Metadata sudah dibuat di ArcGIS | Metadata yang sama di GeoMDB |
| [G](#g-revisi-metadata-karena-data-diperbarui) | Data diperbarui (versi baru) | Metadata revisi |
| [H](#h-data-terbatas-atau-rahasia) | Data tidak untuk publik | Metadata dengan batasan akses yang benar |
| [I](#i-dataset-geonode-yang-belum-dipublikasikan) | Dataset GeoNode belum terbit, login username/password | Metadata terkirim tanpa bisa diambil dari QGIS |

---

## A. Data vektor baru dari berkas

**Kondisi:** OPD punya `ADMINISTRASI_AR_DESA_KAB_BELITUNG.shp` dan belum punya metadata.

1. Buka Shapefile di QGIS. Bila sempat, isi **Layer Properties › Metadata** (judul, abstrak, kata kunci, kontak).
2. GeoMDB › **Template Kosong** › pilih layer › **Ambil Metadata dari Layer Aktif** ([sesi 03](03-memulai-metadata.md)).
   Cakupan, CRS, geometri, jumlah objek, format, dan ukuran berkas terisi.
3. Tahap 1: **Metadata Identifier** `ADMINISTRASI_AR_DESA_10K_1902_2023`, bahasa, kontak metadata (**📋 Panggil Kontak**).
4. Tahap 2: judul yang jelas, abstrak 3–6 kalimat, tujuan, status **Selesai (Completed)**, periode
   `2019-01-01`–`2023-12-31`, Topic Category **Boundaries**, kata kunci Theme dan Place.
5. Tahap 3: **Resolusi Spasial (Denominator)** `10000`. Tahap 5: **Judul Katalog Unsur** KUGI.
6. Tahap 6: kontak distributor (Walidata). Tahap 7: minimal satu laporan, mis. Domain Consistency kode wilayah.
7. Tahap 8: lineage, satu sumber data, tiga tahap proses. Tahap 10: batasan & lisensi. Tahap 12: **As Needed**.
8. **✓ Validasi Isian**, lengkapi isian inti yang kosong.
9. Centang **Hanya simpan isian yang terisi**, **📁 Simpan Sebagai…** (arsip ISO 19115-3).
10. **Export ISO 19139 › Untuk Palapa / CSW** untuk dikirim ke geoportal.

## B. Melengkapi metadata dataset GeoNode lewat web

**Kondisi:** produsen sudah mengunggah dataset ke GeoNode, metadatanya hanya judul dan abstrak singkat.

Ikuti [sesi 14](14-unggah-lewat-web-geonode.md):
**Download › ISO Metadata** → **Buka XML Metadata…** → lengkapi → **Simpan Sebagai…** (arsip) →
**Export ISO 19139 › Untuk GeoNode** → **Edit › Upload Metadata** pada dataset yang sama → **Reload**.

Kelengkapan hasil di GeoNode bergantung pada server sudah ditambal atau belum.

## C. Memperbarui metadata dataset GeoNode dari QGIS

**Kondisi:** dataset sudah terbit, akun Anda punya izin ubah metadata, server bisa dijangkau dari QGIS.

1. **Ambil dari GeoNode…** › URL › **Login username/password…** › **Masuk & muat dataset** ([sesi 15](15-login-dan-ambil-dari-geonode.md)).
2. Cari dataset, **⬇ Ambil ke formulir**. Baris status: `Tertaut ke GeoNode: …`.
3. Lengkapi isian; **Simpan Sebagai…** untuk arsip.
4. **☁ Kirim ke GeoNode…** › dataset **Asal formulir** sudah terpilih › centang preserve **hanya** bila admin
   memastikan server sudah ditambal › **⬆ Perbarui di GeoNode** ([sesi 16](16-kirim-ke-geonode.md)).
5. Periksa log langkah `5/5`. Bila keliru, **Pulihkan dari cadangan…**.

## D. Data raster (DEM atau citra)

**Kondisi:** DEM GeoTIFF resolusi 8 m, 6000 × 4500 piksel, EPSG:32748.

1. **Template Kosong** (pengambilan otomatis dari layer belum mendukung raster). Untuk acuan, buka
   `contoh_raster.xml` di folder plugin ([sesi 03](03-memulai-metadata.md#b-contoh-metadata)).
2. Ambil nilai dari QGIS: klik kanan layer › **Properties › Information** (ukuran piksel, jumlah baris/kolom, band,
   extent, CRS).
3. Tahap 2: cakupan wilayah dalam derajat WGS 84 (ubah extent ke EPSG:4326 bila perlu), Topic Category
   **Elevation**, format GeoTIFF.
4. Tahap 3: **Tipe Representasi Spasial** Grid, **Resolusi Spasial (Meter)** `8`, centang
   **Aktifkan Informasi Grid / Raster Terektifikasi**: dimensi row `4500`/`8`, column `6000`/`8`,
   **Geometri Sel** `point` ([sesi 07](07-tahap-3-5-representasi-crs-konten.md)).
5. Tahap 4: `EPSG` / `32748` / Projected.
6. Tahap 5: **Aktifkan Deskripsi Cakupan**, Content Type `physicalMeasurement`, satu band Elevasi (min/max).
   Untuk citra: **Aktifkan Deskripsi Citra**, satu blok band per kanal, tutupan awan.
7. Tahap 7: **Gridded Data Positional Accuracy** atau **Absolute External Positional Accuracy** (RMSE vertikal/
   horizontal bila diuji).
8. Simpan dua versi: berkas kerja dengan **Kompatibel Sistem BIG** tidak dicentang (untuk dibuka ulang), dan versi
   untuk sistem BIG dengan opsi itu dicentang ([sesi 12](12-validasi-dan-simpan.md)).
9. Ekspor ISO 19139 bila perlu; baca catatan kesesuaian (GCP dan rentang panjang gelombang band tidak ikut).

## E. Data deret waktu

**Kondisi:** satu dataset berisi data tahun 2021, 2023, dan 2024 (mis. kolom `tanggal` bertipe Date per fitur).

1. Di QGIS, bila kolom tahun masih angka, buat kolom tanggal dengan Field Calculator: `make_date("tahun", 1, 1)`.
2. Opsional: **Layer Properties › Temporal** aktif dengan rentang tetap. Rentang ini terbaca oleh
   **Ambil Metadata dari Layer Aktif**.
3. Tahap 2 tab **Cakupan & Topik**: **Periode Awal** `2021-01-01`, **Periode Akhir** `2024-12-31`.
4. Tab **Kata Kunci**: kelompok tipe **Temporal** berisi `2021`, `2023`, `2024`.
5. Abstrak: sebutkan tahun-tahun yang tersedia dan kolom waktunya.
6. Tahap 8: satu tahap proses per periode pemutakhiran.
7. Tahap 12: **Frekuensi Pemeliharaan Data** sesuai siklus (mis. **Annually**), catatan "Ditambah data tahun
   berikutnya setiap ….".
8. Tahap 7 (opsional): **Temporal Validity** untuk memastikan tanggal berada dalam rentang yang benar.

## F. Metadata dari ArcGIS

**Kondisi:** metadata sudah ada di ArcGIS (ArcCatalog/ArcGIS Pro).

1. Ekspor dari ArcGIS dalam format **ISO 19139**: ArcGIS Pro **Export Metadata** dengan *style* ISO 19139, atau
   ArcCatalog dengan *translator* `ARCGIS2ISO19139`.
2. GeoMDB › **Buka XML Metadata…** › berkas hasil ekspor. Baris status menampilkan `[Format ISO 19139 (gmd) Diimpor]`.
3. Periksa setiap tahapan; lengkapi bagian yang belum ada (biasanya laporan kualitas dan pemeliharaan).
4. **Simpan Sebagai…** dengan nama baru (berkas ArcGIS asli jangan ditimpa).

Berkas `.shp.xml` bawaan ArcGIS dan format FGDC tidak terbaca utuh; ekspor dulu ke ISO 19139.

## G. Revisi metadata karena data diperbarui

**Kondisi:** data batas desa diperbarui karena ada penegasan batas baru.

1. **Buka XML Metadata…** › arsip ISO 19115-3 versi sebelumnya.
2. Tahap 1: tambah blok **Tanggal Metadata** tipe **Revision** bertanggal hari ini.
3. Tahap 2: isi **Tanggal Revisi**, perbarui **Edisi**, abstrak (jumlah objek, sumber baru), dan
   **Jumlah Objek Geometri** di Tahap 3. Bila layer baru dibuka di QGIS, **Ambil Metadata dari Layer Aktif**
   memperbarui cakupan, geometri, dan ukuran berkas sekaligus.
4. Tahap 8: **tambahkan** tahap proses pemutakhiran (jangan hapus tahap lama) dan sumber data baru.
5. Tahap 7: perbarui hasil pemeriksaan mutu.
6. Tahap 12: perbarui **Tanggal Pemeliharaan / Update Data**.
7. **Simpan Sebagai…** dengan tanggal baru di nama berkas, lalu ekspor/kirim ulang.

## H. Data terbatas atau rahasia

**Kondisi:** data jaringan infrastruktur vital hanya untuk internal pemerintah daerah.

1. Tahap 10: **Batasan Akses** Restricted, **Batasan Hukum Lainnya** berisi dasar pembatasan dan cara permintaan
   data, **Klasifikasi Keamanan** sesuai ketentuan (mis. For Official Use Only/Confidential), isi **Handling
   Description**.
2. Tahap 6: jangan cantumkan tautan unduhan publik; pakai fungsi **Order** atau instruksi kontak.
3. Tahap 2: hindari detail sensitif di abstrak (lokasi persis aset vital, dsb.).
4. Metadata (bukan datanya) boleh dipublikasikan di katalog bila diizinkan: atur **Batasan Metadata** Unclassified.
5. Jangan mengunggah data rahasia ke GeoNode publik.

## I. Dataset GeoNode yang belum dipublikasikan

**Kondisi:** dataset masih menunggu persetujuan Walidata; Anda login dengan username/password.

1. **Ambil ke formulir** akan ditolak, karena CSW GeoNode tidak mengenali login username/password.
2. Di browser (login GeoNode): **Download › ISO Metadata**, lalu **Buka XML Metadata…** di GeoMDB. Simpan berkas unduhan
   itu sebagai cadangan.
3. Lengkapi isian, **Simpan Sebagai…**.
4. **☁ Kirim ke GeoNode…** › pilih dataset › ketik nama layer untuk konfirmasi (formulir tidak tertaut) ›
   **⬆ Perbarui di GeoNode** › saat diminta **Lanjut TANPA cadangan?** pilih **Yes** (cadangan sudah Anda unduh di
   langkah 2).
5. Periksa hasilnya lewat browser (**View Metadata**), karena pemeriksaan CSW dilewati.
6. Alternatif tanpa QGIS: unggah lewat web ([sesi 14](14-unggah-lewat-web-geonode.md)).

**Lanjut ke:** [Sesi 18 – Pemecahan masalah](18-pemecahan-masalah.md)
