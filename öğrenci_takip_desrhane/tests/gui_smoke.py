import os
import time
import customtkinter as ctk
from database import Database
from telegram_bot import TelegramNotifier
from main import AdminDashboard

DB_PATH = 'f:/öğrenci_takip_desrhane/test_gui.db'
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

print('Setting up DB...')
db = Database(DB_PATH)
notifier = TelegramNotifier(db)

# create a hidden root to attach CTk frames without showing window
root = ctk.CTk()
root.withdraw()

print('Creating AdminDashboard (hidden)')
admin = AdminDashboard(root, db, notifier)

print('Simulating create user via UI method')
admin.new_username.insert(0,'guisim')
admin.new_password.insert(0,'gpwd')
admin.new_role.set('teacher')
admin.create_user()
print('Users after create:', db.list_users())

print('Simulating add student via UI')
admin.form_name.insert(0,'Deniz')
admin.form_surname.insert(0,'Kaya')
admin.form_tc.insert(0,'98765432100')
admin.form_parent_chat.insert(0,'')
admin.add_student()
print('Students:', db.list_students())

print('Simulating taking attendance (manual_attendance uses first student)')
admin.status_cb.set('Gelen')
admin.manual_attendance()
cur = db.conn.cursor()
cur.execute('SELECT * FROM attendance')
print('Attendance rows:', len(cur.fetchall()))

print('Simulating save token')
admin.token_entry.delete(0,'end')
admin.token_entry.insert(0,'TEST_TOKEN_123')
admin.save_token()
print('Token stored:', db.get_setting('telegram_token'))

print('Simulating teacher availability and appointment via UI')
admin.av_teacher_id.insert(0,'2')
now = time.strftime('%Y-%m-%dT09:00:00')
admin.av_start.insert(0, now)
admin.av_end.insert(0, now.replace('09:00:00','11:00:00'))
admin.save_availability()
# create appointment inside slot
admin.app_student_id.insert(0,'1')
admin.app_teacher_id.insert(0,'2')
admin.app_datetime.insert(0, now.replace('T','T09:30:00'))
admin.create_appointment()
print('Appointments:', db.list_appointments())

print('Simulating student edit')
admin.edit_student_id.insert(0,'1')
admin.edit_student_name.insert(0,'DenizUpdated')
admin.update_student_action()
print('Students after update:', db.list_students())

print('Simulating exam add')
admin.exam_student_id.insert(0,'1')
admin.exam_name.insert(0,'Matematik')
admin.exam_score.insert(0,'92')
admin.add_exam_action()
print('Exams for student:', db.list_exams(1))

print('Simulating cancel appointment')
appts = db.list_appointments()
if appts:
    admin.cancel_appt_id.insert(0,str(appts[0]['id']))
    admin.cancel_appointment()
    print('Appointments after cancel:', db.list_appointments())

print('GUI smoke simulation complete')

# cleanup
root.destroy()
db.close()
