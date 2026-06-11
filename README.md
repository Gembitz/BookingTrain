# 🚆 KAI Digital — Sistem Ticketing Kereta Api

Aplikasi pemesanan tiket kereta api terintegrasi dengan chatbot, panel admin, dan koneksi Supabase.

---

## �️ Struktur Proyek

```
Kereta/
├── app.py                      # Entry point Streamlit
├── requirements.txt
├── supabase_schema.sql         # Jalankan ini di Supabase SQL Editor
├── .env                        # Kredensial lokal (jangan di-commit)
├── .gitignore
├── .streamlit/
│   ├── config.toml             # Tema & server config
│   └── secrets.toml            # Secrets lokal (jangan di-commit)
└── src/
    ├── chatbot/bot_engine.py   # State machine chatbot
    ├── admin/admin_panel.py    # Panel manajemen admin
    ├── user/
    │   ├── manual_form.py      # Form pemesanan manual
    │   └── profile_settings.py
    └── database/
        └── supabase_client.py  # Koneksi DB + fallback simulasi
```

---

## ⚙️ Setup Database Supabase

### 1. Buat project baru di [supabase.com](https://supabase.com)

### 2. Jalankan SQL schema
Buka **SQL Editor** di dashboard Supabase, paste seluruh isi `supabase_schema.sql`, lalu klik **Run**.

Schema ini akan:
- Membuat tabel `users`, `jadwal`, `bookings`
- Mengisi data awal (seed data)
- Menonaktifkan RLS agar aplikasi bisa baca/tulis

### 3. Ambil kredensial
Buka **Project Settings → API**, salin:
- `Project URL` → `SUPABASE_URL`
- `anon public` key → `SUPABASE_KEY`

---

## 🖥️ Menjalankan Secara Lokal

```bash
# Install dependencies
pip install -r requirements.txt

# Isi kredensial di .streamlit/secrets.toml
# (sudah ada templatenya, tinggal sesuaikan)

# Jalankan aplikasi
streamlit run app.py
```

Jika Supabase tidak tersambung, aplikasi otomatis beralih ke **mode simulasi offline** menggunakan data bawaan.

---

## 🚀 Deploy ke Streamlit Cloud

### 1. Push ke GitHub
Pastikan `.gitignore` sudah ada sehingga **`.env`** dan **`.streamlit/secrets.toml`** tidak ikut ter-push.

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/username/nama-repo.git
git push -u origin main
```

### 2. Deploy di [share.streamlit.io](https://share.streamlit.io)
- Klik **New app**
- Pilih repository dan branch
- Main file path: `app.py`
- Klik **Advanced settings → Secrets**, tempel:

```toml
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_KEY = "eyJ..."
```

### 3. Deploy!
Klik **Deploy** — selesai. Streamlit Cloud akan membaca secrets dari dashboard, bukan dari file.

---

## � Akun Default (Mode Simulasi / Supabase)

| Username | Password  | Role  |
|----------|-----------|-------|
| `admin`  | `admin123`| Admin |
| `dion`   | `12345`   | User  |
| `budi`   | `12345`   | User  |

---

## 🔌 Logika Koneksi Database

```
Streamlit Cloud  →  baca dari st.secrets
Development lokal  →  baca dari .streamlit/secrets.toml atau .env
Koneksi gagal  →  otomatis fallback ke data simulasi (session_state)
```

Tidak perlu mengubah kode apapun antara mode lokal dan deployment.
