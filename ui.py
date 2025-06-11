import streamlit as st
import requests
import pandas as pd
import json
import datetime
from io import BytesIO
from urllib.parse import urlparse
from script import (
    get_all_main_catalogs,
    get_catalog_total_assets,
    get_metadata_value,
    NAMA_KUNCI_METADATA_TANGGAL,
    FORMAT_STRING_TANGGAL_METADATA,
    CATALOG_LIST_ENDPOINT_PATH,
    DEFAULT_CATALOG_QUERY_PARAMS,
)
import re

# Konfigurasi halaman Streamlit
st.set_page_config(
    page_title="Laporan Records Katalog",
    page_icon="📊",
    layout="wide"
)

# Inisialisasi session state
if 'main_catalog_id' not in st.session_state:
    st.session_state.main_catalog_id = DEFAULT_CATALOG_QUERY_PARAMS.get('catalog_id', None)

# Inisialisasi st.session_state.catalog_id karena muncul dalam error
if 'catalog_id' not in st.session_state:
    st.session_state.catalog_id = DEFAULT_CATALOG_QUERY_PARAMS.get('catalog_id', None)

# Inisialisasi variabel session state untuk menyimpan data laporan
if 'report_generated' not in st.session_state:
    st.session_state.report_generated = False
if 'categorized_report_data' not in st.session_state:
    st.session_state.categorized_report_data = {}
if 'all_dates_in_filtered_data' not in st.session_state:
    st.session_state.all_dates_in_filtered_data = []
if 'monthly_dates' not in st.session_state:
    st.session_state.monthly_dates = {}
if 'total_catalogs_found' not in st.session_state:
    st.session_state.total_catalogs_found = 0
if 'start_date_input' not in st.session_state:
    st.session_state.start_date_input = datetime.date.today()
if 'end_date_input' not in st.session_state:
    st.session_state.end_date_input = datetime.date.today()

# Daftar kategori program spesifik (case-insensitive) dengan variasi umum
# Format: (Nama Standar, [daftar_variasi_yang_dinormalisasi])
SPECIFIC_PROGRAM_CATEGORIES_MAPPING = [
    ("NTV Morning", ["ntv morning", "ntv mornings"]),
    ("NTV Today", ["ntv today"]),
    ("NTV Crime", ["ntv crime"]),
    ("NTV Prime", ["ntv prime"]),
    ("NTV Sports", ["ntv sports", "ntv sport"]),
    ("NTV Toplines", ["ntv toplines", "ntv topline"]),
    ("NTV Tonight", ["ntv tonight"]),
    ("NTV Newsflash", ["ntv newsflash", "news flash", "newsflash"]),
]

# All month names joined by '|' for regex. Split for line length.
MONTH_REGEX_OPTIONS = (
    'JANUARI|JAN|FEBRUARI|FEB|MARET|MAR|APRIL|APR|MEI|MAY|'
    'JUNI|JUN|JULI|JUL|AGUSTUS|AGS|AUG|SEPTEMBER|SEP|'
    'OKTOBER|OKT|OCT|NOVEMBER|NOV|DESEMBER|DES|DEC'
)

# Fungsi untuk menentukan kategori program
def categorize_program(catalog_name):
    if not catalog_name:
        return catalog_name

    # Normalisasi nama katalog (lowercase dan hapus spasi di awal/akhir)
    normalized_catalog_name = catalog_name.strip().lower()

    # Date part regex for flexibility: DD Month, DD, or YYYY
    date_regex_flexible = (
        r"(?:\d{1,2}\s*(?:%s)|\d{1,2}|\d{4})" % MONTH_REGEX_OPTIONS
    )

    # Define base program keywords for non-NTV prefixed but date-suffixed programs
    # This will be used for Rule 1 and implicitly Rule 2
    base_program_keywords = {
        "NTV Morning": r"morning[s]?",
        "NTV Today": r"today['s]?",
        "NTV Crime": r"crime[s]?",
        "NTV Prime": r"prime(?:\s*time)?",
        "NTV Sports": r"sport[s]?",
        "NTV Toplines": r"topline[s]?",
        "NTV Tonight": r"tonight['s]?",
        "NTV Newsflash": r"(?:news\s*flash|newsflash|news-flash)"
    }

    # Define strict NTV patterns (require "ntv" or "n.t.v." at the beginning)
    # This handles Rule 3: If it has NTV prefix + Program + Date
    strict_ntv_patterns = {
        "NTV Morning": r"^(?:ntv|n\.t\.v)\s*morning[s]?",
        "NTV Today": r"^(?:ntv|n\.t\.v)\s*today['s]?",
        "NTV Crime": r"^(?:ntv|n\.t\.v)\s*crime[s]?",
        "NTV Prime": r"^(?:ntv|n\.t\.v)\s*prime(?:\s*time)?",
        "NTV Sports": r"^(?:ntv|n\.t\.v)\s*sport[s]?",
        "NTV Toplines": r"^(?:ntv|n\.t\.v)\s*topline[s]?",
        "NTV Tonight": r"^(?:ntv|n\.t\.v)\s*tonight['s]?",
        "NTV Newsflash": r"^(?:ntv|n\.t\.v)\s*(?:news\s*flash|newsflash|news-flash)"
    }

    # First, try to match strict NTV patterns (Rule 3)
    for program_name, pattern in strict_ntv_patterns.items():
        if re.match(pattern, normalized_catalog_name, re.IGNORECASE):
            return program_name

    # Rule 4: If only program keyword (e.g., "Newsflash", "Toplines", "Today")
    for ntv_category, base_keyword_regex in base_program_keywords.items():
        # Check for exact match of the base keyword
        if re.fullmatch(base_keyword_regex, normalized_catalog_name, re.IGNORECASE):
            return ntv_category

    # Then, iterate through base keywords to apply Rule 1 & 2
    for ntv_category, base_keyword_regex in base_program_keywords.items():
        # Pattern to search for PROGRAM_NAME + DATE anywhere in the string
        general_program_date_pattern = (
            rf"\b{base_keyword_regex}\s+{date_regex_flexible}"
        )

        if re.search(general_program_date_pattern, normalized_catalog_name, re.IGNORECASE):
            # Rule 1: If it starts directly with PROGRAM_NAME + DATE (no other prefix before PROGRAM_NAME)
            # This handles: "Toplines 11", "Crime 03/02", "Today 10 Feb"
            starts_with_program_date_pattern = (
                rf"^{base_keyword_regex}\s+{date_regex_flexible}"
            )
            if re.match(starts_with_program_date_pattern, normalized_catalog_name, re.IGNORECASE):
                # If it matches Rule 1, categorize it.
                return ntv_category
            # Rule 2: If it matched general_program_date_pattern but *not* starts_with_program_date_pattern,
            # it means it has another prefix (e.g., "My Toplines 11"). In this case, we do nothing,
            # allowing it to fall through and retain its original name.

    # Jika tidak cocok dengan kategori spesifik mana pun, kembalikan nama katalog asli
    return catalog_name

# Fungsi bantu untuk mencoba mem-parsing tanggal dari nama program
def parse_date_from_name(program_name, default_year):
    if not program_name or not default_year:
        return None

    normalized_name = program_name.strip().upper()

    # Mapping nama bulan dalam Bahasa Indonesia dan Inggris (untuk jaga-jaga)
    month_map = {
        'JANUARI': 1, 'JAN': 1,
        'FEBRUARI': 2, 'FEB': 2,
        'MARET': 3, 'MAR': 3,
        'APRIL': 4, 'APR': 4,
        'MEI': 5, 'MAY': 5,
        'JUNI': 6, 'JUN': 6,
        'JULI': 7, 'JUL': 7,
        'AGUSTUS': 8, 'AGS': 8, 'AUG': 8,
        'SEPTEMBER': 9, 'SEP': 9,
        'OKTOBER': 10, 'OKT': 10, 'OCT': 10,
        'NOVEMBER': 11, 'NOV': 11,
        'DESEMBER': 12, 'DES': 12, 'DEC': 12,
    }

    # Now using the global MONTH_REGEX_OPTIONS
    month_regex_options = MONTH_REGEX_OPTIONS

    # Regex untuk mencari pola tanggal dalam nama program
    # (misal: 19 MARET, 05 FEB, 20 MEI 2025)
    # Mencari pola ANGKAspasiBULANspasi(TAHUN opsional)
    # Menangkap angka hari dan nama bulan
    # Menambahkan opsional titik setelah angka hari (misal: 5. MARET)
    pattern = (
        r'\b(\d{1,2})\.?\s+' +  # Hari (1 atau 2 digit)
        r'(' + month_regex_options + r')\s*' +  # Nama bulan
        r'(\d{4})?'  # Tahun opsional
    )
    match = re.search(pattern, normalized_name)

    if match:
        day_str = match.group(1)
        month_str = match.group(2)
        year_str = match.group(3)

        try:
            day = int(day_str)
            month = month_map.get(month_str)
            # Gunakan tahun dari nama jika ada, kalau tidak gunakan tahun default
            # Pastikan default_year adalah integer
            year = int(year_str) if year_str else int(default_year)

            if month:
                # Coba buat objek tanggal
                # Validasi hari dalam bulan
                if 1 <= day <= 31:
                    # Tambahkan try-except untuk menangani invalid day for month
                    # (misal 31 Feb)
                    try:
                        date_from_name = datetime.date(year, month, day)
                        return date_from_name
                    except ValueError:
                        # Invalid day for month, parsing failed
                        pass

        except (ValueError, TypeError):
            # Gagal parsing angka hari atau tahun
            pass

    # Tidak menemukan pola tanggal yang valid atau parsing gagal
    return None

# Fungsi untuk mendeteksi base URL berdasarkan jaringan lokal
def detect_base_url():
    return "https://192.168.16.111/service"

# Fungsi untuk mendapatkan session ID dari login
def get_session_id(base_url, username, password):
    try:
        # URL login Fusion (sesuaikan jika endpoint login berbeda)
        login_url = f"{base_url}/login"
        
        # Data login (sesuaikan struktur data jika API membutuhkan format lain)
        login_data = {
            "username": username,
            "password": password
        }
        
        # Headers untuk request
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json"
        }
        
        # Kirim request login
        response = requests.post(
            login_url,
            json=login_data,
            headers=headers,
            verify=False  # HATI-HATI: Nonaktifkan verifikasi SSL hanya di
                          # lingkungan terpercaya/internal
        )

        # Periksa status kode respons. Sesuaikan 200 jika API login
        # mengembalikan status lain untuk sukses.
        if response.status_code == 200:
            # Coba dapatkan session ID dari cookie. Sesuaikan "session_id"
            # jika nama cookie berbeda.
            cookies = response.cookies
            session_id = cookies.get("session_id")

            if session_id:
                return session_id, None
            else:
                # Jika session_id tidak ada di cookie, coba cari di body
                # respons JSON (jika API mengembalikan di sana)
                try:
                    response_json = response.json()
                    session_id_from_body = response_json.get("session_id")
                    # Sesuaikan kunci jika berbeda
                    if session_id_from_body:
                        return session_id_from_body, None
                    else:
                        return None, ("Session ID tidak ditemukan di cookie "
                                      "maupun respons.")
                except json.JSONDecodeError:
                    return None, ("Login gagal dengan status code: "
                                  f"{response.status_code}. "
                                  "Tidak dapat membaca pesan error dari respons.")

        else:
            # Coba baca pesan error dari respons JSON jika ada
            try:
                error_data = response.json()
                error_message = error_data.get("message",
                                               ("Login gagal dengan status code: "
                                                f"{response.status_code}"))
                return None, error_message
            except json.JSONDecodeError:
                return None, ("Login gagal dengan status code: "
                              f"{response.status_code}. "
                              "Tidak dapat membaca pesan error dari respons.")

    except requests.exceptions.RequestException as e:
        return None, f"Error koneksi atau request: {str(e)}"
    except Exception as e:
        return None, f"Terjadi kesalahan tak terduga: {str(e)}"

# Fungsi untuk memvalidasi URL
def is_valid_url(url):
    try:
        result = urlparse(url)
        # Memeriksa scheme (http/https) dan network location
        is_valid = all([
            result.scheme in ['http', 'https'],
            result.netloc
        ])
        return is_valid
    except Exception as e:
        # Menggunakan Exception yang lebih spesifik atau menangkapnya secara eksplisit
        print(f"Error validating URL: {e}")
        return False  # URL parsing gagal

# Inisialisasi session state jika belum ada
if 'is_logged_in' not in st.session_state:
    st.session_state.is_logged_in = False
if 'session_id' not in st.session_state:
    st.session_state.session_id = None

# Modifikasi inisialisasi base_url agar selalu coba deteksi jika belum ada atau jika user logout
if 'base_url' not in st.session_state or not st.session_state.is_logged_in:
    detected_url = detect_base_url()
    st.session_state.base_url = detected_url if detected_url else None

# Fungsi untuk mengekstrak tanggal dari metadata katalog
def extract_metadata_date(catalog: dict) -> datetime.date | None:
    date_value_raw = get_metadata_value(catalog, NAMA_KUNCI_METADATA_TANGGAL)
    print(f"DEBUG: extract_metadata_date - Raw value for 'asset_created_datetime': {date_value_raw}")
    if date_value_raw:
        try:
            # Pastikan FORMAT_STRING_TANGGAL_METADATA sesuai dengan format di metadata
            extracted_date_obj = datetime.datetime.strptime(
                str(date_value_raw), FORMAT_STRING_TANGGAL_METADATA).date()
            print(f"DEBUG: extract_metadata_date - Successfully parsed date: {extracted_date_obj}")
            return extracted_date_obj
        except (ValueError, TypeError) as e:
            print(f"DEBUG: extract_metadata_date - Failed to parse date '{date_value_raw}' with format '{FORMAT_STRING_TANGGAL_METADATA}': {e}")
            pass  # Gagal parsing metadata
    else:
        print("DEBUG: extract_metadata_date - Raw date value was None or empty.")
    return None

# Fungsi untuk membangun indeks tanggal dari daftar katalog
def build_date_index(catalogs_list: list[dict]) -> dict[datetime.date, list[dict]]:
    date_index = {}
    for catalog in catalogs_list:
        catalog_id = catalog.get("_id")
        catalog_name = get_catalog_display_name(catalog)

        if not catalog_id:
            continue

        # Ekstrak tanggal dari metadata (asset_created_datetime)
        metadata_date = extract_metadata_date(catalog)

        # --- Logika Penentuan Tanggal untuk Pengelompokan (Hanya Metadata) --- #
        date_for_indexing = metadata_date

        if date_for_indexing:
            # Tambahkan katalog ke list untuk tanggal ini di indeks
            if date_for_indexing not in date_index:
                date_index[date_for_indexing] = []
            date_index[date_for_indexing].append(catalog)
            
    return date_index

# Fungsi bantu untuk mendapatkan nama tampilan katalog yang benar
def get_catalog_display_name(catalog):
    # Coba ambil catalog_name terlebih dahulu
    catalog_name = catalog.get("catalog_name")
    if catalog_name:
        return catalog_name.strip()

    # Jika catalog_name null, coba dari catalog_path
    catalog_path = catalog.get("catalog_path")
    if isinstance(catalog_path, list) and len(catalog_path) > 0:
        # Ambil elemen terakhir dari path (biasanya ini yang paling spesifik)
        last_path_element = catalog_path[-1]
        path_value = last_path_element.get("value")
        if path_value and isinstance(path_value, str):
            # Asumsi formatnya "catalog://0/KATALOG/NAMA_KATALOG"
            # Ambil bagian setelah slash terakhir
            return path_value.split('/')[-1].strip()

    return "Nama Tidak Diketahui" # Fallback jika tidak ada yang ditemukan

# --- Tampilan Aplikasi --- #

# Mengatur tampilan sidebar secara kondisional
if st.session_state.is_logged_in:
    with st.sidebar:
        st.header("⚙️ Konfigurasi")
        st.success("✅ Sudah Berhasil Login")
        if st.button("Logout", type="secondary"):
            st.session_state.is_logged_in = False
            st.session_state.session_id = None
            st.session_state.base_url = None  # Set base_url ke None saat logout
            st.rerun()  # Me-rerun aplikasi untuk menampilkan form login
        
        st.markdown("---")
        
        # Input untuk URL endpoint katalog utama (setelah login) - Sekarang hanya untuk tampilan atau informasi
        # Nilai default diambil dari kombinasi base_url dan CATALOG_LIST_ENDPOINT_PATH
        default_url_endpoint_display = (
            f"{st.session_state.base_url}{CATALOG_LIST_ENDPOINT_PATH}" 
            if st.session_state.base_url else ""
        )

        st.text_input(
            "URL Endpoint Katalog Utama",
            value=default_url_endpoint_display,
            help="URL endpoint untuk mendapatkan daftar katalog (otomatis terdeteksi)",
            disabled=True  # Disable input karena otomatis
        )

        # Input untuk ID katalog utama (setelah login) - Masih relevan untuk header Referer
        main_catalog_id = st.text_input(
            "ID Katalog Utama",
            # Gunakan nilai default dari script.py atau dari session state jika disimpan
            value=st.session_state.get(
                'main_catalog_id', DEFAULT_CATALOG_QUERY_PARAMS.get('catalog_id')
            ),
            help="ID katalog utama untuk header Referer",
            disabled=True
        )
        # Simpan nilai main_catalog_id di session state
        st.session_state.main_catalog_id = main_catalog_id

# Konten utama: Login atau Laporan
if not st.session_state.is_logged_in:
    # --- Tampilan Halaman Login ---
    st.title("🔐 Login")
    st.markdown("---")

    # Container untuk form login
    with st.container():
        # Cek apakah base URL sudah terdeteksi
        if st.session_state.base_url:
            st.success(f"Terhubung ke jaringan lokal. Base URL: {st.session_state.base_url}")
        else:
            st.warning("Tidak terhubung ke jaringan lokal yang diinginkan. "
                       "Silakan hubungkan ke jaringan yang benar")
            st.stop()

        # Form login
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        # Tombol login
        if st.button("Login", type="primary", use_container_width=True):
            with st.spinner("Mencoba login..."):
                # Panggil fungsi login dengan base URL yang sudah terdeteksi
                session_id, error = get_session_id(
                    st.session_state.base_url, username, password)

                if session_id:
                    # Simpan data login di session state
                    st.session_state.session_id = session_id
                    st.session_state.is_logged_in = True
                    st.success("Login berhasil!")
                    st.rerun()  # Me-rerun aplikasi untuk menampilkan konten laporan
                else:
                    # Tampilkan pesan error jika login gagal
                    st.error(f"Login gagal: {error}")

else:
    # --- Tampilan Halaman Utama Setelah Login ---
    st.header("📅 Pilih Rentang Tanggal Laporan")

    # Date input untuk memilih rentang tanggal
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Tanggal Mulai",
            value=st.session_state.start_date_input,
            help="Pilih tanggal awal untuk laporan",
            key="start_date_input_widget"
        )
    with col2:
        end_date = st.date_input(
            "Tanggal Akhir",
            value=st.session_state.end_date_input,
            help="Pilih tanggal akhir untuk laporan",
            key="end_date_input_widget"
        )

    # Simpan tanggal yang baru dipilih ke session state
    st.session_state.start_date_input = start_date
    st.session_state.end_date_input = end_date

    # Deteksi jika tanggal berubah dari yang terakhir digunakan untuk generate laporan
    dates_changed = (
        start_date != st.session_state.get('last_generated_start_date') or
        end_date != st.session_state.get('last_generated_end_date')
    )

    if dates_changed:
        st.session_state.report_generated = False # Reset status jika tanggal berubah

    # Validasi tanggal (opsional tapi disarankan)
    if start_date > end_date:
        st.error("⚠️ Tanggal Mulai tidak boleh lebih besar dari Tanggal Akhir.")
    else:
        # Tombol untuk menjalankan laporan
        if st.button("📈 Generate Laporan", type="primary"):
            st.session_state.report_generated = True # Set status ke True saat tombol diklik

            with st.spinner("Memproses laporan..."):
                try:
                    # Set headers dan cookies
                    base_url_from_state = st.session_state.base_url
                    session_id_from_state = st.session_state.session_id
                    main_catalog_id_from_state = st.session_state.main_catalog_id

                    headers = {
                        "Accept": "application/json, text/plain, */*",
                        "Accept-Encoding": "gzip, deflate, br, zstd",
                        "Accept-Language": "id-ID,id;q=0.9",
                        "Connection": "keep-alive",
                        "Host": urlparse(base_url_from_state).netloc,
                        "Referer": (f"{base_url_from_state}/explorer/catalogs/"
                                    f"{main_catalog_id_from_state}")
                    }
                    cookies = {"session_id": session_id_from_state}

                    st.info(f"Mempersiapkan laporan untuk rentang tanggal: "
                            f"{start_date.strftime('%d %B %Y')} - "
                            f"{end_date.strftime('%d %B %Y')}")

                    # Dapatkan daftar katalog (menggunakan fungsi yang sudah mendukung pagination)
                    print("Parameters for get_all_main_catalogs:")
                    print(f"  base_url: {base_url_from_state}")
                    print(f"  endpoint_path: {CATALOG_LIST_ENDPOINT_PATH}")
                    print(f"  query_params: {DEFAULT_CATALOG_QUERY_PARAMS}")
                    print(f"  headers: {headers}")
                    print(f"  cookies: {cookies}")
                    catalogs_list = get_all_main_catalogs(
                        base_url=base_url_from_state,
                        endpoint_path=CATALOG_LIST_ENDPOINT_PATH,
                        query_params=DEFAULT_CATALOG_QUERY_PARAMS,
                        headers=headers,
                        cookies=cookies
                    )

                    if catalogs_list:
                        st.info("Membangun indeks tanggal dari katalog...")
                        date_index = build_date_index(catalogs_list)
                        st.info(f"Indeks dibangun dengan {len(date_index)} tanggal"
                                " unik.")

                        filtered_catalogs = []
                        delta = end_date - start_date
                        for i in range(delta.days + 1):
                            current_date = start_date + datetime.timedelta(days=i)
                            if current_date in date_index:
                                filtered_catalogs.extend(date_index[current_date])

                        total_filtered_catalogs = len(filtered_catalogs)
                        if total_filtered_catalogs > 0:
                            categorized_report_data = {}
                            progress_bar = st.progress(0)

                            for idx, catalog in enumerate(filtered_catalogs):
                                catalog_id = catalog.get("_id")
                                catalog_name = get_catalog_display_name(catalog)

                                if not catalog_id:
                                    continue

                                metadata_date = extract_metadata_date(catalog)
                                date_for_grouping = metadata_date

                                if not date_for_grouping:
                                    st.warning(f"Peringatan: Katalog '{catalog_name}' (ID: {catalog_id}) dilewati karena tanggal dari metadata tidak dapat diurai atau tidak ada. Nilai mentah: {catalog.get('asset_created_datetime')}")
                                    continue

                                program_identifier = categorize_program(
                                    catalog_name
                                )

                                progress = (idx + 1) / total_filtered_catalogs
                                progress_bar.progress(progress)

                                count_for_this_catalog = 0
                                catalog_total_assets = get_catalog_total_assets(
                                    catalog_id,
                                    headers,
                                    cookies
                                )
                                if catalog_total_assets is not None:
                                    count_for_this_catalog = catalog_total_assets
                                else:
                                    st.warning(f"Tidak dapat mengambil total aset untuk katalog '{catalog_name}' (ID: {catalog_id}). Menggunakan 0.")

                                if program_identifier not in categorized_report_data:
                                    categorized_report_data[program_identifier] = {}
                                categorized_report_data[program_identifier][date_for_grouping] = (
                                    categorized_report_data[program_identifier].get(
                                        date_for_grouping, 0) + count_for_this_catalog
                                )
                            progress_bar.empty()
                            st.success("Data laporan berhasil diproses!")

                            all_dates_in_filtered_data = sorted(
                                list(
                                    set(
                                        date for program_data in categorized_report_data.values()
                                        for date in program_data.keys()
                                    )
                                )
                            )

                            monthly_dates = {}
                            for date_obj in all_dates_in_filtered_data:
                                year_month_key = (date_obj.year, date_obj.month)
                                if year_month_key not in monthly_dates:
                                    monthly_dates[year_month_key] = []
                                monthly_dates[year_month_key].append(date_obj)

                            st.session_state.categorized_report_data = categorized_report_data
                            st.session_state.all_dates_in_filtered_data = all_dates_in_filtered_data
                            st.session_state.monthly_dates = monthly_dates
                            st.session_state.total_catalogs_found = len(filtered_catalogs)
                            st.session_state.report_generated = True
                            st.session_state.last_generated_start_date = start_date
                            st.session_state.last_generated_end_date = end_date

                        else:
                            st.warning("Tidak ada katalog yang ditemukan dalam rentang tanggal yang dipilih.")
                            st.session_state.report_generated = False
                            st.session_state.categorized_report_data = {}
                            st.session_state.all_dates_in_filtered_data = []
                            st.session_state.monthly_dates = {}
                            st.session_state.total_catalogs_found = 0

                    else:
                        st.warning("Tidak ada katalog yang diambil dari API. Periksa URL atau koneksi.")
                        st.session_state.report_generated = False
                        st.session_state.categorized_report_data = {}
                        st.session_state.all_dates_in_filtered_data = []
                        st.session_state.monthly_dates = {}
                        st.session_state.total_catalogs_found = 0

                except Exception as e:
                    st.error(f"Terjadi kesalahan saat memproses laporan: {e}")
                    st.session_state.report_generated = False
                    st.session_state.categorized_report_data = {}
                    st.session_state.all_dates_in_filtered_data = []
                    st.session_state.monthly_dates = {}
                    st.session_state.total_catalogs_found = 0

# --- Bagian untuk Tampilan Laporan di Streamlit (Hanya jika laporan sudah digenerate) ---
# Ini akan selalu dijalankan pada setiap rerun, tetapi konten hanya akan muncul jika
# st.session_state.report_generated adalah True.
if st.session_state.report_generated:
    st.header("📊 Overview Records Katalog")

    st.info(f"Ditemukan {st.session_state.total_catalogs_found}"
            " katalog dalam rentang tanggal yang dipilih.")

    categorized_report_data = st.session_state.categorized_report_data
    all_dates_in_filtered_data = st.session_state.all_dates_in_filtered_data
    monthly_dates = st.session_state.monthly_dates

    sorted_months = sorted(monthly_dates.keys())

    unique_years = sorted(list(set(date_obj.year for date_obj in all_dates_in_filtered_data)))

    selected_year = None
    if unique_years:
        current_year = datetime.date.today().year
        default_year_index = unique_years.index(current_year) if current_year in unique_years else 0
        selected_year = st.selectbox(
            "Pilih Tahun untuk Preview",
            options=unique_years,
            index=default_year_index,
            help="Filter preview data per bulan berdasarkan tahun."
        )
    else:
        st.info("Tidak ada tahun yang tersedia untuk preview.")

    filtered_sorted_months = [
        (year, month) for year, month in sorted_months
        if selected_year is None or year == selected_year
    ]

    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        for year, month in filtered_sorted_months:
            dates_for_this_month = monthly_dates[(year, month)]

            if not dates_for_this_month:
                continue

            month_name = datetime.date(year, month, 1).strftime('%B %Y')
            date_columns_month = [
                date.strftime('%d')
                for date in dates_for_this_month
            ]

            df_data_month = []
            row_num = 1
            total_daily_counts_month = {date: 0 for date in dates_for_this_month}

            def sort_key(item):
                for index, (standard_name, _) in enumerate(SPECIFIC_PROGRAM_CATEGORIES_MAPPING):
                    if item == standard_name:
                        return (0, index)
                return (1, item)

            sorted_program_identifiers = sorted(
                categorized_report_data.keys(),
                key=sort_key
            )

            program_identifiers_in_this_month = [
                program for program in sorted_program_identifiers
                if any(
                    date in dates_for_this_month
                    for date in categorized_report_data.get(program, {}).keys()
                )
            ]

            for program_name in program_identifiers_in_this_month:
                row = {"NO": str(row_num), "NAMA PROGRAM": program_name}
                row_num += 1
                for date_col_obj in dates_for_this_month:
                    count = categorized_report_data[program_name].get(date_col_obj, 0)
                    row[date_col_obj.strftime('%d')] = count
                    total_daily_counts_month[date_col_obj] += count

                df_data_month.append(row)

            total_daily_row_month = {"NO": "", "NAMA PROGRAM": "TOTAL DAILY"}
            total_video_count_month = 0
            for date in dates_for_this_month:
                total_daily_row_month[date.strftime('%d')] = total_daily_counts_month[date]
                total_video_count_month += total_daily_counts_month[date]
            df_data_month.append(total_daily_row_month)

            total_video_row_month = {"NO": "", "NAMA PROGRAM": "TOTAL VIDEO"}
            # Inisialisasi semua kolom tanggal dengan None
            for date_col in date_columns_month:
                total_video_row_month[date_col] = None
            if date_columns_month:
                # Letakkan total video di kolom tanggal awal
                total_video_row_month[date_columns_month[0]] = total_video_count_month
            df_data_month.append(total_video_row_month)

            columns_order_month = ["NO", "NAMA PROGRAM"] + date_columns_month
            df_month = pd.DataFrame(df_data_month, columns=columns_order_month)
            df_month.to_excel(writer, sheet_name=month_name, index=False)

    st.download_button(
        label="📥 Unduh Laporan Excel",
        data=buffer,
        file_name=f"Laporan_Katalog_{st.session_state.start_date_input.strftime('%d-%m-%Y')}_sampai_{st.session_state.end_date_input.strftime('%d-%m-%Y')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        help="Unduh data laporan yang ditampilkan sebagai file Excel."
    )

    st.subheader("📋 Preview Data per Bulan")

    if not filtered_sorted_months:
        st.info(f"Tidak ada data untuk tahun {selected_year} dalam rentang tanggal yang dipilih.")
        
    month_tabs = st.tabs([
        datetime.date(year, month, 1).strftime('%B %Y')
        for year, month in filtered_sorted_months
    ])

    for tab, (year, month) in zip(month_tabs, filtered_sorted_months):
        with tab:
            st.subheader(f"Bulan {datetime.date(year, month, 1).strftime('%B %Y')}")

            dates_for_this_month_in_preview = sorted([
                date_obj for date_obj in all_dates_in_filtered_data
                if (date_obj.year == year and date_obj.month == month)
            ])

            total_daily_counts = {date: 0 for date in dates_for_this_month_in_preview}
            df_display_data = []
            display_row_num = 1

            sorted_program_identifiers_display = sorted(
                categorized_report_data.keys(),
                key=sort_key
            )
            program_identifiers_in_this_month_display = [
                program for program in sorted_program_identifiers_display
                if any(
                    date in dates_for_this_month_in_preview
                    for date in categorized_report_data.get(program, {}).keys()
                )
            ]

            for program_name in program_identifiers_in_this_month_display:
                row = {"NO": str(display_row_num), "NAMA PROGRAM": program_name}
                display_row_num += 1
                for date_col_obj in dates_for_this_month_in_preview:
                    count = categorized_report_data[program_name].get(date_col_obj, 0)
                    row[date_col_obj.strftime('%d')] = count
                    total_daily_counts[date_col_obj] += count
                df_display_data.append(row)

            total_daily_row = {"NO": "", "NAMA PROGRAM": "TOTAL DAILY"}
            for date_col_obj in dates_for_this_month_in_preview:
                total_daily_row[date_col_obj.strftime('%d')] = total_daily_counts[date_col_obj]
            df_display_data.append(total_daily_row)

            total_video_row = {"NO": "", "NAMA PROGRAM": "TOTAL VIDEO"}
            # Inisialisasi semua kolom tanggal dengan None
            display_date_columns_str = [d.strftime('%d') for d in dates_for_this_month_in_preview]
            for date_col_str in display_date_columns_str:
                total_video_row[date_col_str] = None
            total_video_count_month_display = sum(total_daily_counts.values())

            if dates_for_this_month_in_preview:
                # Letakkan total video di kolom tanggal awal
                total_video_row[dates_for_this_month_in_preview[0].strftime('%d')] = total_video_count_month_display
            df_display_data.append(total_video_row)

            display_columns_order = ["NO", "NAMA PROGRAM"] + [d.strftime('%d') for d in dates_for_this_month_in_preview]
            df_display = pd.DataFrame(df_display_data, columns=display_columns_order)
            st.dataframe(df_display, hide_index=True)

# Footer
st.markdown("---")
st.markdown("Made by Bryan Sean Abner (Anak Magang Nusantara TV - 2025)")
