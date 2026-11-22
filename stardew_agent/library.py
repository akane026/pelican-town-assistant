"""Editable source library, deliberately separate from immutable agent snapshots."""
from __future__ import annotations

import base64
import binascii
import http.client
import ipaddress
import json
import socket
import sqlite3
import ssl
import uuid
from contextlib import closing
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
import certifi

from .core import DATA, ValidationError, database, digest, now

MAX_BYTES = 2 * 1024 * 1024
EXTENSIONS = {'.txt', '.md', '.markdown', '.html', '.htm', '.json', '.csv'}


def validate_url(url):
    if not isinstance(url, str) or len(url) > 2048 or any(ord(char) <= 32 for char in url):
        raise ValidationError('LIBRARY_INVALID_URL')
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
                or parsed.password or parsed.port not in (None, 443)):
            raise ValueError()
    except ValueError:
        raise ValidationError('LIBRARY_INVALID_URL') from None
    return parsed


def fetch_webpage(url):
    """Fetch public HTTPS pages with pinned DNS, bounded size and checked redirects."""
    for _ in range(4):
        parsed = validate_url(url)
        host = parsed.hostname.encode('idna').decode('ascii')
        try:
            addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            ips = [row[4][0] for row in addresses]
            if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
                raise ValidationError('LIBRARY_PRIVATE_URL')
            # Connect to the validated address, while TLS still verifies the original host.
            with closing(http.client.HTTPSConnection(host, timeout=15)) as connection:
                raw = socket.create_connection((ips[0], 443), timeout=15)
                try:
                    context = ssl.create_default_context()
                    context.load_verify_locations(cafile=certifi.where())
                    connection.sock = context.wrap_socket(raw, server_hostname=host)
                except Exception:
                    raw.close()
                    raise
                connection.request('GET', (parsed.path or '/') + ('?' + parsed.query if parsed.query else ''),
                                   headers={'User-Agent': 'PelicanTownLibrary/1.0', 'Accept': 'text/html,text/plain',
                                            'Accept-Encoding': 'identity'})
                response = connection.getresponse()
                if response.status in (301, 302, 303, 307, 308):
                    location = response.getheader('Location')
                    if not location:
                        raise ValidationError('LIBRARY_FETCH_FAILED')
                    url = urljoin(url, location)
                    continue
                if response.status != 200:
                    raise ValidationError('LIBRARY_FETCH_FAILED')
                mime = response.getheader('Content-Type', '').split(';')[0].strip().lower()
                if mime not in ('text/html', 'application/xhtml+xml', 'text/plain'):
                    raise ValidationError('LIBRARY_WEB_FORMAT')
                if response.getheader('Content-Encoding', 'identity') != 'identity':
                    raise ValidationError('LIBRARY_WEB_FORMAT')
                payload = response.read(MAX_BYTES + 1)
                if len(payload) > MAX_BYTES:
                    raise ValidationError('LIBRARY_SIZE_LIMIT')
                encoding = response.headers.get_content_charset() or 'utf-8'
                content = payload.decode(encoding)
                return {'url': url, 'content': content, 'filename': 'webpage.html' if mime != 'text/plain' else 'webpage.txt'}
        except (OSError, UnicodeError, LookupError, http.client.HTTPException):
            raise ValidationError('LIBRARY_FETCH_FAILED') from None
    raise ValidationError('LIBRARY_REDIRECT_LIMIT')


def prepare_content(filename, content):
    suffix = Path(filename).suffix.lower()
    if suffix not in EXTENSIONS:
        raise ValidationError('LIBRARY_UNSUPPORTED_FORMAT')
    if not isinstance(content, str) or '\0' in content or not content.strip():
        raise ValidationError('LIBRARY_EMPTY_CONTENT')
    if len(content.encode('utf-8')) > MAX_BYTES:
        raise ValidationError('LIBRARY_SIZE_LIMIT')
    title = ''
    if suffix in ('.html', '.htm'):
        soup = BeautifulSoup(content, 'html.parser')
        title = soup.title.get_text(' ', strip=True) if soup.title else ''
        for element in soup(['script', 'style', 'noscript', 'iframe', 'object', 'nav', 'form']):
            element.decompose()
        text = soup.get_text('\n', strip=True)
    else:
        if suffix == '.json':
            try:
                json.loads(content)
            except ValueError:
                raise ValidationError('LIBRARY_INVALID_JSON') from None
        text = content
    if not text.strip():
        raise ValidationError('LIBRARY_EMPTY_CONTENT')
    return text, title


class LibraryStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else DATA / 'library/library.sqlite3'
        with closing(database(self.path)) as db, db:
            db.execute('''CREATE TABLE IF NOT EXISTS library_sources (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL,
                filename TEXT NOT NULL, url TEXT NOT NULL, content TEXT NOT NULL,
                text_content TEXT NOT NULL, sha256 TEXT NOT NULL, revision INTEGER NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')

    def _connect(self):
        db = database(self.path)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _public(row):
        return {**dict(row), 'status': 'pending_build'}

    def list(self, query='', kind='', offset=0):
        if not isinstance(query, str) or len(query) > 200 or kind not in ('', 'file', 'web'):
            raise ValidationError('LIBRARY_INVALID_FILTER')
        offset = max(0, int(offset))
        needle = '%' + query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        where = "WHERE (title LIKE ? ESCAPE '\\' OR text_content LIKE ? ESCAPE '\\') AND (? = '' OR kind = ?)"
        args = (needle, needle, kind, kind)
        with closing(self._connect()) as db:
            total = db.execute('SELECT count(*) FROM library_sources ' + where, args).fetchone()[0]
            rows = db.execute('''SELECT id,title,kind,filename,url,sha256,revision,created_at,updated_at,
                length(text_content) AS characters FROM library_sources ''' + where +
                ' ORDER BY updated_at DESC,id LIMIT 20 OFFSET ?', (*args, offset)).fetchall()
        return {'items': [self._public(row) for row in rows], 'total': total, 'offset': offset, 'limit': 20}

    def get(self, source_id):
        with closing(self._connect()) as db:
            row = db.execute('SELECT * FROM library_sources WHERE id=?', (source_id,)).fetchone()
        if row is None:
            raise ValidationError('LIBRARY_NOT_FOUND')
        return self._public(row)

    def create(self, data):
        kind = data.get('kind')
        if kind == 'web':
            source = fetch_webpage(data.get('url'))
            filename, url, content = source['filename'], source['url'], source['content']
        elif kind == 'file':
            filename = data.get('filename', '')
            if not isinstance(filename, str) or len(filename) > 200 or '/' in filename or '\\' in filename:
                raise ValidationError('LIBRARY_INVALID_FILENAME')
            try:
                raw = base64.b64decode(data.get('data', ''), validate=True)
                if len(raw) > MAX_BYTES:
                    raise ValidationError('LIBRARY_SIZE_LIMIT')
                content = raw.decode('utf-8-sig')
            except (binascii.Error, UnicodeError, TypeError):
                raise ValidationError('LIBRARY_UTF8_REQUIRED') from None
            url = ''
        else:
            raise ValidationError('LIBRARY_INVALID_KIND')
        text, heading = prepare_content(filename, content)
        title = self._title(data.get('title') or heading[:160] or filename)
        source_id = str(uuid.uuid4())
        timestamp = now()
        with closing(self._connect()) as db, db:
            db.execute('INSERT INTO library_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                       (source_id, title, kind, filename, url, content, text, digest(content.encode()), 1, timestamp, timestamp))
        return self.get(source_id)

    @staticmethod
    def _title(value):
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 160:
            raise ValidationError('LIBRARY_TITLE_REQUIRED')
        return value.strip()

    def update(self, source_id, revision, title, content):
        current = self.get(source_id)
        title = self._title(title)
        text, _ = prepare_content(current['filename'], content)
        with closing(self._connect()) as db, db:
            changed = db.execute('''UPDATE library_sources SET title=?,content=?,text_content=?,sha256=?,
                revision=revision+1,updated_at=? WHERE id=? AND revision=?''',
                (title, content, text, digest(content.encode()), now(), source_id, revision)).rowcount
            if not changed:
                raise ValidationError('LIBRARY_STALE_REVISION')
        return self.get(source_id)

    def delete(self, source_id, revision):
        with closing(self._connect()) as db, db:
            changed = db.execute('DELETE FROM library_sources WHERE id=? AND revision=?', (source_id, revision)).rowcount
            if not changed:
                raise ValidationError('LIBRARY_STALE_REVISION')
        return {'status': 'DELETED', 'id': source_id}
