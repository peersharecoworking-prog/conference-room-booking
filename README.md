# Conference Room Self-Service Booking

A lightweight Flask + SQLite booking app for one coworking-space conference room.

## Run locally
1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Run `python -m venv .venv`
4. Activate it:
   - Windows: `.venv\Scripts\activate`
   - macOS/Linux: `source .venv/bin/activate`
5. Run `pip install -r requirements.txt`
6. Set a strong admin password and secret key before first launch:
   - Windows PowerShell: `$env:ADMIN_PASSWORD="Use-A-Strong-Password"; $env:SECRET_KEY="a-long-random-secret"`
   - macOS/Linux: `export ADMIN_PASSWORD="Use-A-Strong-Password"; export SECRET_KEY="a-long-random-secret"`
7. Run `python app.py`
8. Open `http://127.0.0.1:5000`

Admin: `http://127.0.0.1:5000/admin/login`

## Important deployment notes
- This is a working starter application, not yet a hosted public service. To let clients book from their own phones, deploy it to a Python-capable hosting provider and use a persistent disk for `bookings.db`.
- Do not deploy with the default admin password. Set `ADMIN_PASSWORD` and `SECRET_KEY` as hosting environment variables before first launch.
- Use HTTPS in production. Back up `bookings.db` regularly.
- SQLite is suitable for a small single-room coworking space. For high traffic or multiple app instances, move to PostgreSQL.
- Booking confirmations appear on screen. Email/WhatsApp notifications, online payments, and self-service cancellation links are not included in this first version.
- The app uses the server's local date/time. Configure the hosting server to Asia/Kolkata for India-based operations.
