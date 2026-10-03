# Mindful Space

Counsellors across India, daily wellbeing practices and a kind community.
Flask + SQLite backend, single-page frontend (no build step).

## Run locally
```
pip install -r requirements.txt
cp .env.example .env        # then edit it
python app.py               # http://127.0.0.1:5000
```
Counsellor review page: http://127.0.0.1:5000/admin.html (enter your ADMIN_TOKEN).

## What is real
- Accounts, sessions, phone-OTP login, counsellor registration, bookings, friends, community, journal, habits and wellness score are all stored in SQLite (`mindful.db`).
- Two-way chat between real accounts (polling every ~3.5s). Counsellors can reply to anyone who booked or messaged them.
- Counsellor IDs: the format is validated, accounts start as `pending`, and a counsellor appears in search only after you approve them at `/admin.html`. Verify the ID against the official register (RCI CRR, state medical council) before approving.
- Helplines tab: real public helplines and institutions (Tele-MANAS, KIRAN, Vandrevala, Fortis, NIMHANS, iCall, AASRA, Sneha, Connecting Trust, Parivarthan, One Life). Hours change, so re-check them before launch.

## What you must do before a public launch
1. **Real SMS OTP.** Set `SMS_PROVIDER=msg91` (recommended for India, handles DLT templates) or `twilio`, add the keys in `.env`, and set `DEV_SHOW_OTP=0`. With `console`, the code is only printed in the server log (and shown in the app if `DEV_SHOW_OTP=1`). Check the MSG91 call against their current docs.
2. **Real counsellors.** Set `SEED_DEMO=0` to remove sample counsellors and community members (delete `mindful.db` first if it was already seeded). Sample counsellors have no contact details. Real counsellors tick "show my contact" at sign-up so their phone, WhatsApp and email appear on their card.
3. **Payments.** Bookings are settled directly between client and counsellor. Add Razorpay if you want in-app payments.
4. **Hosting.** `gunicorn -w 2 app:app` behind HTTPS, set `SECRET_KEY`, `COOKIE_SECURE=1`, `ADMIN_TOKEN`. SQLite is fine for a pilot; move to Postgres for scale.
5. **Compliance.** India's DPDP Act: add a privacy policy and consent text, and keep the "Delete my account" flow. Get legal advice on handling health-related data and on telemedicine rules for counsellors and psychiatrists.
6. **Safety.** Posts, journal entries and messages containing crisis phrases trigger a helpline pop-up. Add human moderation before opening the community to the public.
