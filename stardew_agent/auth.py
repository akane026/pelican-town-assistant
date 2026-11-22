"""SQLite accounts, hashed passwords and expiring cookie sessions."""
from contextlib import contextmanager
import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from http.cookies import SimpleCookie
from .core import DATA, ValidationError

class AuthStore:
    def __init__(self, path=None):
        self.path = path or DATA / 'library/library.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
                salt TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('user','admin')));
                CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS resource_owners (kind TEXT, resource_id TEXT, user_id TEXT,
                PRIMARY KEY(kind,resource_id));''')
    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()
    def needs_setup(self):
        with self.connect() as db:
            return db.execute('SELECT count(*) FROM users WHERE role="admin"').fetchone()[0] == 0
    def register(self, username, password, setup=False):
        if not isinstance(username,str) or not re.fullmatch(r'[\w\-]{3,32}', username):
            raise ValidationError('用户名需要 3–32 个字母、数字、汉字或下划线')
        if not isinstance(password,str) or not 6 <= len(password) <= 128:
            raise ValidationError('密码需要 6–128 个字符')
        salt = secrets.token_hex(16)
        encoded = hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            first = db.execute('SELECT count(*) FROM users WHERE role="admin"').fetchone()[0] == 0
            if setup and not first:
                raise ValidationError('管理员已经初始化')
            uid = secrets.token_hex(16)
            try:
                db.execute('INSERT INTO users VALUES (?,?,?,?,?)',(uid,username,encoded,salt,'admin' if setup else 'user'))
            except sqlite3.IntegrityError:
                raise ValidationError('用户名已存在') from None
    def login(self, username, password):
        if not isinstance(username,str) or not isinstance(password,str) or len(password)>128:
            raise ValidationError('用户名或密码不正确')
        with self.connect() as db:
            row = db.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
            salt = row['salt'] if row else '00'*16
            encoded = hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
            if not row or not hmac.compare_digest(encoded,row['password_hash']):
                raise ValidationError('用户名或密码不正确')
            token = secrets.token_urlsafe(32)
            db.execute('DELETE FROM sessions WHERE expires < ?',(time.time(),))
            db.execute('INSERT INTO sessions VALUES (?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),row['id'],time.time()+7*86400))
            return token
    def token(self, cookie):
        jar = SimpleCookie()
        try: jar.load(cookie or '')
        except Exception: return ''
        return jar['pelican_session'].value if 'pelican_session' in jar else ''
    def user(self, cookie):
        token = self.token(cookie)
        with self.connect() as db:
            row = db.execute('SELECT u.id,u.username,u.role FROM users u JOIN sessions s ON u.id=s.user_id WHERE s.token=? AND s.expires>?',
                (hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
            return dict(row) if row else None
    def logout(self,cookie):
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(self.token(cookie).encode()).hexdigest(),))
    def own(self,kind,rid,user):
        with self.connect() as db:
            db.execute('INSERT INTO resource_owners VALUES (?,?,?)',(kind,rid,user['id']))
    def allowed(self,kind,rid,user):
        with self.connect() as db:
            row=db.execute('SELECT user_id FROM resource_owners WHERE kind=? AND resource_id=?',(kind,rid)).fetchone()
            return user['role']=='admin' or bool(row and row['user_id']==user['id'])
