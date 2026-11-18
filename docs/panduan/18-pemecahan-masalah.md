# Sesi 18 – Pemecahan masalah

Daftar gejala yang sering ditemui, penyebab, dan solusinya. Rincian ada di sesi yang dirujuk.

## Instalasi & membuka plugin

| Gejala | Penyebab | Solusi |
|---|---|---|
| Ikon GeoMDB tidak muncul | Plugin belum aktif atau toolbar tersembunyi | Aktifkan di **Plugins › Manage and Install Plugins… › Installed**; **View › Toolbars › Plugins Toolbar** ([sesi 01](01-instalasi.md)) |
| Galat Python saat QGIS dibuka setelah pasang dari ZIP | Nama folder di dalam ZIP bukan `iso19115_metadata_editor` (mis. ZIP *Download* GitHub) | Buat ZIP dengan `git archive` atau ganti nama folder lalu kompres ulang ([sesi 01](01-instalasi.md#membuat-zip-sendiri-dari-repositori)) |
| Kontak tersimpan hilang setelah memperbarui plugin | `contacts_presets.json` ada di folder plugin dan ikut terganti | Kembalikan dari cadangan; lain kali cadangkan sebelum memperbarui ([sesi 04](04-kontak-tersimpan.md)) |
| Fitur di panduan tidak ada di layar | Versi plugin lama (mis. 1.0.5) | Pasang 1.1.0 |

## Formulir & berkas

| Gejala | Penyebab | Solusi |
|---|---|---|
| *Saat ini pengambilan metadata otomatis baru mendukung layer vektor* | Layer terpilih berupa raster | Isi tahap 3–5 manual ([sesi 07](07-tahap-3-5-representasi-crs-konten.md)) |
| *Pilih sebuah layer di panel Layers terlebih dahulu* | Tidak ada layer aktif | Klik layer di panel **Layers** |
| Banyak kolom tetap kosong setelah ambil dari layer | Metadata layer QGIS kosong | Isi **Layer Properties › Metadata** di QGIS, atau isi manual |
| *Gagal membaca XML* | Berkas bukan XML yang sah | Buka di editor teks; pastikan berkas lengkap |
| XML terbuka tetapi hampir semua kolom kosong | Format tidak didukung: FGDC, `.shp.xml` ArcGIS, atau respons CSW berbungkus `GetRecordByIdResponse` | Ekspor ulang ke ISO 19139 dari aplikasi asalnya, atau ambil lewat **Download › ISO Metadata** GeoNode ([sesi 03](03-memulai-metadata.md#c-buka-xml-metadata)) |
| Berkas ISO 19139 asli tertimpa | **Simpan** menulis ISO 19115-3 ke berkas aktif hasil impor | Biasakan **Simpan Sebagai…** setelah membuka berkas dari aplikasi lain ([sesi 12](12-validasi-dan-simpan.md)) |
| Isian raster tidak terbaca utuh saat berkas dibuka lagi | Berkas disimpan dengan **Kompatibel Sistem BIG** | Simpan berkas kerja raster tanpa opsi itu ([sesi 12](12-validasi-dan-simpan.md)) |
| Muncul jendela *Catatan Kesesuaian Standar* setiap kali menyimpan | Ada nilai non-standar, struktur BIG, atau draf berisi kolom kosong | Baca kelompok catatannya; jendela hanya muncul lagi bila catatannya berubah ([sesi 12](12-validasi-dan-simpan.md)) |
| Pilihan bertanda *⚠ tidak standar ISO* | Nilai dari formulir BIG yang tidak ada di daftar kode ISO | Boleh dipakai; pilih nilai standar bila tujuannya katalog ISO ([sesi 02](02-mengenal-editor.md)) |
| Hasil validasi menampilkan ratusan isian kosong | Banyak kolom opsional/tidak relevan | Fokus pada isian inti ([sesi 12](12-validasi-dan-simpan.md#validasi-isian)) |

## Ekspor

| Gejala | Penyebab | Solusi |
|---|---|---|
| Bagian tertentu tidak ada di berkas ISO 19139 | Bagian itu tidak punya padanan di ISO 19139 (hasil Descriptive/Coverage, Disaster, GCP, dll.) | Normal; tetap tersimpan di berkas ISO 19115-3 ([sesi 13](13-ekspor-xml.md)) |
| Palapa/pycsw menolak XML | Berkas berdeklarasi `<?xml …?>` | Pakai **Untuk Palapa / CSW** |
| XML tidak lolos validasi XSD | Berkas draf (kolom kosong ikut tersimpan) atau struktur BIG | Untuk validasi ISO 19115-3: centang **Hanya simpan isian yang terisi** dan lepas **Kompatibel Sistem BIG** |

## GeoNode

| Gejala | Penyebab | Solusi |
|---|---|---|
| `Detected content type 'text/plain' does not match extension '.xml'` | XML tanpa deklarasi diunggah ke GeoNode ≥ 5.1.0 | Ekspor **Untuk GeoNode** ([sesi 14](14-unggah-lewat-web-geonode.md)) |
| `Unicode strings with encoding declaration are not supported` | Deklarasi XML memuat `encoding` | Ekspor ulang **Untuk GeoNode** (`<?xml version="1.0"?>`) |
| Lineage, laporan kualitas, kontak organisasi tidak tampil di GeoNode | Server GeoNode belum ditambal; GeoNode membuat ulang XML dari templatenya | Admin memasang [tambalan](https://github.com/hariHK1/geonode-tambal-preserve), lalu unggah ulang XML |
| `Username atau password GeoNode salah` | Password salah/berubah | **Login username/password…** lagi ([sesi 15](15-login-dan-ambil-dari-geonode.md)) |
| `Konfigurasi autentikasi «…» memakai metode OAuth2…` | Konfigurasi login dari versi lama | Buat login baru dengan **Login username/password…** |
| `Dataset ini belum dipublikasikan…` | CSW tidak mengenali login username/password untuk dataset yang belum terbit | Unduh XML lewat browser, **Buka XML Metadata…**; kirim tetap bisa ([studi kasus I](17-studi-kasus.md#i-dataset-geonode-yang-belum-dipublikasikan)) |
| Permintaan *dihadang cek bot* | Cloudflare/WAF di depan GeoNode | Pengelola server mengecualikan `/api/`, `/catalogue/csw`, `/geoserver/`; sementara pakai alur web |
| `Akun Anda tidak punya izin mengubah metadata dataset ini.` | Dataset bertanda **Hanya lihat** | Minta izin ke Walidata/admin |
| Dataset menjadi *INVALID* setelah unggah | Pemrosesan XML gagal | Unggah/kirim ulang XML yang benar, atau **Pulihkan dari cadangan…** ([sesi 16](16-kirim-ke-geonode.md)) |
| CSW dataset galat (HTTP 500) | Record ber-preserve rusak di server yang belum ditambal | **Pulihkan dari cadangan…**; admin memasang tambalan |
| Tanggal dataset GeoNode berubah setelah unggah lewat web | GeoNode mengambil tanggal dataset dari tanggal metadata (`dateStamp`) | Atur **Tanggal Metadata** di Tahap 1 sebelum ekspor |
| Pratinjau peta di katalog kosong | Dataset tanpa layanan WMS, atau WMS tertutup | Tidak memengaruhi ambil/kirim metadata |

## Pertanyaan umum

**Apakah GeoMDB bisa dipakai tanpa internet?**
Ya, untuk mengisi, menyimpan, memvalidasi, dan mengekspor. Internet hanya diperlukan untuk fitur GeoNode dan
peta dasar pratinjau.

**Format mana yang harus saya simpan?**
Selalu simpan berkas ISO 19115-3 dari **Simpan** sebagai arsip. Berkas ISO 19139 dibuat dengan ekspor sesuai
tujuan (Palapa/CSW atau GeoNode).

**Apakah password GeoNode saya disimpan plugin?**
Tidak. Password disimpan terenkripsi di Authentication Manager QGIS, dilindungi master password QGIS. Plugin hanya
memakai ID konfigurasinya.

**Mengapa login OAuth2 tidak ada lagi?**
GeoMDB kini hanya memakai login username/password akun GeoNode. Login ini tidak memerlukan persiapan
apa pun di server. Batasannya: dataset yang belum dipublikasikan tidak bisa diambil dari QGIS, tetapi tetap bisa
diperbarui.

**Bisakah satu berkas metadata dipakai untuk beberapa layer?**
Sebaiknya satu metadata per dataset. Untuk dataset serupa (mis. per kecamatan), buat satu metadata, simpan, lalu
**Simpan Sebagai…** dan ubah bagian yang berbeda. Untuk seri, isi **Parent Metadata** ([sesi 05](05-tahap-1-informasi-metadata.md)).
