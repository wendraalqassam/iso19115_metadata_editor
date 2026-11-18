# Sesi 15 – Login & ambil dari GeoNode

**Tujuan:** masuk ke GeoNode dari QGIS dengan akun sendiri, menelusuri katalog dataset, dan memuat metadata dataset
ke formulir GeoMDB.
**Waktu:** ±30 menit.
**Butuh:** internet, alamat GeoNode instansi, dan akun GeoNode (username & password).

## Persiapan

| Pihak | Yang disiapkan |
|---|---|
| **Admin GeoNode** | Akun untuk setiap produsen, dengan izin *ubah metadata* hanya pada dataset miliknya. Tidak ada pengaturan lain di server |
| **Pengguna** | Username & password **lokal** GeoNode. Akun yang hanya bisa login lewat SSO/LDAP tanpa password lokal tidak bisa dipakai |
| **QGIS** | *Master password* QGIS. Diminta saat pertama kali menyimpan login, karena password GeoNode disimpan terenkripsi di **Authentication Manager** QGIS, bukan di plugin |

## Langkah

1. Di GeoMDB klik **Ambil dari GeoNode…**. Jendela katalog terbuka.
2. **URL GeoNode**: isi alamat halaman depan GeoNode, mis. `https://geoportal.contoh.go.id`.
3. **Versi GeoNode**: biarkan **Deteksi otomatis**. Di sampingnya muncul mis. `Terdeteksi: GeoNode 5.x`. Pilih
   manual hanya bila deteksi keliru.
4. **Autentikasi**: klik **Login username/password…**, isi username lalu password akun GeoNode. Login tersimpan
   sebagai konfigurasi `GeoMDB — GeoNode <alamat> (<username>)` dan otomatis terpilih.
5. Klik **Masuk & muat dataset**. Bila berhasil: `Masuk sebagai <username> (grup: …)`, lalu daftar dataset dimuat.

Pada pemakaian berikutnya, URL dan login terakhir sudah terisi; cukup klik **Masuk & muat dataset**.

## Menelusuri katalog

| Fitur | Cara |
|---|---|
| Mode tampilan | **▦ Kartu** (gambar mini) atau **☰ Daftar** (tabel, bisa diurutkan dengan klik judul kolom) |
| Cari | Ketik di **Cari dataset (Enter)…** lalu tekan Enter. Pencarian di judul, abstrak, dan nama layer |
| Halaman | 24 dataset per halaman |
| Pratinjau | Pilih satu dataset: peta layanan WMS-nya tampil di atas peta dasar OpenStreetMap, diperbesar ke cakupannya |
| Lencana **Hanya lihat** 🔒 | Akun Anda tidak boleh mengubah metadata dataset itu. Metadatanya boleh diambil, tetapi tidak bisa dikirim balik |

## Ambil ke formulir

1. Pilih dataset, klik **⬇ Ambil ke formulir** (atau klik ganda kartunya).
2. Bila formulir sedang berisi, GeoMDB meminta konfirmasi karena isian akan diganti. Simpan dulu bila perlu.
3. Record ISO dataset dibaca dari CSW GeoNode dan dimuat ke formulir:
   - nilai contoh template GeoMDB dan teks pengisi GeoNode (`None`, `No abstract provided`) dibuang, sehingga yang
     tampil hanya data GeoNode;
   - lisensi, DOI, batasan, dan informasi tambahan GeoNode ikut terbawa;
   - baris status menjadi `Tertaut ke GeoNode: <judul> — dataset #<nomor> di <alamat>`.
4. Lengkapi isian (sesi 04–11), simpan arsipnya ([sesi 12](12-validasi-dan-simpan.md)), lalu kirim balik
   ([sesi 16](16-kirim-ke-geonode.md)).

Formulir **tertaut** berarti GeoMDB mengingat dataset asalnya, sehingga **☁ Kirim ke GeoNode…** otomatis memilih
dataset yang sama.

## Apa saja yang bisa dilakukan dengan login username/password?

| Dataset | Ambil | Perbarui | Cadangan & pemeriksaan CSW |
|---|---|---|---|
| Sudah dipublikasikan (terlihat publik) | ✓ | ✓ (bila punya izin) | ✓ |
| Belum dipublikasikan | ✗ | ✓ (bila punya izin) | ✗ |
| Tanpa login | ✓ dataset publik | ✗ | — |

CSW GeoNode tidak mengenali login username/password, sehingga record dataset yang belum dipublikasikan tidak
terbaca plugin. Untuk dataset seperti itu:

1. login GeoNode di browser, buka dataset, **Download › ISO Metadata**;
2. buka berkasnya dengan **Buka XML Metadata…** di GeoMDB (berkas itu sekaligus cadangan);
3. kirim dengan **☁ Kirim ke GeoNode…** dan pilih datasetnya (sesi 16), atau unggah lewat web ([sesi 14](14-unggah-lewat-web-geonode.md)).

## Versi GeoNode yang didukung

| Versi | Ambil | Perbarui dari QGIS | Mode preserve |
|---|---|---|---|
| GeoNode 5.x, 4.4 | ✓ | ✓ | diatur plugin (server harus sudah ditambal) |
| GeoNode 4.2.3 – 4.3 | ✓ | ✓ | hanya lewat Django admin (server harus sudah ditambal) |
| GeoNode 4.0 – 4.2.2 | ✓ | ✗ (belum ada API unggah XML) | — |

## Kondisi khusus

| Kondisi / pesan | Penyebab | Solusi |
|---|---|---|
| `Username atau password GeoNode salah` | Password salah atau sudah diganti | **Login username/password…** lagi dengan password baru; hapus konfigurasi lama lewat ikon hapus di samping pilihan autentikasi |
| `Konfigurasi autentikasi «…» memakai metode OAuth2…` | Konfigurasi login OAuth2 dari GeoMDB versi lama | Buat login baru dengan **Login username/password…**. GeoMDB 1.1.0 hanya mendukung username/password |
| `Konfigurasi autentikasi «…» tidak terbaca` | Master password QGIS dibatalkan, atau konfigurasinya dihapus | Ulangi dan isi master password, atau buat login baru |
| `Dataset ini belum dipublikasikan…` saat **Ambil** | Lihat tabel di atas | Unduh XML lewat browser lalu **Buka XML Metadata…** |
| Permintaan *dihadang cek bot* (Cloudflare) | Server memasang cek bot/WAF yang menolak aplikasi selain browser | Minta pengelola server mengecualikan path `/api/`, `/catalogue/csw`, dan `/geoserver/` dari cek bot, atau mengizinkan jaringan instansi. Pindah jaringan tidak bisa diandalkan. Sementara itu pakai alur web ([sesi 14](14-unggah-lewat-web-geonode.md)) |
| `Versi GeoNode tidak dapat dideteksi` | URL salah, server tidak menjawab, atau API tertutup | Periksa URL (tanpa `/catalogue/…` di belakang); pilih versi manual |
| Ganti akun | — | Pilih konfigurasi login lain. Daftar dikosongkan dan GeoMDB otomatis masuk ulang dengan akun baru |
| Kantor memakai proxy | — | GeoMDB mengikuti pengaturan jaringan QGIS (**Settings › Options › Network**) |

**Lanjut ke:** [Sesi 16 – Kirim ke GeoNode](16-kirim-ke-geonode.md)
