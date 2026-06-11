import streamlit as st
import pandas as pd
from src.database.supabase_client import get_all_jadwal, add_jadwal, get_all_bookings

def render_admin_panel():


    st.markdown('<div class="admin-header">⚙️ Panel Admin KAI</div>', unsafe_allow_html=True)
    st.markdown('<div class="admin-sub">Kelola Jadwal Kereta & Pantau Seluruh Transaksi Penumpang</div>', unsafe_allow_html=True)

    # 1. Fetch data
    schedules = get_all_jadwal()
    bookings = get_all_bookings()

    # Calculate metrics
    total_bookings = len(bookings)
    price_map = {(s["kereta"].lower(), s["rute"].lower()): s["harga"] for s in schedules}
    
    total_revenue = 0
    for b in bookings:
        key = (b["kereta"].lower(), b["rute"].lower())
        price = price_map.get(key, 250000)
        if b.get("status") == "Lunas":
            total_revenue += price

    total_schedules = len(schedules)
    total_seats_available = sum([s["sisa_kursi"] for s in schedules])

    # Display Metrics Row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Total Pendapatan</div>
                <div class="metric-value">Rp {total_revenue:,.0f}</div>
            </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Tiket Terjual</div>
                <div class="metric-value">{total_bookings} Tiket</div>
            </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Jadwal Aktif</div>
                <div class="metric-value">{total_schedules} Rute</div>
            </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Total Sisa Kursi</div>
                <div class="metric-value">{total_seats_available} Kursi</div>
            </div>
        """, unsafe_allow_html=True)

    # Tabs
    tab1, tab2, tab3 = st.tabs(["📊 Pemantauan Transaksi", "➕ Tambah Jadwal Baru", "🚆 Daftar Jadwal Aktif"])

    with tab1:
        st.subheader("Log Transaksi Tiket")
        if not bookings:
            st.info("Belum ada transaksi pemesanan tiket.")
        else:
            df_bookings = pd.DataFrame(bookings)
            
            # Select relevant columns for tracking
            columns_to_show = ["kode", "username", "kereta", "rute", "status"]
            if "id" in df_bookings.columns:
                columns_to_show.insert(0, "id")
                
            df_show = df_bookings[columns_to_show]
            
            # Simple interactive search
            search_query = st.text_input("🔍 Cari berdasarkan Username atau Kode Booking", placeholder="Contoh: dion atau TRAIN-...")
            if search_query:
                mask = (df_show['username'].str.contains(search_query, case=False, na=False)) | \
                       (df_show['kode'].str.contains(search_query, case=False, na=False))
                df_show = df_show[mask]

            st.dataframe(df_show, use_container_width=True)

    with tab2:
        st.subheader("Input Jadwal Perjalanan Baru")
        
        with st.form("tambah_jadwal_form"):
            col_a, col_b = st.columns(2)
            with col_a:
                kereta = st.text_input("Nama Kereta Api", placeholder="Contoh: Argo Lawu")
                
                # Rute Dropdown with manual entry option
                rute_options = [
                    "Jakarta - Surabaya", 
                    "Jakarta - Malang", 
                    "Jakarta - Yogyakarta", 
                    "Bandung - Jakarta", 
                    "Surabaya - Malang",
                    "Rute Lain (Ketik Manual)"
                ]
                selected_rute_option = st.selectbox("Pilih Rute Perjalanan", rute_options)
                
                # Show custom input if "Rute Lain" is selected
                custom_rute = ""
                if selected_rute_option == "Rute Lain (Ketik Manual)":
                    custom_rute = st.text_input("Masukkan Rute Kustom (Asal - Tujuan)", placeholder="Contoh: Semarang - Surabaya")
                
                kelas = st.selectbox("Pilih Kelas Kereta", ["Eksekutif", "Bisnis", "Ekonomi"])
            with col_b:
                harga = st.number_input("Harga Tiket (Rp)", min_value=10000, value=250000, step=10000)
                kuota = st.number_input("Kuota Kursi Awal", min_value=10, value=80, step=10)
            
            submit_btn = st.form_submit_button("Simpan Jadwal Perjalanan", use_container_width=True)
            
            if submit_btn:
                # Resolve the chosen route
                final_rute = custom_rute if selected_rute_option == "Rute Lain (Ketik Manual)" else selected_rute_option
                
                if not kereta or not final_rute:
                    st.error("Nama Kereta dan Rute Perjalanan wajib diisi!")
                else:
                    new_sched = add_jadwal(kereta, final_rute, kelas, int(harga), int(kuota))
                    if new_sched:
                        st.success(f"Berhasil menambahkan jadwal baru: **{kereta} ({final_rute})** dengan kuota {kuota} kursi.")
                        st.rerun()
                    else:
                        st.error("Gagal menyimpan jadwal baru.")

    with tab3:
        st.subheader("Daftar Jadwal Perjalanan Kereta Api")
        if not schedules:
            st.info("Belum ada jadwal perjalanan.")
        else:
            df_schedules = pd.DataFrame(schedules)
            if "harga" in df_schedules.columns:
                df_schedules["harga"] = df_schedules["harga"].apply(lambda x: f"Rp {x:,.0f}")
                
            cols_to_show = ["id", "kereta", "rute", "kelas", "harga", "sisa_kursi"]
            df_show = df_schedules[[c for c in cols_to_show if c in df_schedules.columns]]
            
            st.dataframe(df_show, use_container_width=True)

if __name__ == "__main__":
    render_admin_panel()
