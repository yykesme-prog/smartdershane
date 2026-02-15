import os
import threading
import datetime
import customtkinter as ctk
from tkinter import messagebox
from database import Database
from telegram_bot import TelegramNotifier
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

APP_DB = 'f:/öğrenci_takip_desrhane/smartdershane.db'


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode('light')
        ctk.set_default_color_theme('blue')
        self.title('SmartDershane')
        self.geometry('900x600')

        self.db = Database(APP_DB)
        self.notifier = TelegramNotifier(self.db)

        self.current_user = None

        self.login_frame = LoginFrame(self, self.db, self.on_login)
        self.login_frame.pack(fill='both', expand=True)

    def on_login(self, user):
        self.current_user = user
        self.login_frame.pack_forget()
        role = user['role']
        if role == 'admin':
            self.dashboard = AdminDashboard(self, self.db, self.notifier)
        elif role == 'teacher':
            self.dashboard = TeacherDashboard(self, self.db, self.notifier)
        else:
            self.dashboard = ParentDashboard(self, self.db)
        self.dashboard.pack(fill='both', expand=True)


class LoginFrame(ctk.CTkFrame):
    def __init__(self, parent, db, login_callback):
        super().__init__(parent)
        self.db = db
        self.login_callback = login_callback

        self.grid_columnconfigure((0,1), weight=1)
        ctk.CTkLabel(self, text='SmartDershane Giriş', font=ctk.CTkFont(size=24, weight='bold')).grid(row=0, column=0, columnspan=2, pady=20)

        ctk.CTkLabel(self, text='Kullanıcı adı:').grid(row=1, column=0, sticky='e', padx=10, pady=5)
        self.username = ctk.CTkEntry(self)
        self.username.grid(row=1, column=1, sticky='w', padx=10)

        ctk.CTkLabel(self, text='Parola:').grid(row=2, column=0, sticky='e', padx=10, pady=5)
        self.password = ctk.CTkEntry(self, show='*')
        self.password.grid(row=2, column=1, sticky='w', padx=10)

        ctk.CTkLabel(self, text='Rol:').grid(row=3, column=0, sticky='e', padx=10, pady=5)
        self.role_var = ctk.CTkComboBox(self, values=['admin','teacher','parent'])
        self.role_var.grid(row=3, column=1, sticky='w', padx=10)

        ctk.CTkButton(self, text='Giriş', command=self.do_login).grid(row=4, column=0, columnspan=2, pady=20)

    def do_login(self):
        user = self.db.authenticate(self.username.get(), self.password.get(), self.role_var.get())
        if user:
            self.login_callback(user)
        else:
            messagebox.showerror('Hata', 'Geçersiz kimlik bilgileri')


class AdminDashboard(ctk.CTkFrame):
    def __init__(self, parent, db, notifier):
        super().__init__(parent)
        self.db = db
        self.notifier = notifier

        self.left = ctk.CTkFrame(self, width=300)
        self.left.pack(side='left', fill='y', padx=10, pady=10)
        self.right = ctk.CTkFrame(self)
        self.right.pack(side='right', fill='both', expand=True, padx=10, pady=10)

        ctk.CTkLabel(self.left, text='Öğrenciler', font=ctk.CTkFont(size=18)).pack(pady=5)
        self.student_list = ctk.CTkScrollableFrame(self.left, width=260, height=300)
        self.student_list.pack()
        self.refresh_students()

        ctk.CTkButton(self.left, text='Yenile', command=self.refresh_students).pack(pady=5)

        # right: CRUD and attendance
        self.form_name = ctk.CTkEntry(self.right, placeholder_text='İsim')
        self.form_surname = ctk.CTkEntry(self.right, placeholder_text='Soyisim')
        self.form_tc = ctk.CTkEntry(self.right, placeholder_text='TC Kimlik')
        self.form_parent_chat = ctk.CTkEntry(self.right, placeholder_text='Veli Telegram Chat ID')
        for w in (self.form_name, self.form_surname, self.form_tc, self.form_parent_chat):
            w.pack(pady=6, fill='x')

        ctk.CTkButton(self.right, text='Öğrenci Ekle', command=self.add_student).pack(pady=6)

        # Attendance status selector
        ctk.CTkLabel(self.right, text='Yoklama Durumu:').pack(pady=(10,0))
        self.status_cb = ctk.CTkComboBox(self.right, values=['Gelen','Geç Kaldı','Gelmedi','İzinli'])
        self.status_cb.set('Gelen')
        self.status_cb.pack(pady=6, fill='x')
        ctk.CTkButton(self.right, text='Seçiliye Yoklama Al', command=self.manual_attendance).pack(pady=6)

        # Appointment section
        ctk.CTkLabel(self.right, text='Randevu Oluştur (15dk, max 3/hafta)').pack(pady=(10,0))
        self.app_student_id = ctk.CTkEntry(self.right, placeholder_text='Öğrenci ID')
        self.app_teacher_id = ctk.CTkEntry(self.right, placeholder_text='Öğretmen ID')
        self.app_datetime = ctk.CTkEntry(self.right, placeholder_text='YYYY-MM-DDTHH:MM')
        for w in (self.app_student_id, self.app_teacher_id, self.app_datetime):
            w.pack(pady=4, fill='x')
        ctk.CTkButton(self.right, text='Randevu Kaydet', command=self.create_appointment).pack(pady=6)
        ctk.CTkLabel(self.right, text='Randevu İptal (ID)').pack(pady=(6,0))
        self.cancel_appt_id = ctk.CTkEntry(self.right, placeholder_text='Randevu ID')
        self.cancel_appt_id.pack(pady=4, fill='x')
        ctk.CTkButton(self.right, text='Randevu İptal Et', command=self.cancel_appointment).pack(pady=4)

        # Teacher availability editor
        ctk.CTkLabel(self.right, text='Öğretmen Müsaitlik (Başlat/Bitiş)').pack(pady=(10,0))
        self.av_teacher_id = ctk.CTkEntry(self.right, placeholder_text='Öğretmen ID')
        self.av_start = ctk.CTkEntry(self.right, placeholder_text='YYYY-MM-DDTHH:MM')
        self.av_end = ctk.CTkEntry(self.right, placeholder_text='YYYY-MM-DDTHH:MM')
        for w in (self.av_teacher_id, self.av_start, self.av_end):
            w.pack(pady=3, fill='x')
        ctk.CTkButton(self.right, text='Müsaitlik Kaydet', command=self.save_availability).pack(pady=6)

        # Telegram token yönetimi
        ctk.CTkLabel(self.right, text='Telegram Bot Token (settings)').pack(pady=(10,0))
        self.token_entry = ctk.CTkEntry(self.right, placeholder_text='Bot Token')
        self.token_entry.pack(pady=4, fill='x')
        # önceden kaydedilmiş token varsa göster
        try:
            tok = self.db.get_setting('telegram_token')
            if tok:
                self.token_entry.insert(0, tok)
        except Exception:
            pass
        ctk.CTkButton(self.right, text='Token Kaydet', command=self.save_token).pack(pady=6)

        # attendance log area
        self.att_frame = ctk.CTkFrame(self.right)
        self.att_frame.pack(fill='both', expand=True, pady=8)
        ctk.CTkLabel(self.att_frame, text='Son Yoklamalar').pack()
        self.att_list = ctk.CTkScrollableFrame(self.att_frame, height=200)
        self.att_list.pack(fill='both', expand=True)
        self.refresh_attendance()

        # User management
        ctk.CTkLabel(self.left, text='Kullanıcı Yönetimi', font=ctk.CTkFont(size=16)).pack(pady=(10,4))
        self.user_frame = ctk.CTkFrame(self.left)
        self.user_frame.pack(fill='x', padx=6)
        self.new_username = ctk.CTkEntry(self.user_frame, placeholder_text='Kullanıcı adı')
        self.new_password = ctk.CTkEntry(self.user_frame, placeholder_text='Parola', show='*')
        self.new_role = ctk.CTkComboBox(self.user_frame, values=['admin','teacher','parent'])
        for w in (self.new_username, self.new_password, self.new_role):
            w.pack(fill='x', pady=3)
        ctk.CTkButton(self.user_frame, text='Kullanıcı Ekle', command=self.create_user).pack(pady=4, fill='x')

        self.users_listbox = ctk.CTkScrollableFrame(self.left, width=260, height=140)
        self.users_listbox.pack(pady=6)
        self.refresh_users()
        ctk.CTkButton(self.left, text='Seçili Sil', command=self.delete_selected_user).pack(pady=4)
        # change password
        self.pw_user_id = ctk.CTkEntry(self.left, placeholder_text='Kullanıcı ID (şifre değiştir)')
        self.pw_new = ctk.CTkEntry(self.left, placeholder_text='Yeni Parola', show='*')
        self.pw_user_id.pack(fill='x', padx=6, pady=3)
        self.pw_new.pack(fill='x', padx=6, pady=3)
        ctk.CTkButton(self.left, text='Şifre Değiştir', command=self.change_password_action).pack(pady=4)
        # Student edit/delete controls
        ctk.CTkLabel(self.left, text='Öğrenci Düzenle/Sil', font=ctk.CTkFont(size=12)).pack(pady=(8,2))
        self.edit_student_id = ctk.CTkEntry(self.left, placeholder_text='Öğrenci ID')
        self.edit_student_name = ctk.CTkEntry(self.left, placeholder_text='Yeni İsim')
        self.edit_student_surname = ctk.CTkEntry(self.left, placeholder_text='Yeni Soyisim')
        for w in (self.edit_student_id, self.edit_student_name, self.edit_student_surname):
            w.pack(fill='x', padx=6, pady=2)
        ctk.CTkButton(self.left, text='Güncelle', command=self.update_student_action).pack(pady=4)
        ctk.CTkButton(self.left, text='Öğrenci Sil', command=self.delete_student_action).pack(pady=4)

        # Exam add
        ctk.CTkLabel(self.right, text='Sınav Ekle', font=ctk.CTkFont(size=12)).pack(pady=(8,2))
        self.exam_student_id = ctk.CTkEntry(self.right, placeholder_text='Öğrenci ID')
        self.exam_name = ctk.CTkEntry(self.right, placeholder_text='Sınav Adı')
        self.exam_score = ctk.CTkEntry(self.right, placeholder_text='Puan (0-100)')
        for w in (self.exam_student_id, self.exam_name, self.exam_score):
            w.pack(fill='x', pady=2)
        ctk.CTkButton(self.right, text='Sınav Kaydet', command=self.add_exam_action).pack(pady=4)

    def refresh_students(self):
        for child in self.student_list.winfo_children():
            child.destroy()
        students = self.db.list_students()
        for s in students:
            lbl = ctk.CTkLabel(self.student_list, text=f"{s['id']}: {s['name']} {s['surname']}")
            lbl.pack(anchor='w', padx=6, pady=2)

    def add_student(self):
        name = self.form_name.get()
        surname = self.form_surname.get()
        tc = self.form_tc.get()
        chat = self.form_parent_chat.get()
        if not name or not surname:
            messagebox.showwarning('Eksik', 'İsim veya soyisim eksik')
            return
        self.db.add_student(name, surname, tc, chat)
        self.refresh_students()

    # User management actions
    def refresh_users(self):
        for child in self.users_listbox.winfo_children():
            child.destroy()
        try:
            users = self.db.list_users()
        except Exception:
            users = []
        for u in users:
            lbl = ctk.CTkLabel(self.users_listbox, text=f"{u['id']}: {u['username']} ({u['role']})")
            lbl.pack(anchor='w', padx=6, pady=2)

    def create_user(self):
        uname = self.new_username.get().strip()
        pwd = self.new_password.get()
        role = self.new_role.get()
        if not uname or not pwd or not role:
            messagebox.showwarning('Hata','Tüm alanları doldurun')
            return
        try:
            self.db.create_user(uname, pwd, role)
            messagebox.showinfo('Tamam','Kullanıcı oluşturuldu')
            self.new_username.delete(0,'end')
            self.new_password.delete(0,'end')
            self.refresh_users()
        except Exception as e:
            messagebox.showerror('Hata', str(e))

    def delete_selected_user(self):
        kids = self.users_listbox.winfo_children()
        if not kids:
            messagebox.showinfo('Bilgi','Kullanıcı yok')
            return
        first = kids[0].cget('text').split(':')[0]
        uid = int(first)
        confirm = messagebox.askyesno('Onay','Seçili kullanıcıyı silmek istiyor musunuz?')
        if not confirm:
            return
        try:
            self.db.delete_user(uid)
            messagebox.showinfo('Tamam','Kullanıcı silindi')
            self.refresh_users()
        except Exception as e:
            messagebox.showerror('Hata', str(e))

    def change_password_action(self):
        try:
            uid = int(self.pw_user_id.get())
            newp = self.pw_new.get()
            if not newp:
                messagebox.showwarning('Hata','Yeni parola boş')
                return
            self.db.change_password(uid, newp)
            messagebox.showinfo('Tamam','Parola değiştirildi')
            self.pw_user_id.delete(0,'end')
            self.pw_new.delete(0,'end')
        except Exception as e:
            messagebox.showerror('Hata', str(e))

    def manual_attendance(self):
        # take first listed student as example
        kids = self.student_list.winfo_children()
        if not kids:
            messagebox.showinfo('Bilgi','Öğrenci yok')
            return
        first = kids[0].cget('text').split(':')[0]
        sid = int(first)
        status = self.status_cb.get()
        self.db.add_attendance(sid, status)
        threading.Thread(target=self.notifier.notify_parent_attendance, args=(sid,status), daemon=True).start()
        messagebox.showinfo('Yoklama','Yoklama kaydedildi ve veli bilgilendirildi (varsa)')
        self.refresh_attendance()

    def refresh_attendance(self):
        for child in self.att_list.winfo_children():
            child.destroy()
        # fetch last 20
        cur = self.db.conn.cursor()
        cur.execute('SELECT a.*, s.name, s.surname FROM attendance a LEFT JOIN students s ON a.student_id=s.id ORDER BY a.ts DESC LIMIT 20')
        for r in cur.fetchall():
            status = r['status']
            text = f"{r['ts'][:19]} - {r['name']} {r['surname']} - {status}"
            color = 'green' if status=='Gelen' else ('yellow' if status=='Geç Kaldı' else ('red' if status=='Gelmedi' else 'blue'))
            lbl = ctk.CTkLabel(self.att_list, text=text, fg_color=color, corner_radius=6)
            lbl.pack(fill='x', padx=6, pady=3)

    def create_appointment(self):
            def cancel_appointment(self):
                try:
                    aid = int(self.cancel_appt_id.get())
                    self.db.delete_appointment(aid)
                    messagebox.showinfo('Tamam','Randevu iptal edildi')
                    self.refresh_attendance()
                except Exception as ex:
                    messagebox.showerror('Hata', str(ex))
            def update_student_action(self):
                try:
                    sid = int(self.edit_student_id.get())
                    name = self.edit_student_name.get().strip() or None
                    surname = self.edit_student_surname.get().strip() or None
                    if not any([name, surname]):
                        messagebox.showwarning('Hata','En az bir alanı doldurun')
                        return
                    self.db.edit_student(sid, name=name, surname=surname)
                    messagebox.showinfo('Tamam','Öğrenci güncellendi')
                    self.refresh_students()
                except Exception as e:
                    messagebox.showerror('Hata', str(e))

            def delete_student_action(self):
                try:
                    sid = int(self.edit_student_id.get())
                    confirm = messagebox.askyesno('Onay','Öğrenciyi silmek istiyor musunuz?')
                    if not confirm:
                        return
                    self.db.delete_student(sid)
                    messagebox.showinfo('Tamam','Öğrenci silindi')
                    self.refresh_students()
                except Exception as e:
                    messagebox.showerror('Hata', str(e))

            def add_exam_action(self):
                try:
                    sid = int(self.exam_student_id.get())
                    name = self.exam_name.get().strip()
                    score = int(self.exam_score.get())
                    if not name or score < 0 or score > 100:
                        messagebox.showwarning('Hata','Geçerli sınav ve puan girin')
                        return
                    self.db.add_exam(sid, name, score)
                    messagebox.showinfo('Tamam','Sınav kaydedildi')
                except Exception as e:
                    messagebox.showerror('Hata', str(e))
        try:
            sid = int(self.app_student_id.get())
            tid = int(self.app_teacher_id.get())
            dt = self.app_datetime.get()
            # expect ISO like '2026-02-15T14:30'
            ok, err = self.db.add_appointment(sid, tid, dt, duration_min=15)
            if not ok:
                messagebox.showerror('Randevu Hatası', err)
            else:
                messagebox.showinfo('Tamam', 'Randevu kaydedildi')
                self.refresh_attendance()
        except Exception as e:
            messagebox.showerror('Hata', str(e))

    def save_availability(self):
        try:
            tid = int(self.av_teacher_id.get())
            s = self.av_start.get()
            e = self.av_end.get()
            # validate
            datetime.datetime.fromisoformat(s)
            datetime.datetime.fromisoformat(e)
            cur = self.db.conn.cursor()
            cur.execute('INSERT INTO teacher_availability (teacher_id,start_ts,end_ts) VALUES (?,?,?)', (tid,s,e))
            self.db.conn.commit()
            messagebox.showinfo('Tamam','Müsaitlik kaydedildi')
        except Exception as ex:
            messagebox.showerror('Hata', str(ex))

    def save_token(self):
        token = self.token_entry.get().strip()
        if not token:
            messagebox.showwarning('Hata','Token boş olamaz')
            return
        try:
            self.db.set_setting('telegram_token', token)
            try:
                self.notifier.set_token(token)
            except Exception:
                pass
            messagebox.showinfo('Tamam','Telegram token kaydedildi')
        except Exception as ex:
            messagebox.showerror('Hata', str(ex))


class TeacherDashboard(AdminDashboard):
    pass


class ParentDashboard(ctk.CTkFrame):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        ctk.CTkLabel(self, text='Veli Paneli', font=ctk.CTkFont(size=20)).pack(pady=10)
        # Dinamik grafik: DB'den son 6 sınav
        ctk.CTkLabel(self, text='Öğrenci ID giriniz:').pack()
        self.parent_student_id = ctk.CTkEntry(self, placeholder_text='Öğrenci ID')
        self.parent_student_id.pack(pady=4)
        ctk.CTkButton(self, text='Grafiği Göster', command=self.show_student_graph).pack(pady=6)
        self.graph_frame = ctk.CTkFrame(self)
        self.graph_frame.pack(fill='both', expand=True)

    def show_student_graph(self):
        for w in self.graph_frame.winfo_children():
            w.destroy()
        try:
            sid = int(self.parent_student_id.get())
        except:
            messagebox.showerror('Hata','Geçersiz öğrenci ID')
            return
        cur = self.db.conn.cursor()
        cur.execute('SELECT name,score,ts FROM exams WHERE student_id=? ORDER BY ts DESC LIMIT 6', (sid,))
        rows = cur.fetchall()[::-1]
        if not rows:
            messagebox.showinfo('Bilgi','Sınav bulunamadı')
            return
        tests = [r['name'] for r in rows]
        scores = [r['score'] for r in rows]
        fig, ax = plt.subplots(figsize=(6,3))
        ax.plot(tests, scores, marker='o', color='seagreen')
        ax.set_ylim(0,100)
        ax.set_title('Son Sınav Performansı')
        canvas = FigureCanvasTkAgg(fig, master=self.graph_frame)
        canvas.get_tk_widget().pack()

    


if __name__ == '__main__':
    app = App()
    app.mainloop()
