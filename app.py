"""Mindful Space backend: Flask + SQLite.
Run:  pip install -r requirements.txt && python app.py   ->  http://127.0.0.1:5000
"""
import os, re, json, math, time, hmac, base64, random, sqlite3, secrets, hashlib
import urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, request, jsonify, session, g, send_from_directory

BASE = os.path.dirname(os.path.abspath(__file__))

def load_env():
    p = os.path.join(BASE, '.env')
    if os.path.exists(p):
        for line in open(p, encoding='utf-8'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())
load_env()

DB_PATH = os.environ.get('DATABASE', os.path.join(BASE, 'mindful.db'))
if not os.path.isabs(DB_PATH):
    DB_PATH = os.path.join(BASE, DB_PATH)
IST = timezone(timedelta(hours=5, minutes=30))

def secret_key():
    k = os.environ.get('SECRET_KEY')
    if k:
        return k
    p = os.path.join(BASE, '.secret_key')
    if not os.path.exists(p):
        open(p, 'w').write(secrets.token_hex(32))
    return open(p).read().strip()

app = Flask(__name__, static_folder='static', static_url_path='')
app.secret_key = secret_key()
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                  SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE', '0') == '1',
                  PERMANENT_SESSION_LIFETIME=timedelta(days=30), MAX_CONTENT_LENGTH=256 * 1024)

# ---------------------------------------------------------------- data
CITIES = [
 ('Delhi','Delhi',28.61,77.21,'N',['Hindi','English','Punjabi']),('Gurugram','Haryana',28.46,77.03,'N',['Hindi','English']),
 ('Noida','Uttar Pradesh',28.54,77.39,'N',['Hindi','English']),('Mumbai','Maharashtra',19.08,72.88,'W',['Hindi','Marathi','English']),
 ('Thane','Maharashtra',19.22,72.98,'W',['Marathi','Hindi','English']),('Pune','Maharashtra',18.52,73.86,'W',['Marathi','Hindi','English']),
 ('Nagpur','Maharashtra',21.15,79.09,'W',['Marathi','Hindi','English']),('Nashik','Maharashtra',20.0,73.79,'W',['Marathi','Hindi','English']),
 ('Aurangabad','Maharashtra',19.88,75.34,'W',['Marathi','Hindi','English']),('Bengaluru','Karnataka',12.97,77.59,'S',['Kannada','English','Hindi']),
 ('Mysuru','Karnataka',12.3,76.64,'S',['Kannada','English']),('Hyderabad','Telangana',17.39,78.49,'S',['Telugu','Hindi','English','Urdu']),
 ('Visakhapatnam','Andhra Pradesh',17.69,83.22,'S',['Telugu','English']),('Chennai','Tamil Nadu',13.08,80.27,'S',['Tamil','English']),
 ('Coimbatore','Tamil Nadu',11.02,76.96,'S',['Tamil','English']),('Madurai','Tamil Nadu',9.93,78.12,'S',['Tamil','English']),
 ('Kochi','Kerala',9.93,76.27,'S',['Malayalam','English']),('Thiruvananthapuram','Kerala',8.52,76.94,'S',['Malayalam','English']),
 ('Kolkata','West Bengal',22.57,88.36,'E',['Bengali','Hindi','English']),('Bhubaneswar','Odisha',20.3,85.82,'E',['Odia','Hindi','English']),
 ('Guwahati','Assam',26.14,91.74,'E',['Assamese','Hindi','English']),('Patna','Bihar',25.59,85.14,'E',['Hindi','English']),
 ('Ranchi','Jharkhand',23.34,85.31,'E',['Hindi','English']),('Ahmedabad','Gujarat',23.02,72.57,'W',['Gujarati','Hindi','English']),
 ('Surat','Gujarat',21.17,72.83,'W',['Gujarati','Hindi','English']),('Vadodara','Gujarat',22.31,73.18,'W',['Gujarati','Hindi','English']),
 ('Jaipur','Rajasthan',26.91,75.79,'N',['Hindi','English']),('Jodhpur','Rajasthan',26.24,73.02,'N',['Hindi','English']),
 ('Lucknow','Uttar Pradesh',26.85,80.95,'N',['Hindi','English','Urdu']),('Kanpur','Uttar Pradesh',26.45,80.33,'N',['Hindi','English']),
 ('Varanasi','Uttar Pradesh',25.32,82.97,'N',['Hindi','English']),('Indore','Madhya Pradesh',22.72,75.86,'W',['Hindi','English']),
 ('Bhopal','Madhya Pradesh',23.26,77.41,'W',['Hindi','English']),('Raipur','Chhattisgarh',21.25,81.63,'W',['Hindi','English']),
 ('Chandigarh','Chandigarh',30.73,76.78,'N',['Hindi','Punjabi','English']),('Amritsar','Punjab',31.63,74.87,'N',['Punjabi','Hindi','English']),
 ('Dehradun','Uttarakhand',30.32,78.03,'N',['Hindi','English']),('Shimla','Himachal Pradesh',31.1,77.17,'N',['Hindi','English']),
 ('Srinagar','Jammu & Kashmir',34.08,74.8,'N',['Urdu','Hindi','English']),('Panaji','Goa',15.49,73.83,'W',['Konkani','English','Hindi'])]
CITY = {c[0]: c for c in CITIES}

# Real public helplines / institutions, cross-checked against government and NGO directories.
HELPLINES = [
 {'name':'Tele-MANAS (Govt. of India)','city':'All India','phone':'14416','alt':'1800-891-4416','hours':'24x7, free, 20 languages','kind':'Government helpline'},
 {'name':'KIRAN Mental Health Helpline','city':'All India','phone':'18005990019','alt':'1800-599-0019','hours':'24x7, free','kind':'Government helpline'},
 {'name':'Vandrevala Foundation','city':'All India','phone':'+919999666555','alt':'+91 9999 666 555','hours':'24x7 (also on WhatsApp)','kind':'NGO helpline'},
 {'name':'Fortis Stress Helpline','city':'All India','phone':'+918376804102','alt':'+91 83768 04102','hours':'24x7, multilingual','kind':'Hospital helpline'},
 {'name':'NIMHANS Helpline','city':'Bengaluru','phone':'08046110007','alt':'080-46110007','hours':'Check current hours','kind':'Institute'},
 {'name':'iCall (TISS)','city':'Mumbai','phone':'02225521111','alt':'022-25521111','hours':'Mon-Sat, daytime; email icall@tiss.edu','kind':'Counselling helpline'},
 {'name':'AASRA','city':'Mumbai','phone':'+919820466726','alt':'+91 98204 66726','hours':'24x7','kind':'NGO helpline'},
 {'name':'Sneha','city':'Chennai','phone':'04424640050','alt':'044 2464 0050','hours':'Check current hours','kind':'NGO helpline'},
 {'name':'Connecting Trust','city':'Pune','phone':'9922001122','alt':'99220 01122','hours':'Daily, daytime','kind':'NGO helpline'},
 {'name':'Parivarthan Counselling Helpline','city':'Bengaluru','phone':'+917676602602','alt':'7676 602 602','hours':'Weekdays, afternoon-evening','kind':'Counselling helpline'},
 {'name':'One Life Helpline','city':'Hyderabad','phone':'7893078930','alt':'78930 78930','hours':'24x7','kind':'NGO helpline'},
 {'name':'Emergency (police, fire, ambulance)','city':'All India','phone':'112','alt':'112','hours':'24x7','kind':'Emergency'}]

NAMES = {
 'N': (['Aarav','Ananya','Kavya','Rohan','Ishita','Vikram','Neha','Arjun','Priya','Siddharth','Meera','Kabir','Simran','Harpreet','Pooja','Aditi','Manish','Nisha'],
       ['Sharma','Verma','Kapoor','Singh','Malhotra','Gupta','Chopra','Mehra','Bhatia','Saxena','Tiwari','Khanna']),
 'S': (['Lakshmi','Karthik','Divya','Suresh','Anjali','Arvind','Meenakshi','Praveen','Deepa','Naveen','Revathi','Harish','Sowmya','Vignesh','Nandini'],
       ['Iyer','Nair','Reddy','Krishnan','Menon','Rao','Pillai','Subramanian','Naidu','Varghese','Gowda','Kurup']),
 'E': (['Sourav','Ritika','Debasish','Moumita','Anindya','Sreya','Subhajit','Tanushree','Bikram','Pallavi','Arunima','Rajib'],
       ['Banerjee','Chatterjee','Das','Ghosh','Mukherjee','Sen','Mohapatra','Bora','Dutta','Saha','Mishra','Jha']),
 'W': (['Hetal','Jignesh','Sneha','Omkar','Rutuja','Chirag','Pranav','Mansi','Tejas','Shruti','Nilesh','Kiran','Gauri','Aniket'],
       ['Patel','Joshi','Kulkarni','Deshmukh','Shah','Mehta','Desai','Patil','Pawar','Naik','Bhosale','Trivedi'])}
TITLES = ['Clinical Psychologist','Counselling Psychologist','Psychiatrist','Psychotherapist','Child & Adolescent Counsellor','Couples & Family Therapist','Rehabilitation Psychologist']
SPECS = ['Anxiety','Depression','Stress & burnout','Relationships','Grief & loss','Trauma & PTSD','OCD','Sleep issues','Exam & career stress','Addiction recovery','Teen mental health','Self-esteem','Postpartum wellbeing','LGBTQ+ affirming','Anger management']
AREAS = ['Civil Lines','MG Road','Model Town','Sector 14','Residency Road','Old Town','Lakeview','Central Market','Ring Road','Garden Colony','Station Road','Hill View']
LANGS = ['English','Hindi','Marathi','Gujarati','Bengali','Tamil','Telugu','Kannada','Malayalam','Punjabi','Odia','Assamese','Urdu','Konkani']
MODES = ['Video', 'Audio', 'In-person']
SLOTS = ['10:00', '11:30', '14:00', '16:30', '18:00', '19:30']
PRACTICES = {'breathing', 'grounding', 'gratitude', 'stretch', 'sound'}
COUNCILS = ['Rehabilitation Council of India (RCI)', 'National Medical Commission / State Medical Council', 'Other recognised body']
CRISIS_RE = re.compile(r"(suicid|kill myself|end my life|want to die|don'?t want to live|self[- ]?harm|hurt myself|cut myself)", re.I)
PHONE_RE = re.compile(r'^[6-9]\d{9}$')

# ---------------------------------------------------------------- db
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT UNIQUE NOT NULL, role TEXT NOT NULL CHECK(role IN('user','counsellor')),
 name TEXT NOT NULL, nick TEXT NOT NULL, nick_lc TEXT NOT NULL, age INTEGER, gender TEXT, city TEXT, lat REAL, lng REAL,
 langs TEXT DEFAULT '[]', concerns TEXT DEFAULT '[]', mode_pref TEXT, em_name TEXT, em_phone TEXT,
 is_demo INTEGER DEFAULT 0, created REAL NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ux_nick ON users(nick_lc) WHERE role='user';
CREATE TABLE IF NOT EXISTS counsellors(
 user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, title TEXT, council TEXT, reg_id TEXT UNIQUE, qual TEXT,
 area TEXT, exp INTEGER, spec TEXT, langs TEXT, modes TEXT, fee INTEGER, bio TEXT, email TEXT, contact_phone TEXT,
 show_contact INTEGER DEFAULT 0, avail INTEGER DEFAULT 1, status TEXT DEFAULT 'pending',
 rating_avg REAL DEFAULT 0, rating_count INTEGER DEFAULT 0, lat REAL, lng REAL);
CREATE TABLE IF NOT EXISTS otps(id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT NOT NULL, code_hash TEXT NOT NULL,
 expires REAL NOT NULL, attempts INTEGER DEFAULT 0, used INTEGER DEFAULT 0, created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ix_otp_phone ON otps(phone, created);
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT, from_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 to_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, body TEXT NOT NULL, ts REAL NOT NULL, read INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_msg_pair ON messages(from_id, to_id, ts);
CREATE TABLE IF NOT EXISTS friends(user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 friend_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, status TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(user_id, friend_id));
CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 body TEXT NOT NULL, tag TEXT, ts REAL NOT NULL, seed_support INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS post_support(post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, PRIMARY KEY(post_id, user_id));
CREATE TABLE IF NOT EXISTS bookings(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 counsellor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, date TEXT NOT NULL, time TEXT NOT NULL, mode TEXT NOT NULL,
 fee INTEGER NOT NULL, status TEXT NOT NULL, payment TEXT DEFAULT 'pay_at_session', created REAL NOT NULL, rating INTEGER, review TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS ux_slot ON bookings(counsellor_id, date, time) WHERE status IN ('requested','confirmed');
CREATE TABLE IF NOT EXISTS habits(user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, day TEXT NOT NULL,
 water INTEGER DEFAULT 0, sleep REAL DEFAULT 0, move INTEGER DEFAULT 0, PRIMARY KEY(user_id, day));
CREATE TABLE IF NOT EXISTS journal(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 body TEXT NOT NULL, ts REAL NOT NULL);
CREATE TABLE IF NOT EXISTS practice(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 kind TEXT NOT NULL, seconds INTEGER NOT NULL, day TEXT NOT NULL, ts REAL NOT NULL);
"""

def db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
    return g.db

@app.teardown_appcontext
def close_db(_):
    d = g.pop('db', None)
    if d:
        d.close()

def q(sql, args=(), one=False):
    cur = db().execute(sql, args)
    rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows

def ex(sql, args=()):
    cur = db().execute(sql, args)
    db().commit()
    return cur.lastrowid

def J(v):
    return json.dumps(v, ensure_ascii=False)

def L(s):
    try:
        return json.loads(s or '[]')
    except Exception:
        return []

def today_ist():
    return datetime.now(IST).strftime('%Y-%m-%d')

def haversine(a, b, c, d):
    r = lambda x: x * math.pi / 180
    x = math.sin(r(c - a) / 2) ** 2 + math.cos(r(a)) * math.cos(r(c)) * math.sin(r(d - b) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(x))

# ---------------------------------------------------------------- helpers
def err(msg, code=400):
    return jsonify(error=msg), code

def me():
    if 'me' not in g:
        uid = session.get('uid')
        g.me = q('SELECT * FROM users WHERE id=?', (uid,), one=True) if uid else None
    return g.me

def auth(role=None):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            u = me()
            if not u:
                return err('Please sign in.', 401)
            if role and u['role'] != role:
                return err('Not allowed for your account type.', 403)
            return f(*a, **k)
        return w
    return deco

@app.before_request
def csrf_guard():
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and request.path.startswith('/api/') \
            and not request.path.startswith('/api/admin/') and not request.is_json:
        return err('JSON body required.', 415)

@app.after_request
def headers(r):
    r.headers['X-Content-Type-Options'] = 'nosniff'
    r.headers['X-Frame-Options'] = 'DENY'
    r.headers['Referrer-Policy'] = 'same-origin'
    r.headers['Permissions-Policy'] = 'geolocation=(self)'
    if request.path.startswith('/api/'):
        r.headers['Cache-Control'] = 'no-store'
    return r

def body():
    return request.get_json(silent=True) or {}

def clean(s, n=200):
    return re.sub(r'\s+', ' ', str(s or '')).strip()[:n]

def pick(vals, allowed, mx=20):
    return [v for v in dict.fromkeys(vals or []) if v in allowed][:mx]

def valid_reg_id(rid):
    rid = re.sub(r'\s', '', str(rid or '')).upper()
    return rid if re.match(r'^[A-Z0-9][A-Z0-9/\-]{5,19}$', rid) and len(re.findall(r'\d', rid)) >= 4 else None

def user_dict(u):
    d = {'id': u['id'], 'role': u['role'], 'name': u['name'], 'nick': u['nick'], 'phone': u['phone'], 'age': u['age'], 'gender': u['gender'],
         'city': u['city'], 'lat': u['lat'], 'lng': u['lng'], 'langs': L(u['langs']), 'concerns': L(u['concerns']),
         'mode_pref': u['mode_pref'], 'em_name': u['em_name'], 'em_phone': u['em_phone']}
    if u['role'] == 'counsellor':
        d['counsellor'] = counsellor_dict(q('SELECT c.*, u.name, u.city, u.is_demo FROM counsellors c JOIN users u ON u.id=c.user_id WHERE c.user_id=?', (u['id'],), one=True), True)
    return d

def counsellor_dict(c, own=False, origin=None):
    contact = None
    if own or (c['show_contact'] and not c['is_demo']):
        contact = {'phone': c['contact_phone'], 'email': c['email']}
    city = CITY.get(c['city'])
    d = {'id': c['user_id'], 'name': c['name'], 'title': c['title'], 'council': c['council'], 'qual': c['qual'], 'area': c['area'], 'city': c['city'],
         'state': city[1] if city else '', 'exp': c['exp'], 'spec': L(c['spec']), 'langs': L(c['langs']), 'modes': L(c['modes']), 'fee': c['fee'],
         'bio': c['bio'], 'avail': bool(c['avail']), 'status': c['status'], 'rating': round(c['rating_avg'], 1), 'reviews': c['rating_count'],
         'demo': bool(c['is_demo']), 'contact': contact, 'show_contact': bool(c['show_contact'])}
    if own:
        d['reg_id'] = c['reg_id']
    if origin and c['lat'] is not None:
        d['dist'] = round(haversine(origin[0], origin[1], c['lat'], c['lng']), 1)
    return d

# ---------------------------------------------------------------- sms / otp
def send_sms(phone, code):
    prov = os.environ.get('SMS_PROVIDER', 'console')
    text = f'Your Mindful Space code is {code}. It expires in 5 minutes. Do not share it with anyone.'
    if prov == 'twilio':
        sid, tok = os.environ['TWILIO_ACCOUNT_SID'], os.environ['TWILIO_AUTH_TOKEN']
        data = {'To': '+91' + phone, 'Body': text}
        if os.environ.get('TWILIO_MESSAGING_SERVICE_SID'):
            data['MessagingServiceSid'] = os.environ['TWILIO_MESSAGING_SERVICE_SID']
        else:
            data['From'] = os.environ['TWILIO_FROM']
        req = urllib.request.Request(f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json',
                                     urllib.parse.urlencode(data).encode(), method='POST')
        req.add_header('Authorization', 'Basic ' + base64.b64encode(f'{sid}:{tok}'.encode()).decode())
        urllib.request.urlopen(req, timeout=10).read()
    elif prov == 'msg91':
        params = urllib.parse.urlencode({'template_id': os.environ['MSG91_TEMPLATE_ID'], 'mobile': '91' + phone,
                                         'authkey': os.environ['MSG91_AUTHKEY'], 'otp': code})
        req = urllib.request.Request('https://control.msg91.com/api/v5/otp?' + params, b'{}', method='POST',
                                     headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=10).read()
    else:
        print(f'[DEV SMS] to +91{phone}: {text}', flush=True)

def code_hash(phone, code):
    return hmac.new(app.secret_key.encode(), f'{phone}:{code}'.encode(), hashlib.sha256).hexdigest()

@app.post('/api/auth/send-otp')
def send_otp():
    b = body()
    phone = re.sub(r'\D', '', str(b.get('phone', '')))[-10:]
    if not PHONE_RE.match(phone):
        return err('Enter a valid 10-digit Indian mobile number.')
    now = time.time()
    recent = q('SELECT COUNT(*) n FROM otps WHERE phone=? AND created>?', (phone, now - 3600), one=True)['n']
    last = q('SELECT created FROM otps WHERE phone=? ORDER BY created DESC LIMIT 1', (phone,), one=True)
    if recent >= 5:
        return err('Too many codes requested. Try again in an hour.', 429)
    if last and now - last['created'] < 30:
        return err(f'Please wait {int(30 - (now - last["created"])) + 1}s before requesting another code.', 429)
    code = f'{secrets.randbelow(900000) + 100000}'
    ex('INSERT INTO otps(phone,code_hash,expires,created) VALUES(?,?,?,?)', (phone, code_hash(phone, code), now + 300, now))
    try:
        send_sms(phone, code)
    except Exception as e:  # provider failure must not leak details
        app.logger.error('SMS send failed: %s', e)
        return err('Could not send the SMS right now. Please try again.', 502)
    out = {'ok': True}
    if os.environ.get('DEV_SHOW_OTP', '0') == '1':
        out['dev_otp'] = code
    return jsonify(out)

@app.post('/api/auth/verify-otp')
def verify_otp():
    b = body()
    phone = re.sub(r'\D', '', str(b.get('phone', '')))[-10:]
    code = re.sub(r'\D', '', str(b.get('otp', '')))
    role = b.get('role')
    if role not in ('user', 'counsellor') or not PHONE_RE.match(phone) or len(code) != 6:
        return err('Enter the 6-digit code.')
    row = q('SELECT * FROM otps WHERE phone=? AND used=0 ORDER BY created DESC LIMIT 1', (phone,), one=True)
    if not row or row['expires'] < time.time():
        return err('This code has expired. Request a new one.')
    if row['attempts'] >= 5:
        return err('Too many wrong attempts. Request a new code.', 429)
    if not hmac.compare_digest(row['code_hash'], code_hash(phone, code)):
        ex('UPDATE otps SET attempts=attempts+1 WHERE id=?', (row['id'],))
        return err(f'Incorrect code. {4 - row["attempts"]} attempt(s) left.')
    ex('UPDATE otps SET used=1 WHERE id=?', (row['id'],))
    u = q('SELECT * FROM users WHERE phone=?', (phone,), one=True)
    if u:
        if u['role'] != role:
            return err(f'This number is registered as a {u["role"]}. Switch the option on the first screen.', 409)
        session.clear(); session.permanent = True; session['uid'] = u['id']
        return jsonify(ok=True, exists=True, me=user_dict(u))
    session.clear(); session.permanent = True
    session['vphone'], session['vrole'], session['vat'] = phone, role, time.time()
    return jsonify(ok=True, exists=False)

@app.post('/api/auth/register')
def register():
    b = body()
    phone, role = session.get('vphone'), session.get('vrole')
    if not phone or time.time() - session.get('vat', 0) > 900 or b.get('role') != role:
        return err('Please verify your phone number again.', 401)
    name, city = clean(b.get('name'), 80), b.get('city')
    if len(name) < 2:
        return err('Enter your full name.')
    if city not in CITY:
        return err('Choose your city.')
    langs = pick(b.get('langs'), LANGS)
    if not langs:
        return err('Pick at least one language.')
    try:
        lat, lng = float(b['lat']), float(b['lng'])
        if not (6 <= lat <= 38 and 68 <= lng <= 98):
            raise ValueError
    except Exception:
        lat, lng = CITY[city][2], CITY[city][3]
    now = time.time()
    try:
        if role == 'user':
            nick = clean(b.get('nick'), 30)
            age = int(b.get('age') or 0)
            if len(nick) < 3 or not re.match(r'^[\w .\-]+$', nick):
                return err('Choose a nickname of at least 3 letters or numbers.')
            if not 13 <= age <= 99:
                return err('Enter a valid age (13 or above).')
            ep = re.sub(r'\D', '', str(b.get('em_phone', '')))
            if ep and not PHONE_RE.match(ep):
                return err('Emergency contact number must be a valid 10-digit mobile number.')
            uid = ex('INSERT INTO users(phone,role,name,nick,nick_lc,age,gender,city,lat,lng,langs,concerns,mode_pref,em_name,em_phone,created) '
                     'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                     (phone, 'user', name, nick, nick.lower(), age, clean(b.get('gender'), 30), city, lat, lng, J(langs),
                      J([c for c in (b.get('concerns') or [])][:12]), clean(b.get('mode_pref'), 20), clean(b.get('em_name'), 60), ep or None, now))
        else:
            rid = valid_reg_id(b.get('reg_id'))
            if not rid:
                return err('Registration ID looks invalid. Use 6-20 characters with at least 4 digits, e.g. A12345 or CRR/2019/04567.')
            if b.get('council') not in COUNCILS:
                return err('Select your registering body.')
            email = clean(b.get('email'), 120)
            if not re.match(r'^\S+@\S+\.\S+$', email):
                return err('Enter a valid email address.')
            spec, modes = pick(b.get('spec'), SPECS, 4), pick(b.get('modes'), MODES)
            fee, exp = int(b.get('fee') or 0), int(b.get('exp') if b.get('exp') not in (None, '') else -1)
            if not spec or not modes:
                return err('Pick specialisations and session modes.')
            if not 200 <= fee <= 10000:
                return err('Fee must be between ₹200 and ₹10,000.')
            if not 0 <= exp <= 60:
                return err('Enter years of experience.')
            cp = re.sub(r'\D', '', str(b.get('contact_phone', '')))[-10:]
            if b.get('show_contact') and not PHONE_RE.match(cp):
                return err('Enter a valid public contact number, or untick "Show my contact".')
            uid = ex('INSERT INTO users(phone,role,name,nick,nick_lc,city,lat,lng,langs,created) VALUES(?,?,?,?,?,?,?,?,?,?)',
                     (phone, 'counsellor', name, name, name.lower(), city, lat, lng, J(langs), now))
            ex('INSERT INTO counsellors(user_id,title,council,reg_id,qual,area,exp,spec,langs,modes,fee,bio,email,contact_phone,show_contact,status,lat,lng) '
               'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
               (uid, clean(b.get('title') or 'Counsellor', 60), b['council'], rid, clean(b.get('qual'), 120), clean(b.get('area'), 80), exp,
                J(spec), J(langs), J(modes), fee, clean(b.get('bio'), 600), email, cp or None, 1 if b.get('show_contact') else 0, 'pending', lat, lng))
    except sqlite3.IntegrityError as e:
        m = str(e)
        if 'nick' in m:
            return err('That nickname is taken. Try another.', 409)
        if 'reg_id' in m:
            return err('This registration ID is already registered.', 409)
        return err('An account with this number already exists.', 409)
    except (ValueError, TypeError):
        return err('Please check the numbers you entered.')
    session.clear(); session.permanent = True; session['uid'] = uid
    return jsonify(ok=True, me=user_dict(q('SELECT * FROM users WHERE id=?', (uid,), one=True)))

@app.post('/api/auth/logout')
def logout():
    session.clear()
    return jsonify(ok=True)

# ---------------------------------------------------------------- reference + profile
@app.get('/api/meta')
def meta():
    return jsonify(cities=[[c[0], c[1], c[2], c[3]] for c in CITIES], specs=SPECS, langs=LANGS, councils=COUNCILS, helplines=HELPLINES)

@app.get('/api/me')
@auth()
def get_me():
    return jsonify(me=user_dict(me()))

@app.patch('/api/me')
@auth()
def patch_me():
    b, u = body(), me()
    f = {}
    if b.get('city') in CITY:
        f['city'] = b['city']
        try:
            f['lat'], f['lng'] = float(b['lat']), float(b['lng'])
        except Exception:
            f['lat'], f['lng'] = CITY[b['city']][2], CITY[b['city']][3]
    if u['role'] == 'user':
        if 'em_name' in b: f['em_name'] = clean(b['em_name'], 60)
        if 'em_phone' in b:
            ep = re.sub(r'\D', '', str(b['em_phone']))
            if ep and not PHONE_RE.match(ep):
                return err('Emergency contact number must be a valid 10-digit mobile number.')
            f['em_phone'] = ep or None
        if 'concerns' in b: f['concerns'] = J(list(b['concerns'])[:12])
    if f:
        ex('UPDATE users SET ' + ','.join(f'{k}=?' for k in f) + ' WHERE id=?', (*f.values(), u['id']))
    if u['role'] == 'counsellor':
        c = {}
        if 'fee' in b:
            fee = int(b['fee'] or 0)
            if not 200 <= fee <= 10000:
                return err('Fee must be between ₹200 and ₹10,000.')
            c['fee'] = fee
        if 'avail' in b: c['avail'] = 1 if b['avail'] else 0
        if 'bio' in b: c['bio'] = clean(b['bio'], 600)
        if 'show_contact' in b or 'contact_phone' in b:
            cp = re.sub(r'\D', '', str(b.get('contact_phone', '')))[-10:]
            if b.get('show_contact') and not PHONE_RE.match(cp):
                return err('Enter a valid public contact number first.')
            c['show_contact'], c['contact_phone'] = (1 if b.get('show_contact') else 0), cp or None
        if 'lat' in f: c['lat'], c['lng'] = f['lat'], f['lng']
        if c:
            ex('UPDATE counsellors SET ' + ','.join(f'{k}=?' for k in c) + ' WHERE user_id=?', (*c.values(), u['id']))
    g.pop('me', None)
    return jsonify(ok=True, me=user_dict(me()))

@app.delete('/api/me')
@auth()
def delete_me():
    ex('DELETE FROM users WHERE id=?', (me()['id'],))
    session.clear()
    return jsonify(ok=True)

# ---------------------------------------------------------------- counsellors
@app.get('/api/counsellors')
@auth()
def counsellors():
    a, u = request.args, me()
    try:
        origin = (float(a['lat']), float(a['lng']))
    except Exception:
        origin = (u['lat'], u['lng']) if u['lat'] is not None else None
    rows = q("SELECT c.*, u.name, u.city, u.is_demo FROM counsellors c JOIN users u ON u.id=c.user_id "
             "WHERE (c.status='verified' OR u.is_demo=1) AND u.id!=?", (u['id'],))
    items = [counsellor_dict(r, origin=origin) for r in rows]
    s = clean(a.get('q'), 60).lower()
    if a.get('city'): items = [i for i in items if i['city'] == a['city']]
    if a.get('state'): items = [i for i in items if i['state'] == a['state']]
    if s: items = [i for i in items if s in ' '.join([i['name'], i['title'], i['city'], i['state'], i['area'], *i['spec'], *i['langs']]).lower()]
    if a.get('spec'): items = [i for i in items if a['spec'] in i['spec']]
    if a.get('mode'): items = [i for i in items if a['mode'] in i['modes']]
    if a.get('max_fee'):
        try: items = [i for i in items if i['fee'] <= int(a['max_fee'])]
        except ValueError: pass
    key = {'price': lambda i: i['fee'], 'rating': lambda i: -i['rating'], 'exp': lambda i: -i['exp']}.get(a.get('sort'), lambda i: i.get('dist', 1e9))
    items.sort(key=key)
    try: limit = min(int(a.get('limit', 40)), 100)
    except ValueError: limit = 40
    return jsonify(total=len(items), items=items[:limit])

@app.get('/api/counsellors/<int:cid>/slots')
@auth()
def slots(cid):
    d = request.args.get('date', '')
    try:
        dt = datetime.strptime(d, '%Y-%m-%d').replace(tzinfo=IST)
    except ValueError:
        return err('Invalid date.')
    now = datetime.now(IST)
    if dt.date() < now.date() or dt.date() > (now + timedelta(days=14)).date():
        return err('Choose a date within the next 14 days.')
    taken = {r['time'] for r in q("SELECT time FROM bookings WHERE counsellor_id=? AND date=? AND status IN('requested','confirmed')", (cid, d))}
    out = []
    for s in SLOTS:
        past = dt.date() == now.date() and now.strftime('%H:%M') >= s
        out.append({'time': s, 'free': s not in taken and not past})
    return jsonify(slots=out)

# ---------------------------------------------------------------- bookings
def booking_dict(r, viewer_role):
    return {'id': r['id'], 'date': r['date'], 'time': r['time'], 'mode': r['mode'], 'fee': r['fee'], 'status': r['status'], 'payment': r['payment'],
            'rating': r['rating'], 'with_id': r['counsellor_id'] if viewer_role == 'user' else r['user_id'], 'with_name': r['other_name'], 'concerns': L(r['concerns']) if viewer_role == 'counsellor' else []}

@app.post('/api/bookings')
@auth('user')
def book():
    b, u = body(), me()
    c = q("SELECT c.*, us.name, us.city, us.is_demo FROM counsellors c JOIN users us ON us.id=c.user_id WHERE c.user_id=?", (b.get('counsellor_id'),), one=True)
    if not c or not (c['status'] == 'verified' or c['is_demo']):
        return err('Counsellor not found.', 404)
    if not c['avail']:
        return err('This counsellor is not accepting new bookings right now.', 409)
    d, t, mode = b.get('date', ''), b.get('time', ''), b.get('mode')
    if t not in SLOTS or mode not in L(c['modes']):
        return err('Pick a valid time and session type.')
    try:
        dt = datetime.strptime(f'{d} {t}', '%Y-%m-%d %H:%M').replace(tzinfo=IST)
    except ValueError:
        return err('Invalid date.')
    if dt <= datetime.now(IST) or dt > datetime.now(IST) + timedelta(days=14):
        return err('Choose a future slot within the next 14 days.')
    status = 'confirmed' if c['is_demo'] else 'requested'
    try:
        bid = ex('INSERT INTO bookings(user_id,counsellor_id,date,time,mode,fee,status,created) VALUES(?,?,?,?,?,?,?,?)',
                 (u['id'], c['user_id'], d, t, mode, c['fee'], status, time.time()))
    except sqlite3.IntegrityError:
        return err('That slot was just taken. Pick another.', 409)
    when = dt.strftime('%a %d %b, %I:%M %p')
    ex('INSERT INTO messages(from_id,to_id,body,ts) VALUES(?,?,?,?)', (c['user_id'], u['id'],
       f'Hi {u["nick"]}, thanks for booking a {mode.lower()} session on {when}.' + (' It is confirmed.' if status == 'confirmed' else ' I will confirm shortly.'), time.time() + 1))
    return jsonify(ok=True, id=bid, status=status)

@app.get('/api/bookings')
@auth()
def my_bookings():
    u = me()
    if u['role'] == 'user':
        rows = q('SELECT b.*, us.name other_name, "[]" concerns FROM bookings b JOIN users us ON us.id=b.counsellor_id WHERE b.user_id=? ORDER BY date DESC, time DESC', (u['id'],))
    else:
        rows = q('SELECT b.*, us.nick other_name, us.concerns FROM bookings b JOIN users us ON us.id=b.user_id WHERE b.counsellor_id=? ORDER BY date DESC, time DESC', (u['id'],))
    return jsonify(items=[booking_dict(r, u['role']) for r in rows])

@app.post('/api/bookings/<int:bid>/respond')
@auth('counsellor')
def respond_booking(bid):
    act = body().get('action')
    r = q('SELECT * FROM bookings WHERE id=? AND counsellor_id=?', (bid, me()['id']), one=True)
    if not r: return err('Booking not found.', 404)
    new = {'accept': 'confirmed', 'decline': 'declined', 'complete': 'completed'}.get(act)
    if not new or (act in ('accept', 'decline') and r['status'] != 'requested') or (act == 'complete' and r['status'] != 'confirmed'):
        return err('That action is not available for this booking.', 409)
    ex('UPDATE bookings SET status=? WHERE id=?', (new, bid))
    ex('INSERT INTO messages(from_id,to_id,body,ts) VALUES(?,?,?,?)', (me()['id'], r['user_id'],
       {'confirmed': 'Your session is confirmed. Looking forward to meeting you.', 'declined': 'Sorry, I cannot take that slot. Please pick another time.', 'completed': 'Thank you for today\'s session. Take care.'}[new], time.time()))
    return jsonify(ok=True)

@app.post('/api/bookings/<int:bid>/cancel')
@auth('user')
def cancel_booking(bid):
    r = q('SELECT * FROM bookings WHERE id=? AND user_id=?', (bid, me()['id']), one=True)
    if not r or r['status'] not in ('requested', 'confirmed'): return err('This booking cannot be cancelled.', 409)
    ex("UPDATE bookings SET status='cancelled' WHERE id=?", (bid,))
    return jsonify(ok=True)

@app.post('/api/bookings/<int:bid>/rate')
@auth('user')
def rate_booking(bid):
    b = body()
    r = q('SELECT * FROM bookings WHERE id=? AND user_id=?', (bid, me()['id']), one=True)
    try: stars = int(b.get('rating'))
    except (TypeError, ValueError): return err('Rating must be 1 to 5.')
    if not r or r['status'] != 'completed' or r['rating'] or not 1 <= stars <= 5: return err('You can rate a completed session once (1 to 5 stars).', 409)
    ex('UPDATE bookings SET rating=?, review=? WHERE id=?', (stars, clean(b.get('review'), 400), bid))
    c = q('SELECT rating_avg, rating_count FROM counsellors WHERE user_id=?', (r['counsellor_id'],), one=True)
    n = c['rating_count'] + 1
    ex('UPDATE counsellors SET rating_avg=?, rating_count=? WHERE user_id=?', ((c['rating_avg'] * c['rating_count'] + stars) / n, n, r['counsellor_id']))
    return jsonify(ok=True)

@app.get('/api/counsellor/dashboard')
@auth('counsellor')
def dashboard():
    u = me()
    month = datetime.now(IST).strftime('%Y-%m')
    earn = q("SELECT COALESCE(SUM(fee),0) s FROM bookings WHERE counsellor_id=? AND status IN('confirmed','completed') AND date LIKE ?", (u['id'], month + '%'), one=True)['s']
    done = q("SELECT COUNT(*) n FROM bookings WHERE counsellor_id=? AND status='completed'", (u['id'],), one=True)['n']
    clients = q("SELECT us.id, us.nick, us.concerns, COUNT(*) sessions, MAX(b.date) last FROM bookings b JOIN users us ON us.id=b.user_id WHERE b.counsellor_id=? AND b.status IN('confirmed','completed') GROUP BY us.id ORDER BY last DESC", (u['id'],))
    rows = q('SELECT b.*, us.nick other_name, us.concerns FROM bookings b JOIN users us ON us.id=b.user_id WHERE b.counsellor_id=? AND b.date>=? AND b.status IN(\'requested\',\'confirmed\') ORDER BY date, time', (u['id'], today_ist()))
    bk = [booking_dict(r, 'counsellor') for r in rows]
    return jsonify(earnings=earn, completed=done, today=[x for x in bk if x['date'] == today_ist() and x['status'] == 'confirmed'],
                   requests=[x for x in bk if x['status'] == 'requested'], upcoming=[x for x in bk if x['status'] == 'confirmed'],
                   clients=[{'id': c['id'], 'nick': c['nick'], 'concerns': L(c['concerns']), 'sessions': c['sessions'], 'last': c['last']} for c in clients])

# ---------------------------------------------------------------- messages
BOT_REPLIES = {'counsellor': ['Thank you for reaching out. Could you tell me a little more about what has been going on?',
                              'That sounds hard. We can work through it together. Would a video session this week suit you?',
                              'I hear you. Let us take it one step at a time.'],
               'user': ['Thanks for checking in. I am doing okay today, how about you?', 'That makes sense. I am here if you want to talk.', 'Same here! A walk helped me a lot this week.']}
rate = {}

def can_message(a, b):
    if a['id'] == b['id']: return False
    if a['role'] != b['role']:
        if a['role'] == 'user':
            return True
        return (q('SELECT 1 FROM messages WHERE from_id=? AND to_id=?', (b['id'], a['id']), one=True) is not None
                or q('SELECT 1 FROM bookings WHERE user_id=? AND counsellor_id=?', (b['id'], a['id']), one=True) is not None)
    return a['role'] == 'user' and q("SELECT 1 FROM friends WHERE status='accepted' AND ((user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?))", (a['id'], b['id'], b['id'], a['id']), one=True) is not None

@app.get('/api/threads')
@auth()
def threads():
    uid = me()['id']
    rows = q('''SELECT peer, MAX(ts) last_ts, SUM(CASE WHEN to_id=? AND read=0 THEN 1 ELSE 0 END) unread FROM
                (SELECT CASE WHEN from_id=? THEN to_id ELSE from_id END peer, to_id, read, ts FROM messages WHERE (from_id=? OR to_id=?) AND ts<=?)
                GROUP BY peer ORDER BY last_ts DESC''', (uid, uid, uid, uid, time.time()))
    out = []
    for r in rows:
        p = q('SELECT id,name,nick,role,city,is_demo FROM users WHERE id=?', (r['peer'],), one=True)
        last = q('SELECT body, from_id FROM messages WHERE ((from_id=? AND to_id=?) OR (from_id=? AND to_id=?)) AND ts<=? ORDER BY ts DESC LIMIT 1', (uid, r['peer'], r['peer'], uid, time.time()), one=True)
        out.append({'peer': p['id'], 'name': p['name'] if p['role'] == 'counsellor' else p['nick'], 'role': p['role'], 'city': p['city'], 'demo': bool(p['is_demo']),
                    'last': last['body'], 'mine': last['from_id'] == uid, 'unread': r['unread'], 'ts': r['last_ts']})
    return jsonify(items=out, unread=sum(t['unread'] for t in out))

@app.get('/api/messages/<int:peer>')
@auth()
def get_messages(peer):
    uid, after = me()['id'], int(request.args.get('after', 0) or 0)
    p = q('SELECT id,name,nick,role,city,is_demo FROM users WHERE id=?', (peer,), one=True)
    if not p: return err('Not found.', 404)
    rows = q('SELECT id, from_id, body, ts FROM messages WHERE ((from_id=? AND to_id=?) OR (from_id=? AND to_id=?)) AND id>? AND ts<=? ORDER BY id LIMIT 200', (uid, peer, peer, uid, after, time.time()))
    ex('UPDATE messages SET read=1 WHERE to_id=? AND from_id=? AND ts<=?', (uid, peer, time.time()))
    return jsonify(peer={'id': p['id'], 'name': p['name'] if p['role'] == 'counsellor' else p['nick'], 'role': p['role'], 'city': p['city'], 'demo': bool(p['is_demo'])},
                   items=[{'id': r['id'], 'mine': r['from_id'] == uid, 'body': r['body'], 'ts': r['ts']} for r in rows])

@app.post('/api/messages')
@auth()
def send_message():
    b, u = body(), me()
    p = q('SELECT * FROM users WHERE id=?', (b.get('to'),), one=True)
    text = str(b.get('body', '')).strip()[:2000]
    if not p or not text: return err('Write a message first.')
    if not can_message(u, p): return err('You can message counsellors directly, and friends once they accept your request.', 403)
    now = time.time()
    hits = [t for t in rate.get(u['id'], []) if now - t < 60]
    if len(hits) >= 30: return err('You are sending messages too fast.', 429)
    rate[u['id']] = hits + [now]
    mid = ex('INSERT INTO messages(from_id,to_id,body,ts) VALUES(?,?,?,?)', (u['id'], p['id'], text, now))
    if p['is_demo']:
        ex('INSERT INTO messages(from_id,to_id,body,ts) VALUES(?,?,?,?)', (p['id'], u['id'], random.choice(BOT_REPLIES[p['role']]), now + 2))
    return jsonify(ok=True, id=mid, crisis=bool(CRISIS_RE.search(text)))

# ---------------------------------------------------------------- friends & community
@app.get('/api/friends')
@auth('user')
def friends():
    uid = me()['id']
    def people(sql, a):
        return [{'id': r['id'], 'nick': r['nick'], 'city': r['city'], 'demo': bool(r['is_demo'])} for r in q(sql, a)]
    acc = people("SELECT u.* FROM friends f JOIN users u ON u.id=CASE WHEN f.user_id=? THEN f.friend_id ELSE f.user_id END WHERE f.status='accepted' AND (f.user_id=? OR f.friend_id=?)", (uid, uid, uid))
    inc = people("SELECT u.* FROM friends f JOIN users u ON u.id=f.user_id WHERE f.friend_id=? AND f.status='pending'", (uid,))
    out = people("SELECT u.* FROM friends f JOIN users u ON u.id=f.friend_id WHERE f.user_id=? AND f.status='pending'", (uid,))
    known = {p['id'] for p in acc + inc + out} | {uid}
    sug = [{'id': r['id'], 'nick': r['nick'], 'city': r['city'], 'demo': bool(r['is_demo'])} for r in
           q("SELECT * FROM users WHERE role='user' ORDER BY (city=?) DESC, created DESC LIMIT 40", (me()['city'],)) if r['id'] not in known][:10]
    return jsonify(friends=acc, incoming=inc, outgoing=out, suggestions=sug)

@app.post('/api/friends/request')
@auth('user')
def friend_request():
    uid, fid = me()['id'], body().get('user_id')
    p = q("SELECT * FROM users WHERE id=? AND role='user'", (fid,), one=True)
    if not p or p['id'] == uid: return err('Person not found.', 404)
    if q('SELECT 1 FROM friends WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)', (uid, fid, fid, uid), one=True):
        return err('Request already exists.', 409)
    ex('INSERT INTO friends(user_id,friend_id,status,created) VALUES(?,?,?,?)', (uid, fid, 'accepted' if p['is_demo'] else 'pending', time.time()))
    return jsonify(ok=True, accepted=bool(p['is_demo']))

@app.post('/api/friends/respond')
@auth('user')
def friend_respond():
    b, uid = body(), me()['id']
    if b.get('action') == 'accept':
        n = ex("UPDATE friends SET status='accepted' WHERE user_id=? AND friend_id=? AND status='pending'", (b.get('user_id'), uid))
    else:
        ex("DELETE FROM friends WHERE user_id=? AND friend_id=? AND status='pending'", (b.get('user_id'), uid))
    return jsonify(ok=True)

@app.get('/api/posts')
@auth()
def posts():
    uid = me()['id']
    rows = q('''SELECT p.*, u.nick, u.city, u.is_demo, (SELECT COUNT(*) FROM post_support s WHERE s.post_id=p.id) + p.seed_support n,
                EXISTS(SELECT 1 FROM post_support s WHERE s.post_id=p.id AND s.user_id=?) mine FROM posts p JOIN users u ON u.id=p.user_id ORDER BY p.ts DESC LIMIT 50''', (uid,))
    return jsonify(items=[{'id': r['id'], 'nick': r['nick'], 'city': r['city'], 'body': r['body'], 'tag': r['tag'], 'ts': r['ts'], 'support': r['n'], 'mine': bool(r['mine']), 'demo': bool(r['is_demo']), 'own': r['user_id'] == uid} for r in rows])

@app.post('/api/posts')
@auth('user')
def new_post():
    b = body()
    text = str(b.get('body', '')).strip()[:600]
    if len(text) < 3: return err('Write a few words first.')
    if re.search(r'\d{10}', re.sub(r'[\s\-]', '', text)) or re.search(r'https?://|@\w+\.\w+', text):
        return err('For everyone\'s safety, please do not share phone numbers, links or emails.')
    ex('INSERT INTO posts(user_id,body,tag,ts) VALUES(?,?,?,?)', (me()['id'], text, clean(b.get('tag') or 'Post', 20), time.time()))
    return jsonify(ok=True, crisis=bool(CRISIS_RE.search(text)))

@app.post('/api/posts/<int:pid>/support')
@auth('user')
def support(pid):
    uid = me()['id']
    if q('SELECT 1 FROM post_support WHERE post_id=? AND user_id=?', (pid, uid), one=True):
        ex('DELETE FROM post_support WHERE post_id=? AND user_id=?', (pid, uid))
    else:
        ex('INSERT OR IGNORE INTO post_support(post_id,user_id) VALUES(?,?)', (pid, uid))
    return jsonify(ok=True)

@app.delete('/api/posts/<int:pid>')
@auth('user')
def del_post(pid):
    ex('DELETE FROM posts WHERE id=? AND user_id=?', (pid, me()['id']))
    return jsonify(ok=True)

# ---------------------------------------------------------------- wellness (habits, practice, journal, score)
def day_score(h, practice_secs, journal_n):
    s = 0.0
    if h:
        sl = h['sleep'] or 0
        s += 25 * (1 if 7 <= sl <= 9 else max(0, 1 - abs((8 if sl < 7 else 9) - sl) / 4))
        s += 20 * min(1, (h['water'] or 0) / 8)
        s += 20 * min(1, (h['move'] or 0) / 30)
    s += 20 * min(1, practice_secs / 120)
    s += 15 * min(1, journal_n)
    return round(s)

@app.get('/api/wellness')
@auth('user')
def wellness():
    uid = me()['id']
    days = [(datetime.now(IST) - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6, -1, -1)]
    hab = {r['day']: r for r in q('SELECT * FROM habits WHERE user_id=? AND day>=?', (uid, days[0]))}
    pr = {r['day']: r['s'] for r in q('SELECT day, SUM(seconds) s FROM practice WHERE user_id=? AND day>=? GROUP BY day', (uid, days[0]))}
    jn = {r['day']: r['n'] for r in q("SELECT date(ts,'unixepoch','+5.5 hours') day, COUNT(*) n FROM journal WHERE user_id=? GROUP BY day", (uid,))}
    series = [{'day': d, 'score': day_score(hab.get(d), pr.get(d, 0), jn.get(d, 0)), 'active': bool(hab.get(d) or pr.get(d) or jn.get(d))} for d in days]
    streak = 0
    for s in reversed(series):
        if s['active']: streak += 1
        elif s['day'] != days[-1]: break
    t = hab.get(days[-1])
    return jsonify(series=series, today={'water': t['water'] if t else 0, 'sleep': t['sleep'] if t else 0, 'move': t['move'] if t else 0, 'practice_secs': pr.get(days[-1], 0)},
                   score=series[-1]['score'], avg=round(sum(s['score'] for s in series) / 7), streak=streak,
                   journal_count=q('SELECT COUNT(*) n FROM journal WHERE user_id=?', (uid,), one=True)['n'],
                   practice_total=q('SELECT COALESCE(SUM(seconds),0) s FROM practice WHERE user_id=?', (uid,), one=True)['s'])

@app.put('/api/habits')
@auth('user')
def put_habits():
    b = body()
    try:
        water, sleep, move = int(b.get('water', 0)), float(b.get('sleep', 0)), int(b.get('move', 0))
    except (TypeError, ValueError):
        return err('Invalid values.')
    if not (0 <= water <= 20 and 0 <= sleep <= 24 and 0 <= move <= 600): return err('Values are out of range.')
    ex('INSERT INTO habits(user_id,day,water,sleep,move) VALUES(?,?,?,?,?) ON CONFLICT(user_id,day) DO UPDATE SET water=excluded.water, sleep=excluded.sleep, move=excluded.move',
       (me()['id'], today_ist(), water, sleep, move))
    return jsonify(ok=True)

@app.post('/api/practice')
@auth('user')
def log_practice():
    b = body()
    try: secs = int(b.get('seconds'))
    except (TypeError, ValueError): return err('Invalid duration.')
    if b.get('kind') not in PRACTICES or not 10 <= secs <= 3600: return err('Invalid practice.')
    ex('INSERT INTO practice(user_id,kind,seconds,day,ts) VALUES(?,?,?,?,?)', (me()['id'], b['kind'], secs, today_ist(), time.time()))
    return jsonify(ok=True)

@app.get('/api/journal')
@auth('user')
def get_journal():
    return jsonify(items=[{'id': r['id'], 'body': r['body'], 'ts': r['ts']} for r in q('SELECT * FROM journal WHERE user_id=? ORDER BY ts DESC LIMIT 50', (me()['id'],))])

@app.post('/api/journal')
@auth('user')
def add_journal():
    text = str(body().get('body', '')).strip()[:4000]
    if len(text) < 2: return err('Write a few words first.')
    ex('INSERT INTO journal(user_id,body,ts) VALUES(?,?,?)', (me()['id'], text, time.time()))
    return jsonify(ok=True, crisis=bool(CRISIS_RE.search(text)))

@app.delete('/api/journal/<int:jid>')
@auth('user')
def del_journal(jid):
    ex('DELETE FROM journal WHERE id=? AND user_id=?', (jid, me()['id']))
    return jsonify(ok=True)

# ---------------------------------------------------------------- admin (counsellor ID review)
def admin_ok():
    t = os.environ.get('ADMIN_TOKEN')
    return bool(t) and hmac.compare_digest(request.headers.get('X-Admin-Token', ''), t)

@app.get('/api/admin/counsellors')
def admin_list():
    if not admin_ok(): return err('Unauthorised.', 401)
    rows = q("SELECT c.*, u.name, u.city, u.phone, u.is_demo FROM counsellors c JOIN users u ON u.id=c.user_id WHERE u.is_demo=0 ORDER BY (c.status='pending') DESC, u.created DESC")
    return jsonify(items=[{**counsellor_dict(r, True), 'phone': r['phone']} for r in rows])

@app.post('/api/admin/counsellors/<int:cid>/status')
def admin_status(cid):
    if not admin_ok(): return err('Unauthorised.', 401)
    st = (request.get_json(silent=True) or {}).get('status')
    if st not in ('verified', 'rejected', 'pending'): return err('Invalid status.')
    ex('UPDATE counsellors SET status=? WHERE user_id=?', (st, cid))
    return jsonify(ok=True)

# ---------------------------------------------------------------- static + seed
@app.get('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

def seed_demo():
    if q("SELECT 1 FROM users WHERE is_demo=1 LIMIT 1", one=True): return
    now = time.time()
    for ci, c in enumerate(CITIES):
        rng = random.Random(ci * 977 + 13)
        n = 5 if c[0] in ('Delhi', 'Mumbai', 'Bengaluru', 'Hyderabad', 'Chennai', 'Kolkata', 'Pune', 'Nagpur') else 3
        for i in range(n):
            fns, lns = NAMES[c[4]]
            t = rng.choice(TITLES); doc = t == 'Psychiatrist'
            name = ('Dr. ' if doc or rng.random() > .55 else '') + rng.choice(fns) + ' ' + rng.choice(lns)
            sp = rng.sample(SPECS, 3); exp = rng.randint(8, 24) if doc else rng.randint(3, 20)
            lo, hi = (1200, 2500) if doc else (500, 1800)
            lat, lng = c[2] + (rng.random() - .5) * .12, c[3] + (rng.random() - .5) * .12
            uid = ex('INSERT INTO users(phone,role,name,nick,nick_lc,city,lat,lng,langs,is_demo,created) VALUES(?,?,?,?,?,?,?,?,?,1,?)',
                     (f'demo-c{ci}-{i}', 'counsellor', name, name, name.lower(), c[0], lat, lng, J(c[5]), now))
            ex('INSERT INTO counsellors(user_id,title,council,qual,area,exp,spec,langs,modes,fee,bio,status,rating_avg,rating_count,lat,lng,avail) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
               (uid, t, COUNCILS[1] if doc else COUNCILS[0], 'Sample profile', rng.choice(AREAS), exp, J(sp), J(c[5][:rng.randint(2, 3)]),
                J(MODES if rng.random() > .45 else MODES[:2]), round(rng.uniform(lo, hi) / 50) * 50,
                f'Sample profile for demonstration. {exp}+ years supporting people with {sp[0].lower()}, {sp[1].lower()} and {sp[2].lower()}.',
                'verified', round(4.3 + rng.random() * .6, 1), rng.randint(20, 380), lat, lng, 1))
    peers = [('QuietRiver', 'Pune'), ('SunnyMango', 'Nagpur'), ('NightOwl_91', 'Bengaluru'), ('KiteRunner', 'Delhi'), ('PeacefulBanyan', 'Chennai'),
             ('MonsoonMind', 'Kochi'), ('LotusLeaf', 'Jaipur'), ('TeaAndTrains', 'Kolkata')]
    pids = []
    for i, (nick, city) in enumerate(peers):
        pids.append(ex('INSERT INTO users(phone,role,name,nick,nick_lc,age,city,lat,lng,langs,is_demo,created) VALUES(?,?,?,?,?,?,?,?,?,?,1,?)',
                       (f'demo-p{i}', 'user', nick, nick, nick.lower(), 24, city, CITY[city][2], CITY[city][3], J(['English']), now)))
    posts_seed = [(0, 'Day 12 of going to bed before 11. Small, but my mornings feel different.', 'Sleep', 24), (1, 'Boards are in a month. Breathing for 2 minutes before study blocks is helping more than I expected.', 'Exams', 31),
                  (5, 'Told my sister how I have been feeling. Scary and lighter at the same time.', 'Support', 58), (3, 'A 20-minute walk without my phone. Highly recommend on a rough day.', 'Habits', 19),
                  (6, 'Reminder: asking for help is a skill, not a weakness.', 'Support', 77)]
    for k, (pi, text, tag, n) in enumerate(posts_seed):
        ex('INSERT INTO posts(user_id,body,tag,ts,seed_support) VALUES(?,?,?,?,?)', (pids[pi], text, tag, now - k * 7200, n))

def init():
    with sqlite3.connect(DB_PATH) as c:
        c.executescript(SCHEMA)
    if os.environ.get('SEED_DEMO', '1') == '1':
        with app.app_context():
            seed_demo()

init()

if __name__ == '__main__':
    app.run(host=os.environ.get('HOST', '127.0.0.1'), port=int(os.environ.get('PORT', 5000)), debug=os.environ.get('FLASK_DEBUG', '0') == '1')
