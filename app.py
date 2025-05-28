import streamlit as st
import requests
import pandas as pd
import json
import datetime
import locale
from io import BytesIO
from urllib.parse import urlparse
from script import (
    get_all_main_catalogs,
    get_total_assets_from_metadata,
    get_catalog_total_assets,
    format_date_for_catalog_name_filter
)

# Konfigurasi halaman Streamlit
st.set_page_config(
    page_title="Laporan Records Katalog",
    page_icon="📊",
    layout="wide"
)

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
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # Kirim request login
        response = requests.post(
            login_url,
            json=login_data,
            headers=headers,
            verify=False # HATI-HATI: Nonaktifkan verifikasi SSL hanya di lingkungan terpercaya/internal
        )
        
        # Periksa status kode respons. Sesuaikan 200 jika API login mengembalikan status lain untuk sukses.
        if response.status_code == 200:
            # Coba dapatkan session ID dari cookie. Sesuaikan "session_id" jika nama cookie berbeda.
            cookies = response.cookies
            session_id = cookies.get("session_id")
            
            if session_id:
                return session_id, None
            else:
                # Jika session_id tidak ada di cookie, coba cari di body respons JSON (jika API mengembalikan di sana)
                try:
                    response_json = response.json()
                    session_id_from_body = response_json.get("session_id") # Sesuaikan kunci jika berbeda
                    if session_id_from_body:
                        return session_id_from_body, None
                    else:
                        return None, "Session ID tidak ditemukan di cookie maupun respons"
                except json.JSONDecodeError:
                    return None, "Session ID tidak ditemukan di cookie, dan respons bukan JSON"
            
        else:
            # Coba baca pesan error dari respons JSON jika ada
            try:
                error_data = response.json()
                error_message = error_data.get("message", f"Login gagal dengan status code: {response.status_code}")
                return None, error_message
            except json.JSONDecodeError:
                return None, f"Login gagal dengan status code: {response.status_code}. Tidak dapat membaca pesan error dari respons."
            
    except requests.exceptions.RequestException as e:
        return None, f"Error koneksi atau request: {str(e)}"
    except Exception as e:
        return None, f"Terjadi kesalahan tak terduga: {str(e)}"

# Fungsi untuk memvalidasi URL
def is_valid_url(url):
    try:
        result = urlparse(url)
        # Memeriksa scheme (http/https) dan network location
        return all([result.scheme in ['http', 'https'], result.netloc])
    except:
        return False # URL parsing gagal

# Set locale ke Indonesia
try:
    locale.setlocale(locale.LC_TIME, 'id_ID.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'Indonesian_Indonesia')
    except locale.Error:
        st.warning("Tidak dapat mengatur local ke Indonesia. Nama bulan mungkin dalam Bahasa Inggris.")
        locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')

# Inisialisasi session state jika belum ada
if 'is_logged_in' not in st.session_state:
    st.session_state.is_logged_in = False
if 'session_id' not in st.session_state:
    st.session_state.session_id = None
if 'base_url' not in st.session_state:
    st.session_state.base_url = None

# --- Tampilan Aplikasi --- #

# Mengatur tampilan sidebar secara kondisional
if st.session_state.is_logged_in:
    with st.sidebar:
        st.header("⚙️ Konfigurasi")
        st.success("✅ Sudah login")
        if st.button("Logout", type="secondary"):
            st.session_state.is_logged_in = False
            st.session_state.session_id = None
            st.session_state.base_url = None
            st.rerun() # Me-rerun aplikasi untuk menampilkan form login
        
        st.markdown("---")
        
        # Input untuk URL endpoint katalog utama (setelah login)
        url_endpoint = st.text_input(
            "URL Endpoint Katalog Utama",
            # Gunakan nilai default atau dari session state jika disimpan
            value=st.session_state.get('url_endpoint', "https://192.168.16.111/service/assets?page=1&view_type=list&sort_by=added_datetime&sort_order=-1&browse=true&catalog_id=650ad45f9f8784ac438fa212"),
            help="URL endpoint untuk mendapatkan daftar katalog"
        )
        # Simpan nilai url_endpoint di session state agar tetap ada setelah rerun
        st.session_state.url_endpoint = url_endpoint

        # Input untuk ID katalog utama (setelah login)
        main_catalog_id = st.text_input(
            "ID Katalog Utama",
            # Gunakan nilai default atau dari session state jika disimpan
            value=st.session_state.get('main_catalog_id', "650ad45f9f8784ac438fa212"),
            help="ID katalog utama untuk header Referer"
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
        # Input untuk BASE_URL
        # Menggunakan default value dari session_state jika sudah pernah diisi
        default_base_url = st.session_state.get('base_url', "https://192.168.16.111/service")
        base_url = st.text_input(
            "Base URL",
            value=default_base_url,
            help="URL dasar untuk API service (misal: https://192.168.16.111/service)"
        )

        # Form login
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        # Tombol login
        if st.button("Login", type="primary", use_container_width=True):
            if not is_valid_url(base_url):
                st.error("URL tidak valid. Pastikan format URL benar (diawali http:// atau https://).")
            else:
                with st.spinner("Mencoba login..."):
                    # Panggil fungsi login
                    session_id, error = get_session_id(base_url, username, password)

                    if session_id:
                        # Simpan data login di session state
                        st.session_state.session_id = session_id
                        st.session_state.base_url = base_url
                        st.session_state.is_logged_in = True
                        st.success("Login berhasil!")
                        st.rerun() # Me-rerun aplikasi untuk menampilkan konten laporan
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
                    url_endpoint_from_state = st.session_state.url_endpoint
                    main_catalog_id_from_state = st.session_state.main_catalog_id

                    headers = {
                        "Accept": "application/json, text/plain, */*",
                        "Accept-Encoding": "gzip, deflate, br, zstd",
                        "Accept-Language": "id-ID,id;q=0.9",
                        "Connection": "keep-alive",
                        "Host": urlparse(base_url_from_state).netloc,
                        "Referer": f"{base_url_from_state}/explorer/catalogs/{main_catalog_id_from_state}"
                    }
                    cookies = {"session_id": session_id_from_state}

                    # Format tanggal untuk filter nama katalog (kita tetap pakai tanggal mulai untuk filter nama jika diperlukan)
                    tanggal_filter_str_nama = format_date_for_catalog_name_filter(start_date)

                    st.info(f"Mempersiapkan laporan untuk rentang tanggal: {start_date.strftime('%d %B %Y')} - {end_date.strftime('%d %B %Y')}")

                    # Dapatkan daftar katalog (menggunakan URL endpoint dari session state)
                    catalogs_list = get_all_main_catalogs(url_endpoint_from_state, headers, cookies)

                    if catalogs_list:
                        report_data = []
                        progress_bar = st.progress(0)
                        total_catalogs = len(catalogs_list)

                        for idx, catalog in enumerate(catalogs_list):
                            catalog_id = catalog.get("_id")
                            catalog_name = catalog.get("catalog_name", "Nama Tidak Diketahui")

                            if not catalog_id or catalog_name == "Nama Tidak Diketahui":
                                continue

                            # Update progress
                            progress = (idx + 1) / total_catalogs
                            progress_bar.progress(progress)

                            # Proses katalog
                            count_for_this_catalog = 0
                            filter_matched = False

                            # Kondisi 1: Nama katalog mengandung string tanggal MULAI filter
                            if tanggal_filter_str_nama.upper() in catalog_name.upper():
                                # Ambil total_assets langsung dari metadata katalog (jika nama cocok, kita asumsikan seluruh katalog relevan untuk tanggal mulai)
                                count_for_this_catalog = get_catalog_total_assets(catalog_id, headers, cookies)
                                filter_matched = True

                            # Kondisi 2: Hitung aset di dalam katalog yang metadata tanggalnya cocok dengan RENTANG tanggal
                            # Kita panggil fungsi ini terlepas dari kondisi nama, untuk mendapatkan hitungan berdasarkan metadata.
                            # Perhatikan: get_total_assets_from_metadata di script.py perlu diubah untuk menerima end_date
                            count_metadata_match = get_total_assets_from_metadata(catalog_id, start_date, end_date, headers, cookies)

                            # Logika Final: Jika nama katalog cocok, gunakan count dari nama. Jika nama katalog TIDAK cocok TAPI ada aset dengan metadata tanggal yang cocok dalam rentang, gunakan count dari metadata.
                            if filter_matched:
                                # Count sudah diambil dari get_catalog_total_assets
                                pass # count_for_this_catalog sudah disetel
                            elif count_metadata_match > 0:
                                # Nama tidak cocok, tapi ada aset dengan metadata tanggal yang cocok dalam rentang
                                count_for_this_catalog = count_metadata_match
                                filter_matched = True # Tandai matched untuk dimasukkan ke laporan

                            # Jika filter_matched tetap False, maka katalog ini tidak masuk laporan
                            if filter_matched:
                                report_data.append({
                                    "ID Katalog": catalog_id,
                                    "Nama Katalog": catalog_name,
                                    f"Total Records ({start_date.strftime('%d %B %Y')} - {end_date.strftime('%d %B %Y')})": count_for_this_catalog # Nama kolom mencakup rentang tanggal
                                })

                        # Tampilkan hasil
                        if report_data:
                            df = pd.DataFrame(report_data)
                            st.success(f"✅ Laporan berhasil dibuat dengan {len(report_data)} katalog")

                            # Tampilkan tabel
                            st.dataframe(df, use_container_width=True)

                            # Tombol download Excel
                            buffer = BytesIO()
                            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                                df.to_excel(writer, index=False)

                            excel_data = buffer.getvalue()
                            st.download_button(
                                label="📥 Download Excel",
                                data=excel_data,
                                file_name=f"Laporan_Records_Katalog_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx", # Nama file mencakup rentang tanggal
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        else:
                            st.warning(f"Tidak ada katalog yang ditemukan untuk rentang tanggal {start_date.strftime('%d %B %Y')} - {end_date.strftime('%d %B %Y')}")
                    else:
                        st.error("Gagal mendapatkan daftar katalog. Mohon periksa konfigurasi atau URL endpoint.")

                except Exception as e:
                    st.error(f"Terjadi kesalahan: {str(e)}")

# Footer
st.markdown("---")
st.markdown("Made from Bryan Sean ❤️") 