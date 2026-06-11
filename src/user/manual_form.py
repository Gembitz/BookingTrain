import streamlit as st
import random
import string
import pandas as pd
from src.database.supabase_client import (
    get_user_profile,
    get_all_jadwal,
    add_booking,
    update_sisa_kursi,
    get_user_bookings
)

def generate_booking_code() -> str:
    """Generates a random unique booking code with format TRAIN-XXXXX."""
    suffix = ''.join(random.choices(string.digits, k=5))
    return f"TRAIN-{suffix}"

def render_manual_form(username: str):
    st.markdown('<div class="user-header">🎫 Pemesanan Tiket Manual</div>', unsafe_allow_html=True)
    st.markdown('<div class="user-sub">Cari Jadwal Kereta & Lakukan Pembelian Tiket Secara Mandiri</div>', unsafe_allow_html=True)

    # Ambil profil: coba DB/simulasi dulu, fallback ke session_state
    profile = get_user_profile(username)
    if not profile:
        profile = st.session_state.get("logged_in_user")
    if not profile:
        st.error(f"Sesi pengguna tidak valid. Silakan logout dan login kembali.")
        return

    # Profile summary card
    st.markdown(f"""
        <div class="profile-container">
            <h4 style="margin-top:0; color:#38BDF8; font-weight:700;">👤 Profil Penumpang</h4>
            <div style="display:flex; justify-content:space-between; flex-wrap:wrap; align-items:center;">
                <div><b>Nama:</b> {profile['nama']} ({profile['username']})</div>
                <div><b>Role:</b> <span style="background: linear-gradient(135deg, #38BDF8 0%, #2563EB 100%); padding:4px 12px; border-radius:8px; font-size:0.8rem; font-weight:600; color: white;">{profile['role']}</span></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🛒 Form Pembelian Tiket", "🕒 Riwayat Transaksi Saya"])

    with tab1:
        st.subheader("Beli Tiket Perjalanan")

        # Display last successful booking boarding pass if exists
        if "last_booking" in st.session_state and st.session_state.last_booking:
            b = st.session_state.last_booking
            st.success("🎉 Tiket Perjalanan Berhasil Diterbitkan!")
            st.markdown(f"""
                <div class="ticket-receipt">
                    <div class="ticket-title">BOARDING PASS</div>
                    <div class="ticket-row">
                        <span class="ticket-label">KODE BOOKING:</span>
                        <span class="ticket-value" style="color: #38BDF8; font-size:1.25rem;">{b['kode']}</span>
                    </div>
                    <div class="ticket-row">
                        <span class="ticket-label">NAMA PENUMPANG:</span>
                        <span class="ticket-value">{b['passenger_name']}</span>
                    </div>
                    <div class="ticket-row">
                        <span class="ticket-label">KERETA API:</span>
                        <span class="ticket-value">{b['kereta']} ({b['kelas']})</span>
                    </div>
                    <div class="ticket-row">
                        <span class="ticket-label">RUTE:</span>
                        <span class="ticket-value">{b['rute']}</span>
                    </div>
                    <div class="ticket-row">
                        <span class="ticket-label">HARGA TIKET:</span>
                        <span class="ticket-value">Rp {b['harga']:,.0f}</span>
                    </div>
                    <div class="ticket-row" style="border-top:1px dashed rgba(255,255,255,0.1); padding-top:0.5rem; margin-top:0.5rem;">
                        <span class="ticket-label">STATUS PEMBAYARAN:</span>
                        <span class="ticket-value" style="color:#34D399;">LUNAS</span>
                    </div>
                    <div class="ticket-barcode"></div>
                </div>
            """, unsafe_allow_html=True)
            if st.button("Tutup Boarding Pass Baru", type="secondary"):
                del st.session_state.last_booking
                st.rerun()
            st.write("---")
        
        schedules = get_all_jadwal()
        if not schedules:
            st.info("Jadwal kereta tidak tersedia saat ini.")
            return

        # 1. Dropdown Pilih Rute (Unique routes)
        unique_routes = sorted(list(set([s["rute"] for s in schedules])))
        selected_route = st.selectbox("Pilih Rute Perjalanan", unique_routes)

        # 2. Filter matching schedules for selected route
        matching_schedules = [s for s in schedules if s["rute"] == selected_route]
        
        if not matching_schedules:
            st.warning("Tidak ada kereta melayani rute ini.")
            return

        # 3. Dropdown Pilih Kereta (Dynamically filtered)
        train_options = [
            f"{s['kereta']} ({s['kelas']}) - Rp {s['harga']:,.0f} [Sisa: {s['sisa_kursi']} kursi]" 
            for s in matching_schedules
        ]
        selected_train_str = st.selectbox("Pilih Kereta Api", train_options)
        
        # Parse selected train
        selected_index = train_options.index(selected_train_str)
        selected_sched = matching_schedules[selected_index]

        # 4. Input Nama Penumpang
        passenger_name = st.text_input("Nama Penumpang", value=profile['nama'], placeholder="Ketik nama lengkap penumpang")

        # Details summary
        st.write("---")
        st.markdown("### Ringkasan Transaksi")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Kereta:** {selected_sched['kereta']} ({selected_sched['kelas']})")
            st.write(f"**Rute:** {selected_sched['rute']}")
        with col2:
            st.write(f"**Harga Tiket:** Rp {selected_sched['harga']:,.0f}")
            st.write(f"**Sisa Kursi:** {selected_sched['sisa_kursi']} Kursi")
            
        # Validation checks
        can_buy = True
        error_message = ""
        
        if not passenger_name.strip():
            can_buy = False
            error_message = "Nama penumpang tidak boleh kosong!"
        elif selected_sched["sisa_kursi"] <= 0:
            can_buy = False
            error_message = "Maaf, sisa kursi kereta pilihan Anda sudah habis."

        if not can_buy and passenger_name.strip():
            st.error(error_message)

        # 5. Konfirmasi Pembelian Button
        confirm_btn = st.button("Konfirmasi Pembelian", disabled=not can_buy, type="primary", use_container_width=True)

        if confirm_btn and can_buy:
            new_code = generate_booking_code()
            new_sisa = selected_sched["sisa_kursi"] - 1

            # Database updates
            update_sisa_kursi(selected_sched["id"], new_sisa)
            booking_res = add_booking(
                username=username,
                kode=new_code,
                kereta=selected_sched["kereta"],
                rute=selected_sched["rute"],
                status="Lunas"
            )

            if booking_res:
                st.session_state.last_booking = {
                    "kode": new_code,
                    "passenger_name": passenger_name,
                    "kereta": selected_sched["kereta"],
                    "kelas": selected_sched["kelas"],
                    "rute": selected_sched["rute"],
                    "harga": selected_sched["harga"]
                }
                st.session_state.current_user = get_user_profile(username)
                st.rerun()
            else:
                st.error("Terjadi kegagalan saat menyimpan data transaksi.")

    with tab2:
        st.subheader("Daftar Riwayat Booking")
        bookings = get_user_bookings(username)
        
        if not bookings:
            st.info("Anda belum memiliki riwayat pemesanan tiket.")
        else:
            df_bookings = pd.DataFrame(bookings)
            display_cols = ["kode", "kereta", "rute", "status"]
            if "id" in df_bookings.columns:
                display_cols.insert(0, "id")
            st.dataframe(df_bookings[display_cols], use_container_width=True)
