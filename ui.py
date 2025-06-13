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
import socket
import ipaddress
import re

# Konfigurasi halaman Streamlit
st.set_page_config(
    page_title="Laporan Records Katalog",
    page_icon="📊",
    layout="wide"
)

# Daftar kategori program spesifik (case-insensitive) dengan variasi umum
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

# Fungsi untuk menentukan kategori program
def categorize_program(catalog_name):
    if not catalog_name:
        return catalog_name

    # Normalisasi nama katalog (lowercase dan hapus spasi di awal/akhir)
    normalized_catalog_name = catalog_name.strip().lower()

    # Pattern regex untuk setiap kategori program
    program_patterns = {
        # Mencocokkan variasi "morning" (morning, mornings)
        "NTV Morning": r"(?:ntv\s*)?(?:morning[s]?)",
        
        # Mencocokkan variasi "today" (today, today's)
        "NTV Today": r"(?:ntv\s*)?(?:today['s]?)",
        
        # Mencocokkan variasi "crime" (crime, crimes)
        "NTV Crime": r"(?:ntv\s*)?(?:crime[s]?)",
        
        # Mencocokkan variasi "prime" (prime, prime time)
        "NTV Prime": r"(?:ntv\s*)?(?:prime(?:\s*time)?)",
        
        # Mencocokkan variasi "sport" (sport, sports)
        "NTV Sports": r"(?:ntv\s*)?(?:sport[s]?)",
        
        # Mencocokkan variasi "topline" (topline, toplines)
        "NTV Toplines": r"(?:ntv\s*)?(?:topline[s]?)",
        
        # Mencocokkan variasi "tonight" (tonight, tonight's)
        "NTV Tonight": r"(?:ntv\s*)?(?:tonight['s]?)",
        
        # Mencocokkan variasi "newsflash" (newsflash, news flash, news-flash)
        "NTV Newsflash": r"(?:ntv\s*)?(?:news\s*flash|newsflash|news-flash)"
    }

    # Coba cocokkan dengan setiap pattern
    for program_name, pattern in program_patterns.items():
        if re.search(pattern, normalized_catalog_name, re.IGNORECASE):
            return program_name

    # Jika tidak cocok dengan kategori spesifik mana pun, kembalikan nama katalog asli
    return catalog_name

# Fungsi untuk mendeteksi base URL berdasarkan jaringan lokal
def detect_base_url():
    try:
        # Mendapatkan IP lokal
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        print(f"Detected local IP: {local_ip}")
        
        # Cek apakah IP berada dalam range yang diinginkan (172.10.11.x)
        ip = ipaddress.IPv4Address(local_ip)
        network = ipaddress.IPv4Network('172.10.11.0/24')
        is_in_network = ip in network
        print(f"Is {local_ip} in {network}? {is_in_network}")
        if is_in_network:
            return "https://192.168.16.111/service"
        else:
            # IP tidak dalam jaringan yang diinginkan
            return None

    except (ipaddress.AddressValueError, socket.gaierror) as e:
        print(f"Error checking IP address or network: {e}")
        return None
    except Exception as e:
        # Menangkap exception umum lainnya
        print(f"An unexpected error occurred during IP detection: {e}")
        return None

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
                        return None, "Session ID tidak ditemukan di cookie maupun respons"
                except json.JSONDecodeError:
                    return None, (f"Login gagal dengan status code: "
                                f"{response.status_code}. "
                                "Tidak dapat membaca pesan error dari respons.")

        else:
            # Coba baca pesan error dari respons JSON jika ada
            try:
                error_data = response.json()
                error_message = error_data.get("message",
                                             f"Login gagal dengan status code: "\
                                             f"{response.status_code}")
                return None, error_message
            except json.JSONDecodeError:
                return None, f"Login gagal dengan status code: "\
                            f"{response.status_code}. "\
                            "Tidak dapat membaca pesan error dari respons."

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
    if date_value_raw:
        try:
            # Pastikan FORMAT_STRING_TANGGAL_METADATA sesuai dengan format di metadata
            extracted_date_obj = datetime.datetime.strptime(
                str(date_value_raw), FORMAT_STRING_TANGGAL_METADATA).date()
            return extracted_date_obj
        except (ValueError, TypeError):
            pass  # Gagal parsing metadata
    return None

# Fungsi untuk membangun indeks tanggal dari daftar katalog
def build_date_index(catalogs_list: list[dict]) -> dict[datetime.date, list[dict]]:
    date_index = {}
    for catalog in catalogs_list:
        catalog_id = catalog.get("_id")
        catalog_name = catalog.get("catalog_name", "Nama Tidak Diketahui")

        if not catalog_id or catalog_name == "Nama Tidak Diketahui":
            continue

        # Ekstrak tanggal dari metadata
        metadata_date = extract_metadata_date(catalog)

        if metadata_date:
            # Tambahkan katalog ke list untuk tanggal ini di indeks
            if metadata_date not in date_index:
                date_index[metadata_date] = []
            date_index[metadata_date].append(catalog)
            
    return date_index

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
        default_url_endpoint_display = f"{st.session_state.base_url}{CATALOG_LIST_ENDPOINT_PATH}" if st.session_state.base_url else ""

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
            value=st.session_state.get('main_catalog_id', DEFAULT_CATALOG_QUERY_PARAMS.get('catalog_id')),
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
            st.warning("Tidak terhubung ke jaringan lokal yang diinginkan. Silakan hubungkan ke jaringan yang benar")
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
            value=datetime.date.today(),
            help="Pilih tanggal awal untuk laporan"
        )
    with col2:
        end_date = st.date_input(
            "Tanggal Akhir",
            value=datetime.date.today(),
            help="Pilih tanggal akhir untuk laporan"
        )

    # Validasi tanggal (opsional tapi disarankan)
    if start_date > end_date:
        st.error("⚠️ Tanggal Mulai tidak boleh lebih besar dari Tanggal Akhir.")
    else:
        # Tombol untuk menjalankan laporan
        if st.button("📈 Generate Laporan", type="primary"):
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
                        "Referer": f"{base_url_from_state}/explorer/catalogs/"
                                   f"{main_catalog_id_from_state}"
                    }
                    cookies = {"session_id": session_id_from_state}

                    # Format tanggal untuk filter nama katalog
                    # tanggal_filter_str_nama = format_date_for_catalog_name_filter(
                    #     start_date) # Tidak lagi digunakan untuk filtering API

                    st.info(f"Mempersiapkan laporan untuk rentang tanggal: "
                            f"{start_date.strftime('%d %B %Y')} - "
                            f"{end_date.strftime('%d %B %Y')}")

                    # Dapatkan daftar katalog (menggunakan fungsi yang sudah
                    # mendukung pagination)
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
                        # Langkah 1: Bangun indeks tanggal dari semua katalog yang
                        # didapat (sekali saja)
                        st.info("Membangun indeks tanggal dari katalog...")
                        date_index = build_date_index(catalogs_list)
                        st.info(f"Indeks dibangun dengan {len(date_index)} tanggal"
                                " unik.")

                        # --- Bagian untuk Tampilan Laporan Tunggal di Streamlit ---
                        st.header("📊 Overview Records Katalog")

                        # Kumpulkan katalog yang relevan berdasarkan rentang tanggal
                        # UTUH dari indeks
                        filtered_catalogs = []
                        # Iterasi melalui setiap tanggal dalam rentang yang dipilih
                        delta = end_date - start_date
                        for i in range(delta.days + 1):
                            current_date = start_date + datetime.timedelta(days=i)
                            # Ambil katalog dari indeks untuk tanggal ini
                            if current_date in date_index:
                                filtered_catalogs.extend(date_index[current_date])

                        st.info(f"Ditemukan {len(filtered_catalogs)}"
                               " katalog dalam rentang tanggal yang dipilih.")

                        # Proses katalog yang sudah difilter dan kelompokkan berdasarkan program
                        total_filtered_catalogs = len(filtered_catalogs)
                        if total_filtered_catalogs > 0:
                            # Struktur data baru untuk menyimpan total per program dan tanggal
                            categorized_report_data = {}

                            # Gunakan progress bar global
                            progress_bar = st.progress(0)

                            for idx, catalog in enumerate(filtered_catalogs):
                                catalog_id = catalog.get("_id")
                                catalog_name = catalog.get("catalog_name",
                                                         "Nama Tidak Diketahui")

                                if not catalog_id or catalog_name == "Nama Tidak Diketahui":
                                    continue

                                # Tentukan program/kategori (menggunakan fungsi yang sudah dimodifikasi)
                                program_identifier = categorize_program(catalog_name)

                                # Update progress bar
                                progress = (idx + 1) / total_filtered_catalogs
                                progress_bar.progress(progress)

                                # Proses katalog seperti sebelumnya (mengambil total records)
                                count_for_this_catalog = 0
                                # Pastikan base_url_from_state tersedia saat memanggil get_catalog_total_assets
                                catalog_total_assets = get_catalog_total_assets(
                                    catalog_id, headers, cookies)
                                if isinstance(catalog_total_assets, (int, float)):
                                    count_for_this_catalog = \
                                        int(catalog_total_assets)

                                # Ambil tanggal metadata
                                extracted_date_obj = extract_metadata_date(catalog)

                                if extracted_date_obj:
                                    # Simpan data dalam format {Program/Kategori: {tanggal_obj: total_records}}
                                    if program_identifier not in categorized_report_data:
                                        categorized_report_data[program_identifier] = {}

                                    # Tambahkan total records untuk program/kategori dan tanggal ini
                                    categorized_report_data[program_identifier][extracted_date_obj] = categorized_report_data[program_identifier].get(extracted_date_obj, 0) + count_for_this_catalog

                            # Setelah mengumpulkan semua data, pisahkan per bulan dan buat DataFrame
                            if categorized_report_data:
                                # Kelompokkan tanggal berdasarkan bulan dan tahun
                                monthly_dates = {}
                                all_dates_in_range = sorted(list(set(date for program_data in categorized_report_data.values() for date in program_data.keys())))

                                if not all_dates_in_range:
                                    st.warning(
                                        f"Tidak ada data laporan yang dihasilkan untuk rentang tanggal {start_date.strftime('%d %B %Y')} - {end_date.strftime('%d %B %Y')}"
                                    )

                                for date_obj in all_dates_in_range:
                                    year_month = (date_obj.year, date_obj.month)
                                    if year_month not in monthly_dates:
                                        monthly_dates[year_month] = []
                                    monthly_dates[year_month].append(date_obj)

                                # Urutkan bulan secara kronologis
                                sorted_months = sorted(monthly_dates.keys())

                                # Buat BytesIO buffer untuk menyimpan file Excel
                                buffer = BytesIO()

                                # Gunakan ExcelWriter untuk menulis ke multiple sheets
                                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                                    for year, month in sorted_months:
                                        dates_for_this_month = sorted(monthly_dates[(year, month)])
                                        month_name = datetime.date(year, month, 1).strftime('%B %Y')
                                        date_columns_month = [date.strftime('%d') for date in dates_for_this_month]

                                        df_data_month = []
                                        row_num = 1
                                        total_daily_counts_month = {date: 0 for date in dates_for_this_month}

                                        # Gunakan sort_key yang sudah diperbaiki
                                        # Untuk mempertahankan urutan SPECIFIC_PROGRAM_CATEGORIES_MAPPING dan mengurutkan sisanya
                                        def sort_key(item):
                                            # Periksa apakah item (nama program) adalah salah satu nama standar dalam mapping
                                            # Menggunakan daftar SPECIFIC_PROGRAM_CATEGORIES_MAPPING yang ada di awal file
                                            for index, (standard_name, _) in enumerate(SPECIFIC_PROGRAM_CATEGORIES_MAPPING):
                                                if item == standard_name:
                                                    # Jika cocok, beri prioritas (0) dan gunakan indeks untuk mempertahankan urutan
                                                    return (0, index)
                                            # Jika tidak cocok, beri prioritas lebih rendah (1) dan urutkan berdasarkan nama item
                                            return (1, item)

                                        sorted_program_identifiers = sorted(categorized_report_data.keys(), key=sort_key)

                                        for program_name in sorted_program_identifiers:
                                            row = {"NO": row_num, "NAMA PROGRAM": program_name}
                                            row_num += 1
                                            # Tambahkan data untuk tanggal di bulan ini
                                            for date in dates_for_this_month:
                                                count = categorized_report_data[program_name].get(date, 0)
                                                row[date.strftime('%d/%m/%Y')] = count
                                                total_daily_counts_month[date] += count
                                            df_data_month.append(row)

                                        # Tambahkan baris TOTAL DAILY untuk bulan ini
                                        total_daily_row_month = {"NO": "", "NAMA PROGRAM": "TOTAL DAILY"}
                                        total_video_count_month = 0
                                        for date in dates_for_this_month:
                                             total_daily_row_month[date.strftime('%d/%m/%Y')] = total_daily_counts_month[date]
                                             total_video_count_month += total_daily_counts_month[date]
                                        df_data_month.append(total_daily_row_month)

                                        # Tambahkan baris TOTAL VIDEO untuk bulan ini
                                        total_video_row_month = {"NO": "", "NAMA PROGRAM": "TOTAL VIDEO"}
                                        if date_columns_month:
                                             # Tempatkan total video bulanan di kolom terakhir bulan tersebut
                                             total_video_row_month[date_columns_month[-1]] = total_video_count_month
                                        df_data_month.append(total_video_row_month)

                                        # Buat DataFrame untuk bulan ini
                                        columns_order_month = ["NO", "NAMA PROGRAM"] + date_columns_month
                                        df_month = pd.DataFrame(df_data_month, columns=columns_order_month)

                                        # Tulis DataFrame bulan ini ke sheet baru
                                        df_month.to_excel(writer, sheet_name=month_name, index=False)

                                st.success(f"✅ Laporan berhasil dibuat dengan pemisahan per bulan.")

                                # Tambahkan tampilan tabel preview untuk setiap bulan
                                st.subheader("📋 Preview Data per Bulan")
                                
                                # Buat tabs untuk setiap bulan
                                month_tabs = st.tabs([datetime.date(year, month, 1).strftime('%B %Y') 
                                                    for year, month in sorted_months])
                                
                                # Tampilkan data untuk setiap bulan dalam tab masing-masing
                                for tab, (year, month) in zip(month_tabs, sorted_months):
                                    with tab:
                                        dates_for_this_month = sorted(monthly_dates[(year, month)])
                                        date_columns_month = [date.strftime('%d/%m/%Y') for date in dates_for_this_month]
                                        
                                        df_data_month = []
                                        row_num = 1
                                        total_daily_counts_month = {date: 0 for date in dates_for_this_month}
                                        
                                        # Gunakan sort_key yang sudah ada
                                        sorted_program_identifiers = sorted(categorized_report_data.keys(), key=sort_key)
                                        
                                        for program_name in sorted_program_identifiers:
                                            row = {"NO": row_num, "NAMA PROGRAM": program_name}
                                            row_num += 1
                                            for date in dates_for_this_month:
                                                count = categorized_report_data[program_name].get(date, 0)
                                                row[date.strftime('%d/%m/%Y')] = count
                                                total_daily_counts_month[date] += count
                                            df_data_month.append(row)
                                        
                                        # Tambahkan baris TOTAL DAILY
                                        total_daily_row_month = {"NO": "", "NAMA PROGRAM": "TOTAL DAILY"}
                                        total_video_count_month = 0
                                        for date in dates_for_this_month:
                                            total_daily_row_month[date.strftime('%d/%m/%Y')] = total_daily_counts_month[date]
                                            total_video_count_month += total_daily_counts_month[date]
                                        df_data_month.append(total_daily_row_month)
                                        
                                        # Tambahkan baris TOTAL VIDEO
                                        total_video_row_month = {"NO": "", "NAMA PROGRAM": "TOTAL VIDEO"}
                                        if date_columns_month:
                                            total_video_row_month[date_columns_month[-1]] = total_video_count_month
                                        df_data_month.append(total_video_row_month)
                                        
                                        # Buat dan tampilkan DataFrame
                                        columns_order_month = ["NO", "NAMA PROGRAM"] + date_columns_month
                                        df_month = pd.DataFrame(df_data_month, columns=columns_order_month)
                                        
                                        # Tampilkan tabel dengan styling
                                        st.dataframe(
                                            df_month,
                                            use_container_width=True,
                                            hide_index=True
                                        )

                                excel_data = buffer.getvalue()
                                st.download_button(
                                    label="📥 Download Excel (Per Bulan)",
                                    data=excel_data,
                                    file_name=f"Laporan_Records_Fusion_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                )

                            else:
                                st.warning(f"Tidak ada data laporan yang dihasilkan untuk rentang tanggal {start_date.strftime('%d %B %Y')} - {end_date.strftime('%d %B %Y')}")

                    else:
                        # Menampilkan pesan error yang lebih spesifik jika daftar katalog kosong saat sudah login
                        if st.session_state.is_logged_in:
                            st.error(
                                "Gagal mendapatkan daftar katalog. "
                                "Sesi login mungkin telah kedaluwarsa, "
                                "atau tidak ada katalog dalam rentang tanggal yang dipilih "
                                "dengan ID katalog utama yang dikonfigurasi. "
                                "Mohon coba Logout dan Login kembali atau periksa konfigurasi."
                            )
                        else:
                            st.error(
                                "Gagal mendapatkan daftar katalog. "
                                "Mohon periksa konfigurasi atau URL endpoint."
                            )

                except Exception as e:
                    st.error(f"Terjadi kesalahan saat memproses laporan: {str(e)}")

# Footer
st.markdown("---")
st.markdown("Made by Bryan Sean Abner (Anak Magang Nusantara TV - 2025)")
