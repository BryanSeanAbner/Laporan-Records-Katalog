import requests
import pandas as pd
import json
import datetime
import locale # Untuk nama bulan dalam Bahasa Indonesia

# Set locale ke Indonesia untuk mendapatkan nama bulan yang benar
# Ini mungkin perlu disesuaikan tergantung konfigurasi sistem operasi Anda
try:
    locale.setlocale(locale.LC_TIME, 'id_ID.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'Indonesian_Indonesia')
    except locale.Error:
        print("Peringatan: Tidak dapat mengatur locale ke Indonesia. Nama bulan mungkin dalam Bahasa Inggris.")
        # Default ke English jika locale Indonesia tidak tersedia
        locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')


# --- Konfigurasi yang Perlu Anda Ganti ---
BASE_URL = "https://192.168.16.111/service"

# Ganti string ini dengan nilai SESSION_ID yang valid dari cookie di Developer Tools Anda
# CARA MENDAPATKANNYA: Buka Developer Tools (F12) di browser -> Tab Network -> Klik permintaan API -> Tab Headers -> Request Headers -> Cari Cookie -> Salin nilai setelah session_id=
SESSION_ID = "7bf0b511-b409-4cd3-af64-8d259fa71c1e" # <--- Session ID Dapat Berubah !

# Ganti string ini dengan URL endpoint yang memberikan daftar SEMUA katalog di halaman utama
# CARA MENDAPATKANNYA: Buka halaman utama "Catalogs" -> Developer Tools (F12) -> Tab Network -> Refresh halaman (F5) -> Cari permintaan yang responsnya berisi daftar semua katalog -> Salin Request URL
# URL ini mungkin terlihat seperti: "https://192.168.16.111/service/catalogs" atau "https://192.168.16.111/dcat/catalogs"
URL_ENDPOINT_DAFTAR_KATALOG_UTAMA = "https://192.168.16.111/service/assets?page=1&view_type=list&sort_by=added_datetime&sort_order=-1&browse=true&catalog_id=650ad45f9f8784ac438fa212" # <--- GANTI INI!


# ID katalog utama (root catalog) - Mungkin diperlukan untuk header Referer
# Berdasarkan respons catalog-structure sebelumnya, ini adalah ID untuk "CATALOG"
# Jika struktur katalog Anda berbeda, sesuaikan ID ini. Jika tidak yakin, bisa coba ID dari salah satu katalog yang muncul di daftar utama.
MAIN_CATALOG_ID_FOR_REFERER = "650ad45f9f8784ac438fa212" # <--- PERIKSA/GANTI INI JIKA PERLU, Atau sesuaikan header Referer jika tidak memerlukannya.


OUTPUT_EXCEL_FILE = "Laporan_Records_Katalog_Harian.xlsx"
# --- ANDA PERLU MENENTUKAN INI ---
# Nama KUNCI JSON untuk field metadata TANGGAL di dalam setiap objek asset
# CARA MENDAPATKANNYA: Buka Developer Tools -> Tab Network -> Klik request yang ambil asset list (URL service/assets?catalog_id=...)
# -> Tab Response -> Periksa struktur objek di dalam array "assets" -> Cari kunci yang berisi tanggal
NAMA_KUNCI_METADATA_TANGGAL = ["asset_properties", "DATE"] # <--- SESUAIKAN INI! Ini contoh jika tanggal ada di asset_properties -> DATE


# --- Konfigurasi Filter Tanggal ---
# Set tanggal filter (dalam objek date) untuk membandingkan metadata

# Contoh: untuk tanggal HARI INI
TANGGAL_FILTER_DATE_OBJ = datetime.date.today() # <--- Gunakan format ini jika ingin menspesifikasikan tanggal tertentu datetime.date(YYYY, MM, DD)
# Atau gunakan datetime.date.today() untuk tanggal hari ini

NAMA_KUNCI_METADATA_TANGGAL = ["created_datetime"]
# Format string tanggal yang ada di metadata asset.
# Anda perlu memeriksa format string tanggal di respons API (nilai dari NAMA_KUNCI_METADATA_TANGGAL)
FORMAT_STRING_TANGGAL_METADATA = "%Y-%m-%dT%H:%M:%S" # <--- SESUAIKAN INI!


# Format string tanggal untuk membandingkan NAMA KATALOG
# Sesuaikan agar sesuai persis dengan format tanggal di nama katalog Anda (misal "26 MEI 2025")
# Gunakan strftime untuk format yang fleksibel
def format_date_for_catalog_name_filter(date_obj):
    # Dapatkan nama bulan dalam bahasa Indonesia
    nama_bulan = date_obj.strftime('%B').upper() # Nama bulan lengkap, kapital

    # Dapatkan hari tanpa leading zero
    hari = date_obj.day

    # Dapatkan tahun
    tahun = date_obj.year

    # Sesuaikan format string ini
    return f"{hari} {nama_bulan} {tahun}" # Output contoh: "26 MEI 2025"


# ------------------------------------------

# NONAKTIFKAN VERIFIKASI SSL (HATI-HATI!)
requests.packages.urllib3.disable_warnings()


def get_all_main_catalogs(url_endpoint, headers, cookies): # Tambahkan headers, cookies sebagai parameter
    """Mengambil daftar semua katalog utama dari endpoint yang ditentukan."""
    print(f"Mengambil daftar semua katalog dari: {url_endpoint}")
    try:
        # Menggunakan verify=False karena masalah sertifikat SSL yang umum di lingkungan internal
        response = requests.get(url_endpoint, headers=headers, cookies=cookies, verify=False) # Gunakan parameter headers, cookies
        response.raise_for_status() # Akan raise HTTPError untuk status kode error (4xx atau 5xx)
        data = response.json()

        # --- ANDA SUDAH MENYESUAIKAN BAGIAN INI SEBELUMNYA ---
        # Sesuaikan cara mengekstrak daftar katalog dari 'data' respons endpoint daftar utama
        # Berdasarkan output sebelumnya, daftarnya ada di bawah kunci "assets"
        catalogs_list_raw = []
        if isinstance(data, dict) and "assets" in data and isinstance(data.get("assets"), list):
            catalogs_list_raw = data.get("assets", [])
        elif isinstance(data, list):
            catalogs_list_raw = data
        # Tambahkan logika ekstraksi lain jika diperlukan


        # Filter items untuk memastikan hanya objek katalog yang valid
        filtered_catalogs = []
        for item in catalogs_list_raw:
             if isinstance(item, dict):
                  item_id = item.get("_id")
                  # Coba 'catalog_name' atau 'file_name' atau kunci lain yang menyimpan nama katalog
                  item_name = item.get("catalog_name") or item.get("file_name")
                  item_type = item.get("asset_type") # Cek tipe aset

                  if item_id and item_name and item_type == "catalog":
                       filtered_catalogs.append({
                            "_id": item_id,
                            "catalog_name": item_name
                       })
                  # else: Lewati item yang bukan katalog atau tidak lengkap


        if not filtered_catalogs:
             print("Peringatan: Daftar katalog kosong atau tidak dapat diekstrak dari respons setelah filtering.")
             # print("Respons mentah (sebagian):", json.dumps(data, indent=2)[:500] + "...")

        return filtered_catalogs

    except requests.exceptions.RequestException as e:
        print(f"Error saat mengambil daftar semua katalog utama: {e}")
        return None
    except json.JSONDecodeError:
        print("Error: Respons API daftar katalog bukan JSON yang valid.")
        return None


def get_metadata_value(item, keys):
    """Mengekstrak nilai dari nested dictionary/object menggunakan list kunci."""
    value = item
    try:
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None # Tidak bisa masuk lebih dalam jika bukan dictionary
        return value
    except Exception:
        return None

def get_total_assets_from_metadata(catalog_id, start_date_obj, end_date_obj, headers, cookies): # Tambahkan start_date_obj dan end_date_obj sebagai parameter
    """Mengambil semua aset dalam katalog dan menghitung yang sesuai dengan rentang tanggal filter metadata.""" # Perbarui deskripsi docstring
    url = f"{BASE_URL}/assets"
    params = {
        "catalog_id": catalog_id,
        "page": 1, # Mulai dari halaman pertama
        "view_type": "list", # Penting untuk mendapatkan daftar aset
        "sort_by": "added_datetime", # Opsional, bisa disesuaikan
        "sort_order": -1, # Opsional
        "browse": "true", # Opsional
        "size": 100 # Ukuran halaman, sesuaikan jika API mendukung
    }
    all_assets_in_catalog = []
    total_expected_assets = None # Total dari API metadata

    print(f"  - Mengambil aset untuk katalog ID {catalog_id} (untuk cek metadata dalam rentang {start_date_obj} - {end_date_obj})...") # Perbarui pesan print

    while True: # Loop untuk pagination
        try:
            # Menggunakan verify=False karena masalah sertifikat SSL
            response = requests.get(url, headers=headers, cookies=cookies, params=params, verify=False) # Gunakan parameter headers, cookies
            response.raise_for_status()
            data = response.json()

            # --- ANDA PERLU MENYESUAIKAN BAGIAN INI ---
            # Ekstrak daftar aset dari respons halaman saat ini.
            # Berdasarkan respons sebelumnya, daftar aset ada di kunci "assets"
            current_page_assets = data.get("assets", [])
            if not current_page_assets:
                 # Jika tidak ada aset di halaman ini, atau kunci 'assets' tidak ditemukan
                 # print(f"    - Tidak ada aset di halaman {params['page']} atau struktur respons aset tidak dikenali.")
                 # Cek apakah ini halaman terakhir berdasarkan total_assets
                 if total_expected_assets is not None and len(all_assets_in_catalog) >= total_expected_assets:
                      break # Sudah mengambil semua yang diharapkan
                 elif params['page'] == 1 and (data.get("total_assets") is None or data.get("total_assets") == 0):
                      break # Halaman pertama kosong
                 else:
                      # Mungkin ada masalah pagination atau error, cetak peringatan dan keluar
                      print(f"    - Peringatan: Tidak ada aset di halaman {params['page']} atau struktur respons. Total diambil: {len(all_assets_in_catalog)}. Total diharapkan: {total_expected_assets}.")
                      break # Keluar untuk menghindari loop tak terbatas

            all_assets_in_catalog.extend(current_page_assets)

            # Dapatkan informasi pagination dari respons
            total_expected_assets_from_metadata = data.get("total_assets")
            assets_per_page = data.get("assets_per_page", params.get("size", len(current_page_assets)))
            # page_count = data.get("page_count") # Bisa digunakan jika ada

            if total_expected_assets is None and total_expected_assets_from_metadata is not None:
                 total_expected_assets = total_expected_assets_from_metadata # Update total yang diharapkan dari halaman pertama

            # Cek apakah ada halaman berikutnya
            if total_expected_assets is None:
                 # Jika total_assets tidak ada, berasumsi kita harus ambil sampai halaman kosong
                 print("    - Peringatan: Kunci 'total_assets' tidak ditemukan. Melanjutkan pagination sampai halaman kosong.")
                 # Logic break di awal loop akan menangani ini jika current_page_assets kosong
            elif len(all_assets_in_catalog) >= total_expected_assets:
                break # Selesai mengambil semua halaman berdasarkan total_assets
            # else: Lanjut ke halaman berikutnya


            # Siapkan parameter untuk halaman berikutnya
            params['page'] += 1

        except requests.exceptions.RequestException as e:
            print(f"Error saat mengambil aset halaman {params['page']} untuk katalog ID {catalog_id}: {e}")
            break # Keluar dari loop pagination jika terjadi error
        except json.JSONDecodeError:
            print(f"Error: Respons API aset halaman {params['page']} untuk katalog ID {catalog_id} bukan JSON yang valid.")
            break

    # Hitung aset yang sesuai dengan rentang tanggal filter metadata
    count = 0
    # print(f"  - Memfilter {len(all_assets_in_catalog)} aset berdasarkan rentang tanggal metadata {start_date_obj} - {end_date_obj}...") # Perbarui pesan print
    for asset in all_assets_in_catalog:
        # Ambil nilai metadata tanggal menggunakan fungsi pembantu
        date_value_raw = get_metadata_value(asset, NAMA_KUNCI_METADATA_TANGGAL)

        if date_value_raw:
            try:
                # Parse string tanggal dari metadata asset
                asset_date_obj = datetime.datetime.strptime(str(date_value_raw), FORMAT_STRING_TANGGAL_METADATA).date()

                # Bandingkan apakah tanggal aset berada di antara start_date_obj dan end_date_obj (inklusif)
                if start_date_obj <= asset_date_obj <= end_date_obj: # Perbarui logika perbandingan
                    count += 1
            except (ValueError, TypeError) as e:
                # Abaikan asset jika format tanggalnya tidak valid
                # print(f"    - Peringatan: Gagal memproses tanggal metadata '{date_value_raw}' untuk asset: {asset.get('_id')}. Error: {e}")
                pass # Lewati asset dengan tanggal tidak valid

    # print(f"  - Total aset yang cocok dengan rentang tanggal metadata {start_date_obj} - {end_date_obj}: {count}") # Perbarui pesan print
    return count

def get_catalog_total_assets(catalog_id, headers, cookies): # Tambahkan headers, cookies sebagai parameter
    """Mengambil nilai total_assets langsung dari metadata katalog (endpoint /assets)."""
    # Menggunakan endpoint yang mengandung total_assets di respons
    url = f"{BASE_URL}/assets"
    params = {
        "catalog_id": catalog_id,
        # Parameter lain yang mungkin diperlukan server untuk mengembalikan metadata total
        "page": 1,
        "view_type": "list",
        "browse": "true"
        # Tidak perlu sort_by/sort_order/size jika hanya perlu metadata total
    }
    # print(f"  - Mengambil total_assets untuk katalog ID {catalog_id} (dari metadata)...")
    try:
        response = requests.get(url, headers=headers, cookies=cookies, params=params, verify=False) # Gunakan parameter headers, cookies
        response.raise_for_status()
        data = response.json()

        # Mencari 'total_assets' di struktur respons
        total_assets = data.get("total_assets")

        if total_assets is not None:
            # print(f"  - Total aset dari metadata: {total_assets}")
            return total_assets
        else:
             print(f"  - Peringatan: Kunci 'total_assets' tidak ditemukan dalam respons metadata untuk katalog ID {catalog_id}.")
             # print("Respons metadata (sebagian):", json.dumps(data, indent=2)[:500] + "...")
             return "Tidak diketahui"

    except requests.exceptions.RequestException as e:
        print(f"Error saat mengambil total_assets metadata untuk katalog ID {catalog_id}: {e}")
        return "Error API Metadata"
    except json.JSONDecodeError:
        print(f"Error: Respons API metadata untuk katalog ID {catalog_id} bukan JSON yang valid.")
        return "Error Data Metadata"