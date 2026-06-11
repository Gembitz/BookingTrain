import streamlit as st
from src.database.supabase_client import is_supabase_connected, get_user_profile, create_user, verify_user_login
from src.user.manual_form import render_manual_form
from src.chatbot.bot_engine import handle_keretabot_response
from src.admin.admin_panel import render_admin_panel
from src.user.profile_settings import render_profile_settings

# Set Page Config
st.set_page_config(
    page_title="KAI Digital - Sistem Ticketing Terintegrasi",
    page_icon="🚆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load Custom Stylesheet
with open("src/style.css", "r") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Initialize Login State
if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None

# --- APPLICATION LOGIN SCREEN ---
if st.session_state.logged_in_user is None:
    st.markdown('<div class="header-title">🚆 KAI Digital Platform</div>', unsafe_allow_html=True)
    st.markdown('<div class="header-sub">Sistem Manajemen & Pembelian Tiket Kereta Api Terintegrasi</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.8, 1])
    
    with col2:
        with st.container(border=True):
            # Tab selection for Login vs Register
            login_tab, register_tab = st.tabs(["🔑 Masuk", "📝 Daftar Akun Baru"])
            
            with login_tab:
                st.subheader("Masuk Layanan Loket")
                username_val = st.text_input("Username", key="login_username", placeholder="Masukkan username (cth: dion, admin)...")
                password_val = st.text_input("Password", type="password", key="login_password", placeholder="Masukkan password...")
                
                login_btn = st.button("Masuk Aplikasi", type="primary", use_container_width=True, key="login_btn_click")
                
                if login_btn:
                    if not username_val or not password_val:
                        st.error("Username dan Password wajib diisi!")
                    else:
                        profile = verify_user_login(username_val.strip().lower(), password_val)
                        if profile:
                            st.session_state.logged_in_user = profile
                            if "nav_selection" in st.session_state:
                                del st.session_state.nav_selection
                            st.success(f"Berhasil masuk sebagai {profile['nama']}!")
                            st.rerun()
                        else:
                            st.error("Username atau Password salah! Coba username 'dion' (pass: '12345') atau 'admin' (pass: 'admin123').")
                            
            with register_tab:
                st.subheader("Pendaftaran Anggota")
                reg_username = st.text_input("Buat Username", key="reg_username", placeholder="Username unik...")
                reg_nama = st.text_input("Nama Lengkap", key="reg_nama", placeholder="Nama asli Anda...")
                reg_password = st.text_input("Buat Password", type="password", key="reg_password", placeholder="Minimal 5 karakter...")
                
                register_btn = st.button("Daftar & Masuk", type="primary", use_container_width=True, key="register_btn_click")
                
                if register_btn:
                    if not reg_username or not reg_nama or not reg_password:
                        st.error("Semua kolom registrasi wajib diisi!")
                    elif len(reg_password) < 5:
                        st.error("Password minimal harus 5 karakter!")
                    else:
                        # Check if username already exists
                        existing = get_user_profile(reg_username.strip().lower())
                        if existing:
                            st.error("Username sudah terdaftar! Gunakan username lain.")
                        else:
                            new_profile = create_user(
                                username=reg_username.strip().lower(),
                                nama=reg_nama.strip(),
                                role="User", # Default role is always User
                                saldo=200000,
                                password=reg_password
                            )
                            if new_profile:
                                st.session_state.logged_in_user = new_profile
                                if "nav_selection" in st.session_state:
                                    del st.session_state.nav_selection
                                st.success(f"Registrasi berhasil! Masuk sebagai {new_profile['nama']}.")
                                st.rerun()
                            else:
                                st.error("Terjadi kegagalan saat mendaftar akun baru.")

# --- APPLICATION INTERFACES (LOGGED IN) ---
else:
    user = st.session_state.logged_in_user
    # Refresh profile dari DB; jika tidak ditemukan, tetap pakai data sesi yang ada
    live_profile = get_user_profile(user["username"])
    if live_profile:
        user = live_profile
        st.session_state.logged_in_user = live_profile

    # Sidebar Logout & Status panel
    with st.sidebar:
        st.markdown('<div class="sidebar-header">🚆 KAI Digital Platform</div>', unsafe_allow_html=True)
        
        # Live connection status badge
        if is_supabase_connected():
            st.markdown('<span class="status-badge-connected">🟢 SUPABASE CONNECTED</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-badge-offline">🟡 OFFLINE SIMULATION</span>', unsafe_allow_html=True)

    # --- ROLE ROUTING LAYOUT ---
    
    # Initialize default nav selection based on role if not present
    if "nav_selection" not in st.session_state:
        st.session_state.nav_selection = "admin" if user["role"] == "Admin" else "chatbot"
    
    # CASE: Admin Profile
    if user["role"] == "Admin":
        # Admin Navigation Bar
        nav_cols = st.columns([1.5, 4.0, 1.5])
        with nav_cols[0]:
            admin_active = st.session_state.nav_selection == "admin"
            if st.button("⚙️ Panel Admin", type="primary" if admin_active else "secondary", use_container_width=True, key="nav_admin"):
                st.session_state.nav_selection = "admin"
                st.rerun()
        with nav_cols[2]:
            profile_active = st.session_state.nav_selection == "profile"
            display_name = user['nama']
            if len(display_name) > 12:
                display_name = display_name[:10] + "..."
            profile_btn_text = f"👤 {display_name}"
            if st.button(profile_btn_text, type="primary" if profile_active else "secondary", use_container_width=True, key="nav_profile"):
                st.session_state.nav_selection = "profile"
                st.rerun()
        
        if st.session_state.nav_selection == "profile":
            render_profile_settings(user["username"])
        else:
            render_admin_panel()
        
    # CASE: User Profile
    else:
        # Navigation Bar
        nav_cols = st.columns([1.5, 1.5, 2.5, 1.5])
        with nav_cols[0]:
            chatbot_active = st.session_state.nav_selection == "chatbot"
            if st.button("🤖 Asisten Chatbot", type="primary" if chatbot_active else "secondary", use_container_width=True, key="nav_chatbot"):
                st.session_state.nav_selection = "chatbot"
                st.rerun()
        with nav_cols[1]:
            manual_active = st.session_state.nav_selection == "manual"
            if st.button("🎫 Pemesanan Tiket", type="primary" if manual_active else "secondary", use_container_width=True, key="nav_manual"):
                st.session_state.nav_selection = "manual"
                st.rerun()
        # nav_cols[2] intentionally left empty as spacer
        with nav_cols[3]:
            profile_active = st.session_state.nav_selection == "profile"
            display_name = user['nama']
            if len(display_name) > 12:
                display_name = display_name[:10] + "..."
            profile_btn_text = f"👤 {display_name}"
            if st.button(profile_btn_text, type="primary" if profile_active else "secondary", use_container_width=True, key="nav_profile"):
                st.session_state.nav_selection = "profile"
                st.rerun()
        
        if st.session_state.nav_selection == "profile":
            render_profile_settings(user["username"])
        elif st.session_state.nav_selection == "chatbot":
            # Initialize Chat history if missing
            if "chat_history" not in st.session_state:
                st.session_state.chat_history = [
                    {
                        "role": "assistant", 
                        "content": f"Halo Kak {user['nama']}! 🚂 KeretaBot siap membantu Kakak di stasiun. Silakan ketik **'pesan'** untuk memesan tiket, atau **'tiket saya'** untuk melihat riwayat perjalanan Kakak."
                    }
                ]
                
            # Render chat bubble dialogue
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
            
            # Chat input
            user_input = st.chat_input("Ketik pesan ke KeretaBot...")
            
            if user_input:
                # User message
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                with st.chat_message("user"):
                    st.markdown(user_input)
                
                # Fetch state chatbot response
                response = handle_keretabot_response(user_input, user["username"])
                
                # Bot message
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                with st.chat_message("assistant"):
                    st.markdown(response)
                    
                st.rerun()
                
        else:
            # Render manual form view
            render_manual_form(user["username"])

# Footer credit
st.markdown('<div class="footer">KAI Digital Ticketing App © 2026 - Senior Developer Implementation</div>', unsafe_allow_html=True)
