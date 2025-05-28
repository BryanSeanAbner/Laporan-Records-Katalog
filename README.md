# Proyek Katalog Records

Proyek ini adalah sebuah script Python untuk mengambil dan menganalisis data katalog dari API internal.

## Fitur

- Mengambil data katalog dari API internal
- Filter data berdasarkan tanggal
- Ekspor data ke format Excel
- Mendukung pagination untuk data dalam jumlah besar

## Persyaratan

- Python 3.8 atau lebih baru
- Dependensi yang tercantum dalam `requirements.txt`

## Instalasi

1. Clone repository ini:
```bash
git clone [URL_REPOSITORY]
```

2. Buat virtual environment (opsional tapi direkomendasikan):
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Install dependensi:
```bash
pip install -r requirements.txt
```

## Penggunaan

1. Sesuaikan konfigurasi di `script.py`:
   - `SESSION_ID`: ID sesi dari cookie browser
   - `BASE_URL`: URL dasar API
   - `URL_ENDPOINT_DAFTAR_KATALOG_UTAMA`: Endpoint untuk daftar katalog
   - Konfigurasi lainnya sesuai kebutuhan

2. Jalankan script:
```bash
python script.py
```

## Catatan Penting

- Pastikan Anda memiliki akses ke API internal
- Session ID perlu diperbarui secara berkala
- Gunakan dengan bijak sesuai kebijakan penggunaan API

## Lisensi

[Masukkan informasi lisensi di sini] 