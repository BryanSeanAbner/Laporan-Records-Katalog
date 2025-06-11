# Laporan Records Katalog Nusantara TV

Aplikasi web untuk mengelola dan melaporkan records katalog dari Nusantara TV.

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

## Instalasi

1. Clone repository ini:
```bash
git clone https://github.com/username/laporan-katalog.git
cd laporan-katalog
```

2. Buat virtual environment dan aktifkan:
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. Install dependensi:
```bash
pip install -r requirements.txt
```

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

## Kontribusi

1. Fork repository
2. Buat branch fitur (`git checkout -b fitur-baru`)
3. Commit perubahan (`git commit -m 'Menambahkan fitur baru'`)
4. Push ke branch (`git push origin fitur-baru`)
5. Buat Pull Request

## Made by

Bryan Sean Abner - Anak Magang Nusantara TV 2025
