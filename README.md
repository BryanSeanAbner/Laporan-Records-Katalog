# Laporan Records Katalog Nusantara TV

Aplikasi web ini merupakan project internship yang dilakukan di Nusantara TV. Web ini bertujuan untuk mengelola dan melaporkan records katalog dari Nusantara TV.

## Fitur

- Login otomatis ke sistem Nusantara TV
- Filter data berdasarkan rentang tanggal
- Kategorisasi program otomatis
- Export laporan ke Excel
- Preview data per bulan
- Tampilan yang responsif dan mudah digunakan

## Persyaratan Sistem

- Python 3.8 atau lebih baru
- Koneksi ke jaringan lokal Nusantara TV
- Akses ke API Nusantara TV

## Penggunaan

1. Pastikan terhubung ke jaringan lokal Nusantara TV
2. Jalankan aplikasi:
```bash
streamlit run ui.py
```
3. Buka browser dan akses `http://localhost:8501`
4. Login menggunakan kredensial Nusantara TV
5. Pilih rentang tanggal untuk laporan
6. Klik "Generate Laporan" untuk memproses data
7. Download laporan Excel atau lihat preview per bulan

## Struktur Proyek

```
laporan-katalog/
├── ui.py              # File utama aplikasi Streamlit
├── script.py          # Modul utilitas dan fungsi helper
├── requirements.txt   # Daftar dependensi
└── README.md         # Dokumentasi proyek
```

## Made by
Bryan Sean Abner - Anak Magang Nusantara TV 2025
