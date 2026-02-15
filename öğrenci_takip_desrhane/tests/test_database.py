import datetime
import pytest
from database import Database


def test_user_and_student_flow(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(str(db_path))
    # default admin exists
    users = db.list_users()
    assert any(u['username'] == 'admin' for u in users)

    # create and authenticate teacher
    db.create_user('teacher1', 'secret', 'teacher')
    users = db.list_users()
    assert any(u['username'] == 'teacher1' for u in users)
    assert db.authenticate('teacher1', 'secret', 'teacher') is not None

    # student CRUD and attendance
    db.add_student('Ali', 'Veli', '12345678901')
    students = db.list_students()
    assert len(students) == 1
    sid = students[0]['id']
    db.add_attendance(sid, 'Gelen')
    cur = db.conn.cursor()
    cur.execute('SELECT COUNT(*) as c FROM attendance')
    assert cur.fetchone()['c'] == 1
    db.close()


def test_appointments_and_availability(tmp_path):
    db_path = tmp_path / "test2.db"
    db = Database(str(db_path))
    db.create_user('teacher1', 'p', 'teacher')
    db.add_student('Deniz', 'Kaya', '98765432100')
    students = db.list_students()
    sid = students[0]['id']

    # add an availability slot for teacher id 1
    now = datetime.datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    start_ts = now.isoformat()
    end_ts = (now + datetime.timedelta(hours=2)).isoformat()
    cur = db.conn.cursor()
    cur.execute('INSERT INTO teacher_availability (teacher_id,start_ts,end_ts) VALUES (?,?,?)', (1, start_ts, end_ts))
    db.conn.commit()

    # add three appointments in the same calendar week -> allowed
    for i in range(3):
        appt_time = (now + datetime.timedelta(days=i)).isoformat()
        ok, msg = db.add_appointment(sid, 1, appt_time)
        assert ok, f"Appointment {i} should be added: {msg}"

    # fourth in same week -> rejected
    appt_time = (now + datetime.timedelta(days=4)).isoformat()
    ok, msg = db.add_appointment(sid, 1, appt_time)
    assert not ok

    # appointment outside defined availability -> rejected
    outside = (now - datetime.timedelta(days=1)).isoformat()
    ok2, msg2 = db.add_appointment(sid, 1, outside)
    assert not ok2

    db.close()
