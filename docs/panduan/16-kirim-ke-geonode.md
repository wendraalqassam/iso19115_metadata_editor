# Sesi 16 – Kirim ke GeoNode

**Tujuan:** memperbarui metadata dataset GeoNode langsung dari QGIS, dengan aman.
**Waktu:** ±40 menit.
**Butuh:** login GeoNode ([sesi 15](15-login-dan-ambil-dari-geonode.md)) dan izin *ubah metadata* pada dataset tujuan.

GeoNode tidak punya fitur *undo*. Karena itu GeoMDB memasang beberapa pengaman: cadangan otomatis, kunci dataset
tujuan, konfirmasi nama layer, dan pemulihan.

## Langkah

1. Siapkan isian formulir: hasil **Ambil dari GeoNode** (paling aman, karena sudah tertaut), XML yang dibuka, atau
   isian baru.
2. Klik **☁ Kirim ke GeoNode…** di baris bawah. Panel login sama seperti di katalog; klik
   **Masuk & muat dataset** bila belum masuk.
3. Pilih dataset tujuan dari daftar (kartu atau daftar). Dataset asal formulir sudah terpilih dan bertanda
   **Asal formulir**. Klik ganda di dialog ini **tidak** mengirim apa pun.
4. Tentukan mode pengiriman lewat kotak **Server GeoNode ini sudah ditambal — pakai preserve …** (lihat di bawah).
5. Klik **⬆ Perbarui di GeoNode**, jawab konfirmasi yang muncul.
6. Ikuti **Log**. Pengiriman terdiri dari lima langkah:

   | Log | Isi langkah |
   |---|---|
   | `1/5` | XML ISO 19139 disiapkan; `fileIdentifier` disamakan dengan UUID dataset, tanggal metadata = tanggal dataset GeoNode |
   | `2/5` | Metadata lama dicadangkan |
   | `3/5` | Mode preserve dinyalakan/dimatikan sesuai pilihan |
   | `4/5` | XML diunggah dan ditunggu sampai GeoNode selesai memprosesnya |
   | `5/5` | Hasil diperiksa: record CSW GeoNode dan isian dataset (judul, abstrak) dibandingkan dengan yang dikirim |

7. Bila langkah 5 memperingatkan bahwa XML belum diterapkan, baca pesannya. Penyebab yang umum dibahas di bawah.

## Mode biasa dan mode preserve

| | **Mode biasa** (kotak tidak dicentang, bawaan) | **Mode preserve** (kotak dicentang) |
|---|---|---|
| Yang terjadi di GeoNode | GeoNode memperbarui kolom yang dikenalnya (judul, abstrak, kata kunci, tanggal, wilayah, …) dan **membuat ulang** record CSW dari templatenya | Record CSW GeoNode menyajikan **XML GeoMDB apa adanya**: kontak, lineage, tahap proses, laporan kualitas, batasan, dll. Tautan WMS/WFS/unduhan dan gambar mini GeoNode disisipkan otomatis |
| Syarat server | Semua GeoNode | Server **sudah ditambal** dengan [alat tambal GeoNode](https://github.com/hariHK1/geonode-tambal-preserve). GeoNode 4.2.5 sampai versi terbaru punya bug yang merusak record ber-preserve |
| Kapan dipakai | Server belum ditambal, atau tidak yakin | Admin memastikan server sudah ditambal |

Status "sudah ditambal" diingat per server. Dalam mode preserve, CSW selalu menyajikan XML unggahan terakhir. Karena
itu, sunting metadata dataset tersebut selanjutnya lewat GeoMDB (ambil → sunting → perbarui), bukan lewat formulir
metadata GeoNode.

**Deteksi server yang belum ditambal:**

- Saat daftar dataset dimuat, record CSW rusak pada dataset ber-preserve memunculkan peringatan dan tautan alat
  tambal.
- Saat mengirim dengan preserve, gejala bug membuat GeoMDB otomatis mematikan preserve, mengirim ulang dalam mode
  biasa (record CSW sehat kembali), lalu menandai server "belum ditambal".

## Pengaman salah tujuan

| Pengaman | Cara kerja |
|---|---|
| **Kunci dataset asal** | Formulir hasil **Ambil dari GeoNode** hanya dikirim ke dataset asalnya. Tujuan lain harus dipilih lewat **Ganti dataset tujuan…** |
| **Ketik nama layer** | Mengirim ke dataset yang bukan asal formulir (atau dari formulir yang tidak tertaut) wajib dikonfirmasi dengan **mengetik nama layer** dataset tujuan. Salah ketik membatalkan pengiriman |
| **Cadangan otomatis** | Sebelum menimpa, metadata lama disimpan di `<folder profil QGIS>/geomdb_cadangan/<alamat server>/<nomor>-<nama layer>/` sebagai pasangan berkas `<waktu>.xml` (metadata) dan `<waktu>.json` (keterangan dataset dan tanggalnya) |
| **Cakupan & CRS berbeda** | Bila batas wilayah atau sistem koordinat di formulir berbeda dengan dataset GeoNode, GeoMDB menanyakan nilai mana yang dikirim |
| **Ambil dari layer** | **Ambil Metadata dari Layer Aktif** pada formulir tertaut memperingatkan bahwa isiannya ikut terkirim ke dataset itu |

Folder profil QGIS: **Settings › User Profiles › Open Active Profile Folder**.

## Pulihkan dari cadangan

Untuk mengembalikan metadata sebelum pengiriman, atau memperbaiki record CSW yang rusak akibat bug preserve:

1. **☁ Kirim ke GeoNode…**, masuk, pilih dataset.
2. Klik **Pulihkan dari cadangan…**, pilih berkas keterangan cadangan (`.json`) dataset itu. Folder cadangan
   langsung terbuka.
3. GeoMDB mematikan preserve, mengunggah cadangan, mengembalikan tanggal dataset semula, lalu memeriksa record CSW.

Cadangan hanya bisa dipulihkan ke dataset asalnya; GeoMDB mencocokkan UUID dan server sebelum mengunggah.

## Kondisi khusus

| Kondisi / pesan | Penyebab | Solusi |
|---|---|---|
| `Akun Anda tidak punya izin mengubah metadata dataset ini.` | Dataset bertanda **Hanya lihat** | Minta izin ke Walidata/admin, atau kirim XML ke pemilik dataset |
| `Cadangan metadata lama gagal dibuat … Lanjut TANPA cadangan?` | Paling sering karena dataset belum dipublikasikan, sehingga CSW tidak terbaca dengan login username/password | Pilih **No**, unduh dulu XML-nya lewat browser (**Download › ISO Metadata**) sebagai cadangan, lalu kirim lagi dan pilih **Yes** |
| Langkah 5: *Record CSW tidak diperiksa (dataset tidak publik …)* | Sama seperti di atas | Periksa hasilnya lewat browser (**View Metadata**) |
| Langkah 5: isian GeoNode tidak sama dengan yang dikirim | GeoNode menolak sebagian XML, atau pemrosesan belum selesai | Muat ulang daftar dan periksa dataset; ulangi pengiriman. Lihat log untuk rincian |
| Dataset menjadi *INVALID* | Pemrosesan unggahan gagal | Kirim ulang setelah memperbaiki isian, atau **Pulihkan dari cadangan…** |
| CSW dataset galat (HTTP 500) setelah memakai preserve | Server belum ditambal | **Pulihkan dari cadangan…**, lalu minta admin memasang tambalan |
| Tombol kirim tidak tersedia untuk GeoNode 4.0 – 4.2.2 | Versi itu belum punya API unggah XML | Unggah lewat web bila tersedia, atau upgrade GeoNode |
| Dataset sudah diterbitkan Walidata, akun produsen tidak bisa lagi mengubah | Alur persetujuan (advanced workflow) di server | Walidata yang mengirim, atau mengembalikan dataset ke status belum terbit |
| Tanggal dataset di GeoNode berubah | GeoNode mengambil tanggal dataset dari tanggal metadata | GeoMDB otomatis memakai tanggal dataset GeoNode saat mengirim. Bila tetap berubah, periksa **Tanggal Metadata** di Tahap 1 |

**Lanjut ke:** [Sesi 17 – Studi kasus](17-studi-kasus.md)
