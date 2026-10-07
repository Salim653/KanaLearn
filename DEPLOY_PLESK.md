# Deploy ke UB BITS Plesk

Panduan deploy Kana Chat ke layanan **UB BITS Web Hosting (Plesk)** — primary target.

## Prasyarat

1. Akun layanan UB BITS Web Hosting aktif (subdomain `<nama>.ub.ac.id`).
2. Akses panel Plesk.
3. Database MySQL/MariaDB dibuat di Plesk; catat:
   - host/server
   - database name
   - user
   - password
4. Python 3.10 tersedia di Plesk (atau minimal Python 3.x yang didukung).

## Variabel lingkungan production

Buat file `.env` di root project jika belum ada:

```env
FLASK_CONFIG=production
SECRET_KEY=<64-char-hex-dari-secrets.token_hex(32)>
DATABASE_URL=mysql+pymysql://USER:PASSWORD@HOST/DB_NAME
```

`SECRET_KEY` wajib diganti; value default development tidak boleh dipakai di production.

## Persiapan lokal

```bash
cd /d/!!STUDYKANA/kana-chat-flask
export FLASK_APP=wsgi.py FLASK_CONFIG=production PYTHONNOUSERSITE=1
/c/Users/Salim/.conda/envs/kanachat/python.exe -m flask db upgrade
/c/Users/Salim/.conda/envs/kanachat/python.exe -m flask seed-content
/c/Users/Salim/.conda/envs/kanachat/python.exe -m flask create-admin admin_admin <password>
```

Catatan: `seed-content` akan membuat 92 kana, 4 karakter, 22 baris gojūon, 4 chat, 18 langkah, plus unit+pelajaran kuis (66 pelajaran).

## Langkah deploy di Plesk

1. **Git deploy**
   - Di Plesk, aktifkan Git untuk domain dan arahkan ke repo ini.
   - Pull branch utama ke folder hosting.
   - Pastikan `migrations/`, `seed/`, `requirements.txt`, `wsgi.py`, dan `.env` ikut terdeploy.

2. **Setup Python app**
   - Di Plesk → domain → **Python**.
   - Pilih **Application root**: folder tempat `wsgi.py` berada (biasanya root domain).
   - **Application startup file**: `wsgi.py`
   - **Application entry point**: `application` (atau `app` — `wsgi.py` mengekspor keduanya).
   - Pilih Python 3.10 jika tersedia.
   - Jalankan **Install dependencies** dari `requirements.txt`.

3. **Environment variables**
   - Masukkan `FLASK_CONFIG=production` dan `DATABASE_URL` di bagian environment variables Plesk.
   - Jangan masukkan `SECRET_KEY` ke Git; tambahkan via Plesk environment variables.

4. **Database**
   - Jalankan migrations sekali di server. Plesk biasanya menyediakan akses SSH:
     ```bash
     cd /var/www/vhosts/<domain>/httpdocs
     python -m flask db upgrade
     python -m flask seed-content
     python -m flask create-admin admin_admin <password>
     ```
   - Jika tidak ada SSH, unggah `dev.sqlite3` yang sudah di-seed tidak disarankan untuk production (file SQLite tidak ideal di Plesk). Prioritaskan MySQL.

5. **Restart app**
   - Klik **Restart** di panel Python Plesk.
   - Buka `/healthz` — harus mengembalikan `{"status":"ok"}`.

## Cek cepat setelah deploy

- `/healthz` → ok
- `/` → home Kana Chat
- `/register` → daftar akun baru
- `/admin/` → login admin
- `/content/` → editor konten (guru/admin)
- `/chat/` → chat simulator
- `/quiz/` → jalur kuis
- `/dojo/` → Dojo Menulis

## Fallback: PythonAnywhere

Kalau UB BITS tidak memenuhi salah satu prasyarat (eligibility/MySQL/Python/outbound), fallback ke PythonAnywhere:

- Buat web app Python 3.10 + Flask.
- WSGI file arahkan ke `wsgi.py`.
- Set `DATABASE_URL` dengan MySQL dari PythonAnywhere.
- Perhatikan outbound whitelist kalau menambahkan P9 AI nanti.

## Open items (konfirmasi)

- [ ] Eligibility path: domain ub.ac.id untuk unit resmi UB (Anda di UM; butuh route resmi).
- [ ] MySQL/MariaDB tersedia di Plesk.
- [ ] Python 3.10 tersedia.
- [ ] Outbound HTTPS bebas untuk API eksternal (hanya perlu jika P9 AI).
