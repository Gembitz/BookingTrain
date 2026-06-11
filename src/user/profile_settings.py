import streamlit as st
from src.database.supabase_client import get_user_profile, update_user_profile

def render_profile_settings(username: str):
    """
    Renders the profile settings form, allowing the user to update their display name,
    password, and perform a logout.
    """
    st.markdown('<div class="user-header">👤 Pengaturan Profil</div>', unsafe_allow_html=True)
    st.markdown('<div class="user-sub">Kelola detail profil Anda dan atur keamanan kata sandi di sini</div>', unsafe_allow_html=True)

    # Ambil profil: coba DB/simulasi dulu, fallback ke session_state
    profile = get_user_profile(username)
    if not profile:
        profile = st.session_state.get("logged_in_user")
    if not profile:
        st.error("Sesi pengguna tidak valid. Silakan logout dan login kembali.")
        return

    # Using a modern container style
    with st.container(border=True):
        st.subheader("Data Pengguna")
        
        # Read-only fields
        st.text_input("Username", value=profile["username"], disabled=True, help="Username tidak dapat diubah.")
        st.text_input("Peran / Hak Akses", value=profile["role"], disabled=True, help="Peran akun Anda ditentukan oleh sistem.")
        
        # Editable fields
        new_nama = st.text_input("Nama Lengkap", value=profile["nama"], placeholder="Ketik nama lengkap Anda...")
        
        st.write("---")
        st.subheader("🔑 Ubah Kata Sandi (Opsional)")
        new_password = st.text_input("Kata Sandi Baru", type="password", placeholder="Masukkan kata sandi baru (kosongkan jika tidak ingin mengubah)...")
        confirm_password = st.text_input("Konfirmasi Kata Sandi Baru", type="password", placeholder="Ketik ulang kata sandi baru...")
        
        st.write("")
        col_btn1, col_btn2 = st.columns([2, 1])
        
        with col_btn1:
            save_btn = st.button("Simpan Perubahan", type="primary", use_container_width=True)
        with col_btn2:
            # We place the Log Out button here inside profile settings
            logout_btn = st.button("Keluar (Log Out)", type="secondary", use_container_width=True, key="profile_logout_btn")
            
        if save_btn:
            if not new_nama.strip():
                st.error("Nama Lengkap tidak boleh kosong!")
            elif new_password:
                if len(new_password) < 5:
                    st.error("Kata Sandi Baru minimal harus 5 karakter!")
                elif new_password != confirm_password:
                    st.error("Konfirmasi Kata Sandi Baru tidak cocok!")
                else:
                    # Save both name and password
                    success = update_user_profile(username, new_nama.strip(), new_password)
                    if success:
                        st.success("Profil dan kata sandi berhasil diperbarui!")
                        # Refresh session state
                        st.session_state.logged_in_user = get_user_profile(username)
                        st.rerun()
                    else:
                        st.error("Gagal memperbarui profil di database.")
            else:
                # Save name only
                success = update_user_profile(username, new_nama.strip(), None)
                if success:
                    st.success("Profil berhasil diperbarui!")
                    # Refresh session state
                    st.session_state.logged_in_user = get_user_profile(username)
                    st.rerun()
                else:
                    st.error("Gagal memperbarui profil di database.")

        if logout_btn:
            st.session_state.logged_in_user = None
            if "chat_history" in st.session_state:
                del st.session_state.chat_history
            if "bot_state" in st.session_state:
                del st.session_state.bot_state
            if "bot_context" in st.session_state:
                del st.session_state.bot_context
            if "last_booking" in st.session_state:
                del st.session_state.last_booking
            if "nav_selection" in st.session_state:
                del st.session_state.nav_selection
            st.toast("Anda telah keluar dari aplikasi.", icon="ℹ️")
            st.rerun()
