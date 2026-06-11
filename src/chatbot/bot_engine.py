import streamlit as st
import random
import string
import re
from typing import Dict, List, Any, Optional
from src.database.supabase_client import (
    get_user_profile,
    get_all_jadwal,
    add_booking,
    update_sisa_kursi,
    get_user_bookings,
)

# ── State constants ────────────────────────────────────────────────────────────
STATE_IDLE               = "IDLE"
STATE_PILIH_RUTE         = "PILIH_RUTE"
STATE_PILIH_KERETA       = "PILIH_KERETA"
STATE_ISI_PENUMPANG      = "ISI_PENUMPANG"
STATE_KONFIRMASI         = "KONFIRMASI"

# ── Jadwal tambahan (jam berangkat / tiba) ─────────────────────────────────────
# Karena DB tidak menyimpan jam, kita simpan mapping statis berdasarkan nama kereta.
JADWAL_JAM: Dict[str, Dict[str, str]] = {
    "Argo Bromo Anggrek": {"berangkat": "08:00", "tiba": "16:30", "stasiun_asal": "Gambir",     "stasiun_tujuan": "Surabaya Pasarturi"},
    "Gajayana":           {"berangkat": "17:00", "tiba": "05:30", "stasiun_asal": "Gambir",     "stasiun_tujuan": "Malang"},
    "Jayakarta":          {"berangkat": "10:30", "tiba": "21:00", "stasiun_asal": "Pasar Senen","stasiun_tujuan": "Surabaya Gubeng"},
    "Kertajaya":          {"berangkat": "06:00", "tiba": "17:30", "stasiun_asal": "Pasar Senen","stasiun_tujuan": "Surabaya Pasarturi"},
    "Taksaka":            {"berangkat": "09:00", "tiba": "14:45", "stasiun_asal": "Gambir",     "stasiun_tujuan": "Yogyakarta"},
}
DEFAULT_JAM = {"berangkat": "07:00", "tiba": "14:00", "stasiun_asal": "Stasiun Asal", "stasiun_tujuan": "Stasiun Tujuan"}

# ── Alias kota untuk pencarian fleksibel ──────────────────────────────────────
KOTA_ALIAS: Dict[str, str] = {
    "jkt": "jakarta", "jkta": "jakarta",
    "sby": "surabaya", "sbya": "surabaya",
    "mlg": "malang",
    "yk": "yogyakarta", "yogya": "yogyakarta", "jogja": "yogyakarta", "jogjakarta": "yogyakarta",
    "bdg": "bandung",
    "smg": "semarang",
}

# ── Helper functions ───────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    """Lowercase, remove punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def _expand_alias(word: str) -> str:
    return KOTA_ALIAS.get(word, word)


def _normalize_city(text: str) -> str:
    """Normalize city name: expand aliases and title-case."""
    words = [_expand_alias(w) for w in _norm(text).split()]
    return " ".join(words).title()


def generate_booking_code() -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"KAI-{suffix}"


def generate_seat_number(kelas: str) -> str:
    gerbong = random.randint(1, 8)
    nomor   = random.randint(1, 20)
    sisi    = random.choice(["A", "B", "C", "D"])
    return f"G{gerbong}-{nomor:02d}{sisi}"


def _get_jam(kereta_nama: str) -> Dict[str, str]:
    return JADWAL_JAM.get(kereta_nama, DEFAULT_JAM)


def _ensure_bot_state():
    if "bot_state"   not in st.session_state: st.session_state.bot_state   = STATE_IDLE
    if "bot_context" not in st.session_state: st.session_state.bot_context = {}


def _reset():
    st.session_state.bot_state   = STATE_IDLE
    st.session_state.bot_context = {}


# ── FAQ ────────────────────────────────────────────────────────────────────────

FAQ: List[Dict[str, Any]] = [
    {
        "keywords": ["cara pesan", "cara beli", "cara booking", "memesan tiket", "beli tiket", "pesan tiket", "bagaimana pesan", "gimana pesan"],
        "answer": (
            "Untuk memesan tiket lewat chatbot ini, cukup ketik **'pesan'** dan ikuti langkah-langkahnya. "
            "Kak {nama} juga bisa memesan lewat menu **🎫 Pemesanan Tiket** di atas. 🚂"
        ),
    },
    {
        "keywords": ["jadwal", "lihat jadwal", "cari jadwal", "jam kereta", "kapan berangkat", "jadwal kereta"],
        "answer": (
            "Saya bisa bantu carikan jadwal! Ketik **'pesan'** lalu masukkan rute perjalanan "
            "(contoh: *Jakarta - Surabaya*), dan semua kereta yang tersedia akan ditampilkan. 🚂"
        ),
    },
    {
        "keywords": ["harga", "tarif", "biaya", "berapa harga", "tiket berapa"],
        "answer": (
            "Harga tiket bervariasi tergantung kereta dan kelas. Ketik **'pesan'** dan masukkan rute "
            "perjalanan untuk melihat daftar harga terkini. 🚂"
        ),
    },
    {
        "keywords": ["pilih kursi", "nomor kursi", "tempat duduk", "milih kursi"],
        "answer": (
            "Nomor kursi ditetapkan otomatis oleh sistem saat tiket diterbitkan. "
            "Kak {nama} akan mendapatkan nomor kursi yang tertera di Boarding Pass. 🚂"
        ),
    },
    {
        "keywords": ["bayar", "pembayaran", "cara bayar", "metode bayar", "transfer"],
        "answer": (
            "Pembayaran dilakukan secara langsung saat konfirmasi pemesanan — tidak perlu transfer manual. "
            "Tiket langsung terbit setelah konfirmasi. 🚂"
        ),
    },
    {
        "keywords": ["batal", "cancel", "refund", "pembatalan", "reschedule", "jadwal ulang"],
        "answer": (
            "Pembatalan tiket dapat dilakukan **maksimal 1 jam sebelum keberangkatan** melalui loket stasiun. "
            "Untuk reschedule, batalkan tiket terlebih dahulu lalu pesan tiket baru. 🚂"
        ),
    },
    {
        "keywords": ["riwayat", "tiket saya", "pemesanan saya", "history", "lihat tiket"],
        "answer": "Ketik **'tiket saya'** untuk melihat semua tiket yang pernah Kak {nama} pesan. 🚂",
    },
    {
        "keywords": ["check in", "check-in", "boarding", "berapa menit sebelum", "jam check in"],
        "answer": (
            "Check-in di stasiun dapat dilakukan **paling lambat 30 menit** sebelum jadwal keberangkatan. "
            "Tunjukkan e-ticket dan KTP/KIA asli saat check-in. 🚂"
        ),
    },
    {
        "keywords": ["anak", "bayi", "balita", "tiket anak"],
        "answer": (
            "Anak usia **3 tahun ke atas** wajib membeli tiket penuh. "
            "Anak di bawah 3 tahun gratis (tidak mendapat kursi sendiri, dipangku pendamping). 🚂"
        ),
    },
    {
        "keywords": ["telat", "terlambat", "tertinggal", "ketinggalan kereta"],
        "answer": (
            "Jika tertinggal kereta, tiket **hangus** dan tidak dapat di-refund maupun di-reschedule. "
            "Pastikan tiba di stasiun minimal 30 menit sebelum keberangkatan ya, Kak {nama}! 🚂"
        ),
    },
    {
        "keywords": ["wifi", "makanan", "makan di kereta", "fasilitas", "stopkontak", "colokan"],
        "answer": (
            "Kereta kelas **Eksekutif** dilengkapi WiFi gratis, stopkontak, dan layanan kereta makan. "
            "Kelas **Bisnis** memiliki stopkontak. Kelas **Ekonomi** tersedia kereta makan di beberapa jadwal. 🚂"
        ),
    },
    {
        "keywords": ["cs", "customer service", "hubungi", "kontak", "call center", "bantuan"],
        "answer": (
            "Hubungi Customer Service KAI:\n"
            "- 📞 **121** (24 jam)\n"
            "- 📧 **cs@kai.id**\n"
            "- 💬 WhatsApp: **0812-1212-1212**\n\n"
            "Siap membantu Kak {nama}! 🚂"
        ),
    },
    {
        "keywords": ["syarat", "persyaratan", "dokumen", "ktp", "identitas"],
        "answer": (
            "Syarat naik kereta: \n"
            "1. Tunjukkan **e-ticket / Boarding Pass** yang valid\n"
            "2. Bawa **KTP/KIA/Paspor** asli sesuai nama penumpang\n"
            "3. Kondisi sehat saat keberangkatan\n\n"
            "Selamat bepergian, Kak {nama}! 🚂"
        ),
    },
    {
        "keywords": ["promo", "diskon", "voucher", "cashback", "murah"],
        "answer": (
            "Promo tiket tersedia di aplikasi KAI Access! Di platform ini, "
            "tarif yang ditampilkan sudah merupakan harga terbaik untuk setiap kelas perjalanan. 🚂"
        ),
    },
]


def _find_faq(user_input: str, nama: str) -> Optional[str]:
    norm_input = _norm(user_input)
    best_score = 0
    best_answer = None
    for item in FAQ:
        score = sum(1 for kw in item["keywords"] if _norm(kw) in norm_input)
        if score > best_score:
            best_score = score
            best_answer = item["answer"]
    if best_score > 0 and best_answer:
        return best_answer.format(nama=nama)
    return None


# ── Route matching ─────────────────────────────────────────────────────────────

def _parse_route_input(text: str) -> Optional[tuple]:
    """
    Try to extract (asal, tujuan) from free-form text.
    Supports: 'jakarta - surabaya', 'jakarta surabaya', 'dari jakarta ke surabaya'
    """
    t = _norm(text)
    # "dari X ke Y" or "X ke Y"
    m = re.search(r"dari\s+([\w\s]+?)\s+ke\s+([\w\s]+)", t)
    if not m:
        m = re.search(r"([\w\s]+?)\s+ke\s+([\w\s]+)", t)
    if not m:
        # X - Y or X – Y
        parts = re.split(r"\s*[-–]\s*", t, maxsplit=1)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            m_asal, m_tujuan = parts[0].strip(), parts[1].strip()
        else:
            # Try two consecutive words / phrases after removing filler
            words = re.sub(r"\b(tiket|kereta|mau|minta|tolong|cari|ke|dari|menuju)\b", "", t).split()
            words = [w for w in words if w]
            if len(words) >= 2:
                # Simple: first half = asal, second half = tujuan
                mid = len(words) // 2
                m_asal, m_tujuan = " ".join(words[:mid]), " ".join(words[mid:])
            else:
                return None
    else:
        m_asal, m_tujuan = m.group(1).strip(), m.group(2).strip()

    # Expand aliases
    asal   = _normalize_city(m_asal)
    tujuan = _normalize_city(m_tujuan)
    return (asal, tujuan)


def _match_schedules(asal: str, tujuan: str, schedules: List[Dict]) -> List[Dict]:
    """Return schedules whose rute matches asal-tujuan (case-insensitive, partial)."""
    asal_n   = _norm(asal)
    tujuan_n = _norm(tujuan)
    matched = []
    for s in schedules:
        parts = re.split(r"\s*[-–]\s*", s["rute"], maxsplit=1)
        if len(parts) == 2:
            s_asal   = _norm(parts[0])
            s_tujuan = _norm(parts[1])
            if asal_n in s_asal and tujuan_n in s_tujuan:
                matched.append(s)
    return matched


# ── Boarding pass formatter ────────────────────────────────────────────────────

def _format_boarding_pass(kode: str, nama_penumpang: str, sched: Dict, seat: str) -> str:
    jam = _get_jam(sched["kereta"])
    return (
        f"✅ **Pemesanan Berhasil!** Tiket telah diterbitkan.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎫 **BOARDING PASS — KAI Digital**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 **Kode Booking :** `{kode}`\n"
        f"👤 **Penumpang    :** {nama_penumpang}\n"
        f"🚂 **Kereta       :** {sched['kereta']} ({sched['kelas']})\n"
        f"🗺️ **Rute         :** {sched['rute']}\n"
        f"🏠 **Stasiun Asal :** {jam['stasiun_asal']}\n"
        f"🏁 **Tujuan       :** {jam['stasiun_tujuan']}\n"
        f"🕐 **Berangkat    :** {jam['berangkat']}\n"
        f"🕐 **Tiba (est.)  :** {jam['tiba']}\n"
        f"💺 **Kursi        :** {seat}\n"
        f"💰 **Harga        :** Rp {sched['harga']:,.0f}\n"
        f"✔️  **Status       :** LUNAS\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"_Tunjukkan kode booking & KTP saat check-in di stasiun._\n"
        f"_Check-in paling lambat 30 menit sebelum keberangkatan._"
    )


def _format_schedule_list(schedules: List[Dict], rute_display: str, nama: str) -> str:
    jam_info = {s["kereta"]: _get_jam(s["kereta"]) for s in schedules}
    lines = [f"🚉 Rute **{rute_display}** — {len(schedules)} kereta tersedia:\n"]
    lines.append("| # | Kereta | Kelas | Berangkat | Tiba | Harga | Kursi |")
    lines.append("|---|--------|-------|-----------|------|-------|-------|")
    for i, s in enumerate(schedules, 1):
        j = jam_info[s["kereta"]]
        kursi_info = f"{s['sisa_kursi']} ✅" if s["sisa_kursi"] > 10 else (f"{s['sisa_kursi']} ⚠️" if s["sisa_kursi"] > 0 else "Habis ❌")
        lines.append(
            f"| {i} | {s['kereta']} | {s['kelas']} "
            f"| {j['berangkat']} | {j['tiba']} "
            f"| Rp {s['harga']:,.0f} | {kursi_info} |"
        )
    lines.append(f"\nKetik **nomor kereta** yang ingin Kak {nama} pesan, atau **'batal'** untuk membatalkan.")
    return "\n".join(lines)


# ── Main handler ───────────────────────────────────────────────────────────────

def handle_keretabot_response(user_input: str, username: str) -> str:
    """
    State machine chatbot engine for KeretaBot.
    Returns a response string (Markdown supported).
    """
    _ensure_bot_state()

    profile   = get_user_profile(username)
    nama      = profile["nama"] if profile else username
    raw       = user_input.strip()
    low       = raw.lower()
    norm_in   = _norm(raw)

    current_state: str = st.session_state.bot_state

    # ── Global: 'batal' / 'cancel' at any state ──────────────────────────────
    if norm_in in ("batal", "cancel", "keluar", "stop", "exit"):
        if current_state != STATE_IDLE:
            _reset()
            return (
                f"Baik, proses pemesanan dibatalkan, Kak {nama}. 🚂\n\n"
                f"Ada hal lain yang bisa saya bantu?\n"
                f"- Ketik **'pesan'** untuk memesan tiket\n"
                f"- Ketik **'tiket saya'** untuk riwayat pemesanan\n"
                f"- Ketik **'bantuan'** untuk melihat panduan"
            )
        else:
            return f"Tidak ada proses aktif saat ini, Kak {nama}. Ada yang bisa saya bantu? 🚂"

    # ── Global: 'bantuan' / 'help' / 'menu' ──────────────────────────────────
    if any(k in norm_in for k in ["bantuan", "help", "menu", "apa bisa", "bisa apa", "fitur"]):
        return (
            f"Halo Kak {nama}! 👋 Berikut yang bisa saya bantu:\n\n"
            f"🎫 **Pemesanan Tiket**\n"
            f"   → Ketik `pesan` atau `beli tiket`\n\n"
            f"🔍 **Cek Jadwal**\n"
            f"   → Ketik `jadwal Jakarta - Surabaya`\n\n"
            f"📋 **Riwayat Tiket**\n"
            f"   → Ketik `tiket saya`\n\n"
            f"❓ **Info & FAQ**\n"
            f"   → Tanya langsung: *cara batal*, *syarat naik*, *harga tiket*, dll.\n\n"
            f"🚂 KAI Digital siap melayani perjalanan Anda!"
        )

    # ── STATE: IDLE ───────────────────────────────────────────────────────────
    if current_state == STATE_IDLE:

        # Trigger: pesan / beli / booking
        if any(k in norm_in for k in ["pesan", "beli", "booking", "order", "beli tiket", "pesan tiket"]):
            # Cek apakah user sudah menyertakan rute dalam satu kalimat
            route = _parse_route_input(raw)
            schedules = get_all_jadwal()
            if route:
                asal, tujuan = route
                matched = _match_schedules(asal, tujuan, schedules)
                if matched:
                    rute_display = f"{asal} → {tujuan}"
                    st.session_state.bot_state = STATE_PILIH_KERETA
                    st.session_state.bot_context = {
                        "asal": asal, "tujuan": tujuan,
                        "rute_display": rute_display,
                        "matching_schedules": matched,
                    }
                    return _format_schedule_list(matched, rute_display, nama)

            # Tidak ada rute → minta rute
            all_routes = sorted(set(s["rute"] for s in schedules))
            route_list = "\n".join(f"  • {r}" for r in all_routes)
            st.session_state.bot_state = STATE_PILIH_RUTE
            st.session_state.bot_context = {}
            return (
                f"Siap memesan tiket, Kak {nama}! 🚂\n\n"
                f"Silakan masukkan rute perjalanan dengan format **Kota Asal - Kota Tujuan**.\n"
                f"Contoh: `Jakarta - Surabaya`\n\n"
                f"**Rute tersedia saat ini:**\n{route_list}"
            )

        # Trigger: jadwal [rute]
        if "jadwal" in norm_in:
            route = _parse_route_input(re.sub(r"\bjadwal\b", "", raw))
            if route:
                asal, tujuan = route
                matched = _match_schedules(asal, tujuan, get_all_jadwal())
                if matched:
                    return _format_schedule_list(matched, f"{asal} → {tujuan}", nama) + \
                           "\n\n_Ketik **'pesan'** jika ingin memesan tiket di rute ini._"
                else:
                    return (
                        f"Maaf Kak {nama}, rute **{asal} → {tujuan}** belum tersedia. 😔\n"
                        f"Ketik **'jadwal'** tanpa rute untuk melihat semua rute yang ada."
                    )
            else:
                # Tampilkan semua jadwal
                schedules = get_all_jadwal()
                all_routes = sorted(set(s["rute"] for s in schedules))
                route_list = "\n".join(f"  • {r}" for r in all_routes)
                return (
                    f"Berikut rute kereta yang tersedia, Kak {nama} 🚉:\n\n{route_list}\n\n"
                    f"Ketik `jadwal Jakarta - Surabaya` untuk melihat jadwal rute tertentu."
                )

        # Trigger: tiket saya / riwayat
        if any(k in norm_in for k in ["tiket saya", "riwayat", "history", "pemesanan saya", "tiket ku", "tiketku"]):
            bookings = get_user_bookings(username)
            if not bookings:
                return (
                    f"Kak {nama} belum memiliki riwayat tiket. 🎫\n\n"
                    f"Ketik **'pesan'** untuk memesan tiket pertama Anda!"
                )
            lines = [f"📋 **Riwayat Tiket Kak {nama}** ({len(bookings)} tiket):\n"]
            lines.append("| # | Kode | Kereta | Rute | Status |")
            lines.append("|---|------|--------|------|--------|")
            for i, b in enumerate(bookings, 1):
                lines.append(f"| {i} | `{b['kode']}` | {b['kereta']} | {b['rute']} | **{b['status']}** |")
            lines.append("\nKetik `cek [kode]` untuk melihat detail tiket.")
            return "\n".join(lines)

        # Trigger: cek [kode booking]
        m_cek = re.search(r"\bcek\b\s+(kai-\w+|train-\w+)", norm_in)
        if m_cek:
            kode_cari = m_cek.group(1).upper()
            bookings  = get_user_bookings(username)
            found     = next((b for b in bookings if b["kode"].upper() == kode_cari), None)
            if found:
                sched_match = next(
                    (s for s in get_all_jadwal()
                     if s["kereta"] == found["kereta"] and s["rute"] == found["rute"]),
                    None
                )
                if sched_match:
                    jam = _get_jam(found["kereta"])
                    return (
                        f"📋 **Detail Tiket `{kode_cari}`**\n\n"
                        f"👤 Pemesan   : {nama}\n"
                        f"🚂 Kereta    : {found['kereta']} ({sched_match['kelas']})\n"
                        f"🗺️ Rute      : {found['rute']}\n"
                        f"🕐 Berangkat : {jam['berangkat']}\n"
                        f"🕐 Tiba      : {jam['tiba']}\n"
                        f"✔️  Status    : **{found['status']}**"
                    )
                return f"Tiket `{kode_cari}` ditemukan: {found['kereta']} — {found['rute']} (**{found['status']}**)"
            return f"Kode booking `{kode_cari}` tidak ditemukan di riwayat Kak {nama}. 😔"

        # Sapaan
        if any(k in norm_in for k in ["halo", "hai", "hello", "hi", "selamat", "hei", "hey"]):
            return (
                f"Halo Kak {nama}! 👋 Selamat datang di **KeretaBot KAI Digital**. 🚂\n\n"
                f"Ada yang bisa saya bantu hari ini?\n"
                f"- Ketik **'pesan'** untuk memesan tiket\n"
                f"- Ketik **'jadwal'** untuk melihat jadwal kereta\n"
                f"- Ketik **'tiket saya'** untuk riwayat pemesanan\n"
                f"- Ketik **'bantuan'** untuk panduan lengkap"
            )

        # Cek FAQ
        faq_ans = _find_faq(raw, nama)
        if faq_ans:
            return faq_ans

        # Default
        return (
            f"Halo Kak {nama}! 🚂 Saya **KeretaBot**, asisten pemesanan tiket KAI Digital.\n\n"
            f"Ketik **'bantuan'** untuk melihat semua yang bisa saya bantu, "
            f"atau langsung ketik **'pesan'** untuk memesan tiket sekarang!"
        )

    # ── STATE: PILIH_RUTE ─────────────────────────────────────────────────────
    elif current_state == STATE_PILIH_RUTE:
        route = _parse_route_input(raw)
        schedules = get_all_jadwal()

        if not route:
            return (
                f"Maaf Kak {nama}, format rute belum terbaca. 😅\n"
                f"Coba ketik seperti ini: **Jakarta - Surabaya** atau **dari Jakarta ke Surabaya**."
            )

        asal, tujuan = route
        matched = _match_schedules(asal, tujuan, schedules)

        if not matched:
            all_routes = sorted(set(s["rute"] for s in schedules))
            route_list = "\n".join(f"  • {r}" for r in all_routes)
            return (
                f"Maaf Kak {nama}, rute **{asal} → {tujuan}** belum tersedia. 😔\n\n"
                f"**Rute yang tersedia:**\n{route_list}\n\n"
                f"Silakan coba rute lain, atau ketik **'batal'** untuk membatalkan."
            )

        rute_display = f"{asal} → {tujuan}"
        st.session_state.bot_state = STATE_PILIH_KERETA
        st.session_state.bot_context.update({
            "asal": asal, "tujuan": tujuan,
            "rute_display": rute_display,
            "matching_schedules": matched,
        })
        return _format_schedule_list(matched, rute_display, nama)

    # ── STATE: PILIH_KERETA ───────────────────────────────────────────────────
    elif current_state == STATE_PILIH_KERETA:
        matched = st.session_state.bot_context.get("matching_schedules", [])
        rute_display = st.session_state.bot_context.get("rute_display", "")

        try:
            idx = int(raw.strip())
        except ValueError:
            return (
                f"Masukkan **nomor kereta** (angka), Kak {nama}. "
                f"Contoh: `1`, `2`, dst. Atau ketik **'batal'** untuk membatalkan."
            )

        if not (1 <= idx <= len(matched)):
            return (
                f"Nomor tidak valid. Pilih antara **1** sampai **{len(matched)}**, "
                f"atau ketik **'batal'** untuk membatalkan."
            )

        selected = matched[idx - 1]

        if selected["sisa_kursi"] <= 0:
            return (
                f"Maaf Kak {nama}, kursi **{selected['kereta']}** sudah habis. 😔\n"
                f"Silakan pilih kereta lain (ketik nomornya)."
            )

        jam = _get_jam(selected["kereta"])
        st.session_state.bot_context["selected_sched"] = selected
        st.session_state.bot_state = STATE_ISI_PENUMPANG

        return (
            f"Oke! Kak {nama} memilih:\n\n"
            f"🚂 **{selected['kereta']}** ({selected['kelas']})\n"
            f"🗺️ Rute      : **{selected['rute']}**\n"
            f"🏠 Asal      : {jam['stasiun_asal']}  →  🏁 {jam['stasiun_tujuan']}\n"
            f"🕐 Berangkat : **{jam['berangkat']}**  •  Tiba: **{jam['tiba']}**\n"
            f"💰 Harga     : **Rp {selected['harga']:,.0f}**\n"
            f"💺 Sisa Kursi: {selected['sisa_kursi']} kursi\n\n"
            f"Silakan masukkan **nama lengkap penumpang** sesuai KTP:"
        )

    # ── STATE: ISI_PENUMPANG ──────────────────────────────────────────────────
    elif current_state == STATE_ISI_PENUMPANG:
        nama_penumpang = raw.strip()

        if len(nama_penumpang) < 3:
            return "Nama penumpang terlalu pendek. Masukkan nama lengkap sesuai KTP:"

        if not re.match(r"^[A-Za-z\s\.\-']+$", nama_penumpang):
            return (
                "Nama penumpang hanya boleh berisi huruf dan spasi. "
                "Silakan masukkan nama lengkap yang valid:"
            )

        selected = st.session_state.bot_context.get("selected_sched", {})
        jam      = _get_jam(selected.get("kereta", ""))
        seat     = generate_seat_number(selected.get("kelas", "Ekonomi"))

        st.session_state.bot_context["nama_penumpang"] = nama_penumpang
        st.session_state.bot_context["seat"]           = seat
        st.session_state.bot_state = STATE_KONFIRMASI

        return (
            f"📋 **Ringkasan Pemesanan — Mohon periksa kembali:**\n\n"
            f"👤 Penumpang  : **{nama_penumpang}**\n"
            f"🚂 Kereta     : **{selected['kereta']}** ({selected['kelas']})\n"
            f"🗺️ Rute       : **{selected['rute']}**\n"
            f"🕐 Berangkat  : **{jam['berangkat']}**  •  Tiba: **{jam['tiba']}**\n"
            f"💺 Kursi      : **{seat}**\n"
            f"💰 Total Bayar: **Rp {selected['harga']:,.0f}**\n\n"
            f"Ketik **`ya`** untuk konfirmasi pemesanan, atau **`tidak`** / **`batal`** untuk membatalkan."
        )

    # ── STATE: KONFIRMASI ─────────────────────────────────────────────────────
    elif current_state == STATE_KONFIRMASI:
        if norm_in in ("ya", "yes", "iya", "ok", "oke", "setuju", "lanjut", "konfirmasi", "bayar"):
            selected        = st.session_state.bot_context.get("selected_sched", {})
            nama_penumpang  = st.session_state.bot_context.get("nama_penumpang", nama)
            seat            = st.session_state.bot_context.get("seat", "A1")

            # Final seat availability check
            fresh = next(
                (s for s in get_all_jadwal() if s["id"] == selected.get("id")),
                None
            )
            if not fresh or fresh["sisa_kursi"] <= 0:
                _reset()
                return (
                    f"Maaf Kak {nama}, kursi **{selected.get('kereta','')}** baru saja habis terjual. 😔\n"
                    f"Ketik **'pesan'** untuk mencoba kereta lain."
                )

            kode     = generate_booking_code()
            new_sisa = fresh["sisa_kursi"] - 1

            update_sisa_kursi(selected["id"], new_sisa)
            result = add_booking(
                username=username,
                kode=kode,
                kereta=selected["kereta"],
                rute=selected["rute"],
                status="Lunas",
            )

            _reset()

            if result:
                return _format_boarding_pass(kode, nama_penumpang, selected, seat)
            else:
                return (
                    "Maaf Kak, terjadi kesalahan sistem saat menerbitkan tiket. "
                    "Transaksi dibatalkan. Silakan coba lagi. 🚂"
                )

        elif norm_in in ("tidak", "no", "nggak", "ngga", "ga", "enggak", "batal"):
            _reset()
            return (
                f"Pemesanan dibatalkan, Kak {nama}. Tidak ada yang dikenakan biaya. 🚂\n\n"
                f"Ketik **'pesan'** jika ingin memesan ulang."
            )
        else:
            return (
                f"Ketik **`ya`** untuk melanjutkan pembayaran, "
                f"atau **`tidak`** / **`batal`** untuk membatalkan pemesanan."
            )

    # Fallback
    _reset()
    return (
        f"Terjadi kesalahan sesi, Kak {nama}. Sesi direset. 🚂\n"
        f"Ketik **'pesan'** untuk memulai pemesanan baru."
    )


# ── Session init ───────────────────────────────────────────────────────────────

def init_bot_session(username: str):
    _ensure_bot_state()
    if "chat_history" not in st.session_state:
        profile   = get_user_profile(username)
        nama_user = profile["nama"] if profile else username
        st.session_state.chat_history = [
            {
                "role": "assistant",
                "content": (
                    f"Halo Kak **{nama_user}**! 👋 Selamat datang di **KeretaBot KAI Digital**. 🚂\n\n"
                    f"Saya siap membantu perjalanan Anda hari ini.\n\n"
                    f"🎫 Ketik **`pesan`** untuk memesan tiket\n"
                    f"🔍 Ketik **`jadwal`** untuk melihat jadwal kereta\n"
                    f"📋 Ketik **`tiket saya`** untuk riwayat pemesanan\n"
                    f"❓ Ketik **`bantuan`** untuk panduan lengkap"
                ),
            }
        ]
