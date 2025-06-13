import requests
import pandas as pd
import json
import datetime
# import locale # Tidak perlu impor locale jika tidak setlocale
from urllib.parse import urlparse, parse_qs

# --- Konfigurasi yang Perlu Anda Ganti ---
BASE_URL = "https://192.168.16.111/service" # Ini sekarang dideteksi otomatis di app.py

# Ganti string ini dengan nilai SESSION_ID yang valid dari cookie di Developer Tools Anda
# CARA MENDAPATKANNYA: Buka Developer Tools (F12) di browser -> Tab Network -> Klik permintaan API -> Tab Headers -> Request Headers -> Cari Cookie -> Salin nilai setelah session_id=
SESSION_ID = "7bf0b511-b409-4cd3-af64-8d259fa71c1e"  # <--- Session ID Dapat Berubah !

# Path endpoint untuk mendapatkan daftar SEMUA katalog di halaman utama (BUKAN URL LENGKAP DENGAN PAGE)
# URL ini mungkin terlihat seperti: "/service/catalogs" atau "/dcat/catalogs"
# Berdasarkan URL sebelumnya "https://192.168.16.111/service/assets?page=1...", path-nya adalah "/assets"
CATALOG_LIST_ENDPOINT_PATH = "/assets" # <--- GANTI INI DENGAN PATH YANG BENAR!


# Parameter query default untuk request katalog (misal: view_type, sort_by, sort_order, browse, catalog_id)
# Ambil dari URL_ENDPOINT_DAFTAR_KATALOG_UTAMA sebelumnya, tapi buang parameter 'page'
DEFAULT_CATALOG_QUERY_PARAMS = {
    "view_type": "list", # Penting untuk mendapatkan daftar aset
    "sort_by": "added_datetime", # Opsional, bisa disesuaikan
    "sort_order": -1, # Opsional
    "browse": "true", # Opsional
    "catalog_id": "650ad45f9f8784ac438fa212", # GANTI DENGAN ID KATALOG UTAMA ANDA
    "size": 50 # Ukuran halaman, sesuaikan jika API mendukung, 50 adalah default di gambar
}


# ID katalog utama (root catalog) - Mungkin diperlukan untuk header Referer
# Berdasarkan respons catalog-structure sebelumnya, ini adalah ID untuk "CATALOG"
# Jika struktur katalog Anda berbeda, sesuaikan ID ini. Jika tidak yakin, bisa coba ID dari salah satu katalog yang muncul di daftar utama.
MAIN_CATALOG_ID_FOR_REFERER = "650ad45f9f8784ac438fa212" # <--- PERIKSA/GANTI INI JIKA PERLU, Atau sesuaikan header Referer jika tidak memerlukannya.


OUTPUT_EXCEL_FILE = "Laporan_Records_Katalog_Harian.xlsx"
# --- ANDA PERLU MENENTUKAN INI ---
# Nama KUNCI JSON untuk field metadata TANGGAL yang ingin ditampilkan di laporan.
# Berdasarkan JSON sample, "asset_created_datetime" adalah tanggal pembuatan untuk objek type "catalog".
# Gunakan path ini untuk mengambil nilai dari objek katalog lengkap yang dikembalikan oleh get_all_main_catalogs.
NAMA_KUNCI_METADATA_TANGGAL = ["asset_created_datetime"]


# --- Konfigurasi Filter Tanggal ---
# Set tanggal filter (dalam objek date) untuk membandingkan metadata

# Contoh: untuk tanggal HARI INI
TANGGAL_FILTER_OBJ = datetime.date.today() # <--- Gunakan format ini jika ingin menspesifikasikan tanggal tertentu datetime.date(YYYY, MM, DD)
# Atau gunakan datetime.date.today() untuk tanggal hari ini

# Format string tanggal yang ada di metadata asset.
# Berdasarkan JSON sample, formatnya adalah "YYYY-MM-DDTHH:MM:SS"
FORMAT_STRING_TANGGAL_METADATA = "%Y-%m-%dT%H:%M:%S" # <--- SESUAIKAN INI!


# Format string tanggal untuk membandingkan NAMA KATALOG
# Sesuaikan agar sesuai persis dengan format tanggal di nama katalog Anda (misal "26 MEI 2025")
# Gunakan strftime untuk format yang fleksibel
def format_date_for_catalog_name_filter(date_obj):
    # Pemetaan nama bulan dari Bahasa Inggris ke Bahasa Indonesia
    nama_bulan_indonesia = {
        'January': 'JANUARI',
        'February': 'FEBRUARI',
        'March': 'MARET',
        'April': 'APRIL',
        'May': 'MEI',
        'June': 'JUNI',
        'July': 'JULI',
        'August': 'AGUSTUS',
        'September': 'SEPTEMBER',
        'October': 'OKTOBER',
        'November': 'NOVEMBER',
        'December': 'DESEMBER'
    }

    # Dapatkan nama bulan dalam bahasa Inggris, lalu terjemahkan ke Bahasa Indonesia
    nama_bulan_inggris = date_obj.strftime('%B')
    nama_bulan = nama_bulan_indonesia.get(nama_bulan_inggris, nama_bulan_inggris.upper()) # Default ke kapital jika tidak ada di map

    # Dapatkan hari tanpa leading zero
    hari = date_obj.day

    # Dapatkan tahun
    tahun = date_obj.year

    # Sesuaikan format string ini
    return f"{hari} {nama_bulan} {tahun}"


# ------------------------------------------

# NONAKTIFKAN VERIFIKASI SSL (HATI-HATI!)
requests.packages.urllib3.disable_warnings()


def get_all_main_catalogs(base_url, endpoint_path, query_params, headers, cookies): # Ubah parameter
    """Mengambil daftar semua katalog utama dari endpoint yang ditentukan, mendukung pagination.
    Mengembalikan daftar objek katalog lengkap jika memenuhi kriteria dasar (ID, nama, tipe 'catalog').
    """ # Perbarui docstring

    all_catalogs = []
    current_page = 1
    total_pages = 1 # Mulai dengan 1, akan diupdate setelah request pertama

    print(f"Mengambil daftar semua katalog dari: {base_url}{endpoint_path}")

    while current_page <= total_pages:
        url = f"{base_url}{endpoint_path}"
        params = query_params.copy() # Salin parameter agar tidak mengubah yang asli
        params["page"] = current_page # Set nomor halaman

        print(f"  - Mengambil halaman {current_page}...")

        try:
            response = requests.get(url, headers=headers, cookies=cookies, params=params, verify=False)
            response.raise_for_status()
            data = response.json()

            # Ekstrak daftar aset dari respons halaman saat ini.
            # Berdasarkan respons sebelumnya, daftar aset ada di kunci "assets"
            current_page_assets = data.get("assets", [])

            if current_page == 1:
                # Ambil total_pages dari respons pertama
                total_pages = data.get("page_count", 1) # Default ke 1 jika tidak ada page_count
                print(f"  - Total halaman ditemukan: {total_pages}")

            # Filter katalog yang hanya bertipe 'catalog'
            filtered_current_page_catalogs = []
            for item in current_page_assets:
                 if isinstance(item, dict):
                      item_id = item.get("_id")
                      item_name = item.get("catalog_name") or item.get("file_name")
                      item_type = item.get("asset_type") # Cek tipe aset

                      # Jika memenuhi kriteria dasar, tambahkan objek lengkap ke daftar
                      if item_id and item_name and item_type == "catalog":
                           filtered_current_page_catalogs.append(item) # <<<--- Mengembalikan objek item lengkap

            all_catalogs.extend(filtered_current_page_catalogs)

            # Lanjut ke halaman berikutnya
            current_page += 1

        except requests.exceptions.RequestException as e:
            print(f"Error saat mengambil daftar katalog halaman {current_page}: {e}")
            return None # Berhenti dan kembalikan None jika ada error
        except json.JSONDecodeError:
            print(f"Error: Respons API halaman {current_page} bukan JSON yang valid.")
            return None # Berhenti dan kembalikan None jika respons bukan JSON
        except Exception as e:
            print(f"Terjadi kesalahan tak terduga saat mengambil halaman {current_page}: {e}")
            return None # Berhenti dan kembalikan None untuk error lainnya

    if not all_catalogs:
         print("Peringatan: Daftar katalog kosong atau tidak dapat diekstrak dari respons setelah filtering.")

    return all_catalogs


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
        "size": 50# Ukuran halaman, sesuaikan jika API mendukung
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

def get_catalog_total_assets(catalog_id, headers, cookies):
    """Mengambil nilai total_assets langsung dari metadata katalog (endpoint /assets)."""
    url = f"{BASE_URL}/assets"
    params = {
        "catalog_id": catalog_id,
        "page": 1,
        "view_type": "list",
        "browse": "true"
    }
    try:
        response = requests.get(url, headers=headers, cookies=cookies, params=params, verify=False)
        response.raise_for_status()
        data = response.json()

        # Mencari 'total_assets' di struktur respons
        return data.get("total_assets")

    except requests.exceptions.RequestException as e:
        print(f"Error saat mengambil total_assets untuk katalog ID {catalog_id}: {e}")
        return None
    except json.JSONDecodeError:
        print("Error: Respons API total_assets bukan JSON yang valid.")
        return None
    except Exception as e:
        print(f"Terjadi kesalahan tak terduga saat mengambil total_assets untuk katalog ID {catalog_id}: {e}")
        return None

def get_catalog_files(catalog_id, headers, cookies):
    """Mengambil daftar file dari katalog."""
    url = f"{BASE_URL}/assets"
    params = {
        "catalog_id": catalog_id,
        "page": 1,
        "view_type": "list",
        "browse": "true",
        "size": 50
    }
    all_files = []
    
    try:
        while True:
            response = requests.get(url, headers=headers, cookies=cookies, params=params, verify=False)
            response.raise_for_status()
            data = response.json()
            
            current_page_assets = data.get("assets", [])
            if not current_page_assets:
                break
                
            # Filter hanya file yang memiliki file_info
            for asset in current_page_assets:
                if asset.get("asset_type") == "file" and asset.get("file_info"):
                    for file_info in asset.get("file_info", []):
                        if file_info.get("file_name"):
                            all_files.append({
                                "file_name": file_info.get("file_name"),
                                "file_path": file_info.get("file_path", ""),
                                "asset_id": asset.get("_id", ""),
                                "asset_created_datetime": asset.get("asset_created_datetime", "")
                            })
            
            # Cek apakah ada halaman berikutnya
            if len(current_page_assets) < params["size"]:
                break
                
            params["page"] += 1
            
        return all_files
        
    except requests.exceptions.RequestException as e:
        print(f"Error saat mengambil file untuk katalog ID {catalog_id}: {e}")
        return []
    except json.JSONDecodeError:
        print("Error: Respons API bukan JSON yang valid.")
        return []
    except Exception as e:
        print(f"Terjadi kesalahan tak terduga saat mengambil file untuk katalog ID {catalog_id}: {e}")
        return []

# Anda bisa menambahkan fungsi lain di sini jika diperlukan