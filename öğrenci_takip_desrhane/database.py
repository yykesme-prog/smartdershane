import sqlite3
import os
import shutil
import datetime
import logging
import hashlib
import binascii



logging.basicConfig(filename='smartdershane.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

class Database:
    def __init__(self, path='smartdershane.db'):
        self.path = path
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        cur = self.conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)''')
        # ensure upgradeable columns for hashed passwords
        cur.execute("PRAGMA table_info(users)")
        cols = [r[1] for r in cur.fetchall()]
        if 'password_hash' not in cols:
            try:
                cur.execute('ALTER TABLE users ADD COLUMN password_hash TEXT')
            except Exception:
                pass
        if 'salt' not in cols:
            try:
                cur.execute('ALTER TABLE users ADD COLUMN salt TEXT')
            except Exception:
                pass
        cur.execute('''CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY, name TEXT, surname TEXT, tc TEXT, parent_chat_id TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS attendance (id INTEGER PRIMARY KEY, student_id INTEGER, status TEXT, ts TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS appointments (id INTEGER PRIMARY KEY, student_id INTEGER, teacher_id INTEGER, start_ts TEXT, duration_min INTEGER)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS teacher_availability (id INTEGER PRIMARY KEY, teacher_id INTEGER, start_ts TEXT, end_ts TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS backups (id INTEGER PRIMARY KEY, path TEXT, ts TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS exams (id INTEGER PRIMARY KEY, student_id INTEGER, name TEXT, score INTEGER, ts TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT)''')
        self.conn.commit()
        # add default admin if not exists (use hashed password)
        cur.execute("SELECT * FROM users WHERE username='admin'")
        if not cur.fetchone():
            self.create_user('admin', 'admin', 'admin')
            logging.info('Default admin created')

    def authenticate(self, username, password, role):
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM users WHERE username=? AND role=?', (username, role))
        row = cur.fetchone()
        if not row:
            return None
        r = dict(row)
        # prefer password_hash + salt
        ph = r.get('password_hash')
        salt = r.get('salt')
        if ph and salt:
            if self._verify_password(password, salt, ph):
                return r
            return None
        # legacy: plain password in 'password' column
        if r.get('password') == password:
            # upgrade: hash and store
            sh, sl = self._hash_password(password)
            try:
                cur.execute('UPDATE users SET password_hash=?, salt=? WHERE id=?', (sh, sl, r['id']))
                self.conn.commit()
            except Exception:
                pass
            return r
        return None

    def create_user(self, username, password, role):
        cur = self.conn.cursor()
        ph, sl = self._hash_password(password)
        cur.execute('INSERT INTO users (username, password_hash, salt, role) VALUES (?,?,?,?)', (username, ph, sl, role))
        self.conn.commit()
        return True

    def list_users(self):
        cur = self.conn.cursor()
        cur.execute('SELECT id, username, role FROM users ORDER BY id')
        return [dict(r) for r in cur.fetchall()]

    def delete_user(self, user_id):
        cur = self.conn.cursor()
        cur.execute('DELETE FROM users WHERE id=?', (user_id,))
        self.conn.commit()
        logging.info(f'User {user_id} deleted')

    def change_password(self, user_id, new_password):
        ph, sl = self._hash_password(new_password)
        cur = self.conn.cursor()
        cur.execute('UPDATE users SET password_hash=?, salt=? WHERE id=?', (ph, sl, user_id))
        self.conn.commit()
        logging.info(f'Password changed for user {user_id}')

    def _hash_password(self, password):
        salt = hashlib.sha256(os.urandom(60)).hexdigest().encode('ascii')
        pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        pwdhash = binascii.hexlify(pwdhash)
        return (pwdhash.decode('ascii'), salt.decode('ascii'))

    def _verify_password(self, provided_password, salt_hex, stored_hash_hex):
        salt = salt_hex.encode('ascii')
        pwdhash = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100000)
        pwdhash = binascii.hexlify(pwdhash).decode('ascii')
        return pwdhash == stored_hash_hex

    # Students
    def add_student(self, name, surname, tc, parent_chat_id=None):
        cur = self.conn.cursor()
        cur.execute('INSERT INTO students (name,surname,tc,parent_chat_id) VALUES (?,?,?,?)', (name,surname,tc,parent_chat_id))
        self.conn.commit()
        logging.info(f'Added student {name} {surname}')

    def list_students(self):
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM students')
        return [dict(r) for r in cur.fetchall()]

    def get_student(self, sid):
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM students WHERE id=?', (sid,))
        r = cur.fetchone()
        return dict(r) if r else None

    # Attendance
    def add_attendance(self, student_id, status):
        cur = self.conn.cursor()
        ts = datetime.datetime.now().isoformat()
        cur.execute('INSERT INTO attendance (student_id,status,ts) VALUES (?,?,?)', (student_id,status,ts))
        self.conn.commit()
        logging.info(f'Attendance for {student_id}: {status}')

    # Appointments
    def add_appointment(self, student_id, teacher_id, start_ts, duration_min=15):
        # enforce max 3 appointments per student per calendar week
        cur = self.conn.cursor()
        start = datetime.datetime.fromisoformat(start_ts)
        monday = start - datetime.timedelta(days=start.weekday())
        sunday = monday + datetime.timedelta(days=6, hours=23, minutes=59, seconds=59)
        # count existing appointments for this student in the same calendar week by parsing stored timestamps
        cur.execute('SELECT start_ts FROM appointments WHERE student_id=?', (student_id,))
        rows = cur.fetchall()
        c = 0
        for r in rows:
            try:
                appt_dt = datetime.datetime.fromisoformat(r['start_ts'])
                if appt_dt >= monday and appt_dt <= sunday:
                    c += 1
            except Exception:
                continue
        if c >= 3:
            return False, 'Haftada maksimum 3 randevu hakkı dolu'
        # check teacher availability slots (if any exists, require the appointment to be inside a slot)
        cur.execute('SELECT * FROM teacher_availability WHERE teacher_id=?', (teacher_id,))
        slots = cur.fetchall()
        if slots:
            ok_slot = False
            appt_start = start
            appt_end = start + datetime.timedelta(minutes=duration_min)
            for sl in slots:
                s_start = datetime.datetime.fromisoformat(sl['start_ts'])
                s_end = datetime.datetime.fromisoformat(sl['end_ts'])
                if appt_start >= s_start and appt_end <= s_end:
                    ok_slot = True
                    break
            if not ok_slot:
                return False, 'Seçilen öğretmen bu saatte müsait değil'
        cur.execute('INSERT INTO appointments (student_id,teacher_id,start_ts,duration_min) VALUES (?,?,?,?)', (student_id,teacher_id,start_ts,duration_min))
        self.conn.commit()
        logging.info(f'Appointment added for student {student_id} with teacher {teacher_id} at {start_ts}')
        return True, None

    def list_appointments(self, student_id=None):
        cur = self.conn.cursor()
        if student_id:
            cur.execute('SELECT * FROM appointments WHERE student_id=? ORDER BY start_ts DESC', (student_id,))
        else:
            cur.execute('SELECT * FROM appointments ORDER BY start_ts DESC')
        return [dict(r) for r in cur.fetchall()]

    def delete_appointment(self, appt_id):
        cur = self.conn.cursor()
        cur.execute('DELETE FROM appointments WHERE id=?', (appt_id,))
        self.conn.commit()
        logging.info(f'Appointment {appt_id} deleted')

    # Student edits
    def edit_student(self, student_id, name=None, surname=None, tc=None, parent_chat_id=None):
        cur = self.conn.cursor()
        # build dynamic update
        fields = []
        params = []
        if name is not None:
            fields.append('name=?'); params.append(name)
        if surname is not None:
            fields.append('surname=?'); params.append(surname)
        if tc is not None:
            fields.append('tc=?'); params.append(tc)
        if parent_chat_id is not None:
            fields.append('parent_chat_id=?'); params.append(parent_chat_id)
        if not fields:
            return False
        params.append(student_id)
        sql = f"UPDATE students SET {', '.join(fields)} WHERE id=?"
        cur.execute(sql, params)
        self.conn.commit()
        logging.info(f'Student {student_id} updated')
        return True

    def delete_student(self, student_id):
        cur = self.conn.cursor()
        cur.execute('DELETE FROM students WHERE id=?', (student_id,))
        self.conn.commit()
        logging.info(f'Student {student_id} deleted')

    # Exams
    def add_exam(self, student_id, name, score, ts=None):
        cur = self.conn.cursor()
        if ts is None:
            ts = datetime.datetime.now().isoformat()
        cur.execute('INSERT INTO exams (student_id,name,score,ts) VALUES (?,?,?,?)', (student_id,name,score,ts))
        self.conn.commit()
        logging.info(f'Exam {name} for student {student_id} added')

    def list_exams(self, student_id):
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM exams WHERE student_id=? ORDER BY ts DESC', (student_id,))
        return [dict(r) for r in cur.fetchall()]

    # Backup
    def backup(self, dest_dir='backups'):
        os.makedirs(dest_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        dest = os.path.join(dest_dir, f'smartdershane_{ts}.db')
        self.conn.commit()
        self.conn.close()
        shutil.copyfile(self.path, dest)
        # reopen
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        cur = self.conn.cursor()
        cur.execute('INSERT INTO backups (path,ts) VALUES (?,?)', (dest,ts))
        self.conn.commit()
        logging.info(f'Database backed up to {dest}')
        return dest

    # Settings
    def set_setting(self, k, v):
        cur = self.conn.cursor()
        cur.execute('INSERT OR REPLACE INTO settings (k,v) VALUES (?,?)', (k,v))
        self.conn.commit()

    def get_setting(self, k):
        cur = self.conn.cursor()
        cur.execute('SELECT v FROM settings WHERE k=?', (k,))
        r = cur.fetchone()
        return r['v'] if r else None

    def close(self):
        self.conn.close()
