import os
import streamlit as st
from typing import Dict, List, Any, Optional

# Load .env for local development
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Seed data (used as fallback when Supabase is unreachable) ──────────────────
DEFAULT_USERS: List[Dict[str, Any]] = [
    {"id": 1, "username": "admin",  "nama": "Administrator", "saldo": 1000000, "role": "Admin", "password": "admin123"},
    {"id": 2, "username": "dion",   "nama": "Dion Pratama",  "saldo": 500000,  "role": "User",  "password": "12345"},
    {"id": 3, "username": "budi",   "nama": "Budi Santoso",  "saldo": 50000,   "role": "User",  "password": "12345"},
]

DEFAULT_JADWAL: List[Dict[str, Any]] = [
    {"id": 1, "kereta": "Argo Bromo Anggrek", "rute": "Jakarta - Surabaya",   "kelas": "Eksekutif", "harga": 450000, "sisa_kursi": 50},
    {"id": 2, "kereta": "Gajayana",           "rute": "Jakarta - Malang",     "kelas": "Eksekutif", "harga": 500000, "sisa_kursi": 40},
    {"id": 3, "kereta": "Jayakarta",          "rute": "Jakarta - Surabaya",   "kelas": "Ekonomi",   "harga": 250000, "sisa_kursi": 80},
    {"id": 4, "kereta": "Kertajaya",          "rute": "Jakarta - Surabaya",   "kelas": "Ekonomi",   "harga": 200000, "sisa_kursi": 120},
    {"id": 5, "kereta": "Taksaka",            "rute": "Jakarta - Yogyakarta", "kelas": "Eksekutif", "harga": 380000, "sisa_kursi": 60},
]

DEFAULT_BOOKINGS: List[Dict[str, Any]] = [
    {"id": 1, "username": "dion", "kode": "TRAIN-89312", "kereta": "Argo Bromo Anggrek", "rute": "Jakarta - Surabaya", "status": "Lunas"},
    {"id": 2, "username": "budi", "kode": "TRAIN-12489", "kereta": "Jayakarta",           "rute": "Jakarta - Surabaya", "status": "Lunas"},
]


# ── Supabase client — cached so it is created only once per session ────────────
@st.cache_resource(show_spinner=False)
def _get_supabase_client():
    """
    Reads credentials from Streamlit Secrets (deployment) or .env (local),
    then returns an initialised Supabase client, or None if unavailable.
    """
    url: Optional[str] = None
    key: Optional[str] = None

    # 1. Streamlit Secrets (Streamlit Cloud deployment)
    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")
    except Exception:
        pass

    # 2. Environment variables (.env / system env)
    url = url or os.getenv("SUPABASE_URL")
    key = key or os.getenv("SUPABASE_KEY")

    if not url or not key:
        return None

    # Reject obvious placeholder values
    _PLACEHOLDERS = ("xxx.supabase.co", "your_supabase", "placeholder", "your-project")
    if any(p in url.lower() for p in _PLACEHOLDERS):
        return None

    try:
        from supabase import create_client
        client = create_client(url, key)
        # Quick connectivity probe — fetch 1 row from users
        client.table("users").select("id").limit(1).execute()
        return client
    except Exception as e:
        # Log to console only — do not expose credentials in UI
        print(f"[supabase_client] Connection failed: {e}")
        return None


def _client():
    """Return cached Supabase client or None."""
    return _get_supabase_client()


def is_supabase_connected() -> bool:
    return _client() is not None


# ── Simulation helpers ─────────────────────────────────────────────────────────

def init_simulation() -> None:
    """Lazy-initialise simulation data in session_state (safe to call any time)."""
    if "sim_users"    not in st.session_state: st.session_state.sim_users    = [u.copy() for u in DEFAULT_USERS]
    if "sim_jadwal"   not in st.session_state: st.session_state.sim_jadwal   = [j.copy() for j in DEFAULT_JADWAL]
    if "sim_bookings" not in st.session_state: st.session_state.sim_bookings = [b.copy() for b in DEFAULT_BOOKINGS]


def _sim_users()    -> List[Dict]: init_simulation(); return st.session_state.sim_users
def _sim_jadwal()   -> List[Dict]: init_simulation(); return st.session_state.sim_jadwal
def _sim_bookings() -> List[Dict]: init_simulation(); return st.session_state.sim_bookings


def _handle_error(fn_name: str, exc: Exception) -> None:
    """Log DB error and show a toast — does NOT flip USE_SUPABASE (client is cached)."""
    print(f"[supabase_client.{fn_name}] DB error: {exc}")
    st.toast(f"⚠️ Gagal terhubung ke database. Menggunakan data lokal sementara.", icon="⚠️")


# ── User operations ────────────────────────────────────────────────────────────

def get_user_profile(username: str) -> Optional[Dict[str, Any]]:
    db = _client()
    if db:
        try:
            res = db.table("users").select("*").eq("username", username.lower()).execute()
            if res.data:
                return res.data[0]
            # Supabase connected but user not found — fall through to simulation
        except Exception as e:
            _handle_error("get_user_profile", e)

    # Simulation fallback (covers: no DB, DB error, or user not in DB yet)
    for u in _sim_users():
        if u["username"].lower() == username.lower():
            return u
    return None


def verify_user_login(username: str, password: str) -> Optional[Dict[str, Any]]:
    db = _client()
    if db:
        try:
            res = db.table("users").select("*").eq("username", username.lower()).execute()
            if res.data:
                user = res.data[0]
                if user.get("password") == password:
                    return user
                return None  # Found in DB but wrong password — stop here
            # User not found in Supabase — fall through to simulation
        except Exception as e:
            _handle_error("verify_user_login", e)
            # Fall through to simulation on connection error only

    # Simulation fallback (covers: no DB, DB error, or user not in DB yet)
    for u in _sim_users():
        if u["username"].lower() == username.lower() and u.get("password") == password:
            return u
    return None


def create_user(username: str, nama: str, role: str = "User",
                saldo: int = 200000, password: str = "12345") -> Optional[Dict[str, Any]]:
    db = _client()
    if db:
        try:
            payload = {"username": username.lower(), "nama": nama,
                       "role": role, "saldo": saldo, "password": password}
            res = db.table("users").insert(payload).execute()
            if res.data:
                return res.data[0]
            # Insert returned empty — fall through to simulation
        except Exception as e:
            _handle_error("create_user", e)

    # Simulation fallback
    if get_user_profile(username) is not None:
        return None  # Username already exists
    users = _sim_users()
    new_id = max(u["id"] for u in users) + 1 if users else 1
    new_user = {"id": new_id, "username": username.lower(), "nama": nama,
                "saldo": saldo, "role": role, "password": password}
    users.append(new_user)
    return new_user


def update_user_profile(username: str, new_nama: str,
                        new_password: Optional[str] = None) -> bool:
    payload: Dict[str, Any] = {"nama": new_nama}
    if new_password:
        payload["password"] = new_password

    db = _client()
    if db:
        try:
            res = db.table("users").update(payload).eq("username", username.lower()).execute()
            if len(res.data) > 0:
                return True
            # No rows updated (user not in Supabase) — fall through to simulation
        except Exception as e:
            _handle_error("update_user_profile", e)

    for u in _sim_users():
        if u["username"].lower() == username.lower():
            u["nama"] = new_nama
            if new_password:
                u["password"] = new_password
            return True
    return False


def update_user_saldo(username: str, new_saldo: int) -> bool:
    db = _client()
    if db:
        try:
            res = db.table("users").update({"saldo": new_saldo}).eq("username", username.lower()).execute()
            if len(res.data) > 0:
                return True
            # No rows updated — fall through to simulation
        except Exception as e:
            _handle_error("update_user_saldo", e)

    for u in _sim_users():
        if u["username"].lower() == username.lower():
            u["saldo"] = new_saldo
            return True
    return False


# ── Jadwal operations ──────────────────────────────────────────────────────────

def get_all_jadwal() -> List[Dict[str, Any]]:
    db = _client()
    if db:
        try:
            res = db.table("jadwal").select("*").order("id").execute()
            if res.data:
                return res.data
            # Empty result — fall through to simulation seed data
        except Exception as e:
            _handle_error("get_all_jadwal", e)

    return list(_sim_jadwal())


def add_jadwal(kereta: str, rute: str, kelas: str,
               harga: int, kuota: int) -> Optional[Dict[str, Any]]:
    db = _client()
    if db:
        try:
            payload = {"kereta": kereta, "rute": rute, "kelas": kelas,
                       "harga": harga, "sisa_kursi": kuota}
            res = db.table("jadwal").insert(payload).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            _handle_error("add_jadwal", e)

    jadwal = _sim_jadwal()
    new_id = max(j["id"] for j in jadwal) + 1 if jadwal else 1
    new_j  = {"id": new_id, "kereta": kereta, "rute": rute, "kelas": kelas,
              "harga": harga, "sisa_kursi": kuota}
    jadwal.append(new_j)
    return new_j


def update_sisa_kursi(jadwal_id: int, new_sisa: int) -> bool:
    db = _client()
    if db:
        try:
            res = db.table("jadwal").update({"sisa_kursi": new_sisa}).eq("id", jadwal_id).execute()
            return len(res.data) > 0
        except Exception as e:
            _handle_error("update_sisa_kursi", e)

    for j in _sim_jadwal():
        if j["id"] == jadwal_id:
            j["sisa_kursi"] = new_sisa
            return True
    return False


# ── Booking operations ─────────────────────────────────────────────────────────

def get_all_bookings() -> List[Dict[str, Any]]:
    db = _client()
    if db:
        try:
            res = db.table("bookings").select("*").order("id", desc=True).execute()
            if res.data:
                return res.data
            # Empty — fall through to show simulation bookings
        except Exception as e:
            _handle_error("get_all_bookings", e)

    return list(_sim_bookings())


def get_user_bookings(username: str) -> List[Dict[str, Any]]:
    db = _client()
    if db:
        try:
            res = db.table("bookings").select("*").eq("username", username.lower()).order("id", desc=True).execute()
            # Always return DB result here (could be empty list = no bookings, which is valid)
            return res.data if res.data is not None else []
        except Exception as e:
            _handle_error("get_user_bookings", e)

    return [b for b in _sim_bookings() if b["username"].lower() == username.lower()]


def add_booking(username: str, kode: str, kereta: str,
                rute: str, status: str = "Lunas") -> Optional[Dict[str, Any]]:
    db = _client()
    if db:
        try:
            payload = {"username": username.lower(), "kode": kode,
                       "kereta": kereta, "rute": rute, "status": status}
            res = db.table("bookings").insert(payload).execute()
            if res.data:
                return res.data[0]
            # Insert returned empty — fall through to simulation
        except Exception as e:
            _handle_error("add_booking", e)

    bookings = _sim_bookings()
    new_id   = max(b["id"] for b in bookings) + 1 if bookings else 1
    new_b    = {"id": new_id, "username": username.lower(), "kode": kode,
                "kereta": kereta, "rute": rute, "status": status}
    bookings.append(new_b)
    return new_b
