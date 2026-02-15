
import requests
import logging
from datetime import datetime

logging.basicConfig(filename='smartdershane.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


class TelegramNotifier:
    def __init__(self, db):
        self.db = db
        self.token = db.get_setting('telegram_token')

    def set_token(self, token: str):
        self.token = token
        try:
            self.db.set_setting('telegram_token', token)
            logging.info('Telegram token kaydedildi')
        except Exception:
            logging.exception('Token kaydedilemedi')

    def _send(self, chat_id, text):
        if not self.token or not chat_id:
            logging.warning('Telegram token veya chat_id eksik; mesaj gönderilemedi')
            return False
        url = f'https://api.telegram.org/bot{self.token}/sendMessage'
        payload = {'chat_id': chat_id, 'text': text}
        try:
            r = requests.post(url, data=payload, timeout=5)
            if r.status_code == 200:
                logging.info(f'Telegram message sent to {chat_id}')
                return True
            else:
                logging.error(f'Telegram error {r.status_code} {r.text}')
                return False
        except Exception:
            logging.exception('Telegram gönderilemedi')
            return False

    def notify_parent_attendance(self, student_id, status):
        s = self.db.get_student(student_id)
        if not s:
            return False
        chat = s.get('parent_chat_id')
        text = f"Öğrenciniz {s.get('name')} {s.get('surname')} - durum: {status}. Saat: {datetime_now()}"
        self._send(chat, text)
        return True


def datetime_now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


