from database import Database
from telegram_bot import TelegramNotifier
import os

DB_PATH = 'f:/öğrenci_takip_desrhane/test_auto.db'
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

print('Creating DB...')
db = Database(DB_PATH)
print('DB created')

# Test user creation and authentication
print('Creating user: teacher1')
db.create_user('teacher1','tpass','teacher')
print('Listing users:')
users = db.list_users()
print(users)
assert any(u['username']=='teacher1' for u in users), 'teacher1 not found'

print('Authenticating teacher1...')
user = db.authenticate('teacher1','tpass','teacher')
assert user is not None and user['username']=='teacher1'
print('Auth OK')

# Test student add
print('Adding student...')
db.add_student('Ali','Veli','12345678901','')
students = db.list_students()
print('Students:', students)
assert len(students) == 1
sid = students[0]['id']

# Test attendance
print('Adding attendance...')
db.add_attendance(sid, 'Gelen')
cur = db.conn.cursor()
cur.execute('SELECT * FROM attendance WHERE student_id=?', (sid,))
rows = cur.fetchall()
print('Attendance rows:', len(rows))
assert len(rows) == 1

# Test appointment rules: create 3 appointments in same week
print('Testing appointments limit...')
from datetime import datetime, timedelta
# pick base as this week's Monday to ensure all appointments fall in same calendar week
today = datetime.now()
base = today - timedelta(days=today.weekday()) + timedelta(hours=9)
for i in range(3):
    ts = (base + timedelta(days=i)).isoformat()
    ok,err = db.add_appointment(sid, 1, ts, duration_min=15)
    print('Add appt', i, ok, err)
    assert ok, f'Failed to add appointment {i} : {err}'
# fourth should fail
ts = (base + timedelta(days=4)).isoformat()
ok,err = db.add_appointment(sid,1,ts, duration_min=15)
print('Add appt 4', ok, err)
assert not ok, 'Fourth appointment should be rejected'

# Test teacher availability enforcement
print('Testing teacher availability...')
# clear appointments
cur.execute('DELETE FROM appointments')
db.conn.commit()
# add availability only for a specific slot
start = (base + timedelta(hours=9)).replace(minute=0, second=0, microsecond=0)
end = start + timedelta(hours=2)
cur.execute('INSERT INTO teacher_availability (teacher_id,start_ts,end_ts) VALUES (?,?,?)', (1,start.isoformat(), end.isoformat()))
db.conn.commit()
# try appointment outside slot
outside = (start - timedelta(hours=3)).isoformat()
ok,err = db.add_appointment(sid,1,outside, duration_min=15)
print('Outside slot', ok, err)
assert not ok
# inside slot
inside = (start + timedelta(minutes=30)).isoformat()
ok,err = db.add_appointment(sid,1,inside, duration_min=15)
print('Inside slot', ok, err)
assert ok

# Telegram notifier (no token set -> should not send)
print('Testing telegram notifier...')
notifier = TelegramNotifier(db)
res = notifier.notify_parent_attendance(sid, 'Gelen')
print('Notifier result:', res)
# should be True/False depending on parent_chat_id; it's empty so False

print('All tests passed')

db.close()
