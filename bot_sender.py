import sys
import asyncio
import os
import random
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError, ChatWriteForbiddenError
from telethon.tl.types import UserStatusOnline, UserStatusRecently, UserStatusOffline
from telethon.tl.types import InputMediaUploadedDocument, InputMediaUploadedPhoto
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout,
                             QHBoxLayout, QWidget, QComboBox, QTextEdit,
                             QPushButton, QLabel, QMessageBox, QLineEdit,
                             QDialog, QProgressBar, QListWidget, QListWidgetItem,
                             QCheckBox, QSpinBox, QSystemTrayIcon, QFileDialog,
                             QTabWidget, QGroupBox, QScrollArea)
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QFont, QIcon
import tempfile
import json

# Настройки бота
BOT_TOKEN = 'YOUR_BOT_TOKEN_HERE'  # Замените на токен вашего бота
API_ID = '21339848'
API_HASH = '3bc2385cae1af7eb7bc29302e69233a6'

SESSION_FILE = os.path.join(tempfile.gettempdir(), 'telegram_session')
USERS_FILE = 'users_bot.txt'
SETTINGS_FILE = 'settings_bot.txt'


class SettingsManager:
    @staticmethod
    def load_settings():
        """Загружает настройки из файла"""
        settings = {
            'daily_limit': 10,
            'min_delay': 3600,
            'max_delay': 5400,
            'bot_token': BOT_TOKEN,
            'parse_mode': 'HTML'
        }

        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line:
                            key, value = line.split('=', 1)
                            if key in settings:
                                if key == 'daily_limit':
                                    settings[key] = int(value)
                                elif key in ['min_delay', 'max_delay']:
                                    settings[key] = int(value)
                                else:
                                    settings[key] = value
            except Exception as e:
                print(f"Ошибка загрузки настроек: {e}")

        return settings

    @staticmethod
    def save_settings(settings):
        """Сохраняет настройки в файл"""
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                for key, value in settings.items():
                    f.write(f"{key}={value}\n")
            return True
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")
            return False


class UserManager:
    @staticmethod
    def load_users():
        """Загружает пользователей из файла"""
        users = {}
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                user_data = json.loads(line)
                                user_id = user_data.get('user_id')
                                username = user_data.get('username', '')
                                first_name = user_data.get('first_name', '')
                                last_name = user_data.get('last_name', '')
                                status = user_data.get('status', 'не отправлено')
                                send_time = user_data.get('send_time', '')

                                if user_id:
                                    users[user_id] = {
                                        'username': username,
                                        'first_name': first_name,
                                        'last_name': last_name,
                                        'status': status,
                                        'send_time': send_time
                                    }
                            except json.JSONDecodeError:
                                # Старый формат для обратной совместимости
                                if ',' in line:
                                    parts = line.split(',')
                                    if len(parts) >= 2:
                                        user_id = parts[0]
                                        username = parts[1] if len(parts) > 1 else ''
                                        status = parts[2] if len(parts) > 2 else 'не отправлено'
                                        send_time = parts[3] if len(parts) > 3 else ''
                                        users[user_id] = {
                                            'username': username,
                                            'first_name': '',
                                            'last_name': '',
                                            'status': status,
                                            'send_time': send_time
                                        }
            except Exception as e:
                print(f"Ошибка загрузки файла: {e}")
        return users

    @staticmethod
    def save_users(users):
        """Сохраняет пользователей в файл"""
        try:
            with open(USERS_FILE, 'w', encoding='utf-8') as f:
                for user_id, data in users.items():
                    user_data = {
                        'user_id': user_id,
                        'username': data.get('username', ''),
                        'first_name': data.get('first_name', ''),
                        'last_name': data.get('last_name', ''),
                        'status': data.get('status', 'не отправлено'),
                        'send_time': data.get('send_time', '')
                    }
                    f.write(json.dumps(user_data, ensure_ascii=False) + '\n')
            return True
        except Exception as e:
            print(f"Ошибка сохранения файла: {e}")
            return False

    @staticmethod
    def add_user(user_id, username='', first_name='', last_name=''):
        """Добавляет пользователя в файл"""
        users = UserManager.load_users()

        # Очищаем username от @ если есть
        if username and username.startswith('@'):
            username = username[1:]

        if user_id not in users:
            users[user_id] = {
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'status': 'не отправлено',
                'send_time': ''
            }
            return UserManager.save_users(users)
        else:
            # Обновляем существующего пользователя
            users[user_id]['username'] = username
            users[user_id]['first_name'] = first_name
            users[user_id]['last_name'] = last_name
            return UserManager.save_users(users)

    @staticmethod
    def update_user_status(user_id, status, send_time=''):
        """Обновляет статус пользователя"""
        users = UserManager.load_users()
        if user_id in users:
            users[user_id]['status'] = status
            if send_time:
                users[user_id]['send_time'] = send_time
            return UserManager.save_users(users)
        return False

    @staticmethod
    def get_unsent_users():
        """Возвращает список пользователей со статусом 'не отправлено'"""
        users = UserManager.load_users()
        unsent_users = []
        for user_id, data in users.items():
            if data['status'] == 'не отправлено':
                unsent_users.append(user_id)
        return unsent_users

    @staticmethod
    def get_today_sent_count():
        """Возвращает количество сообщений, отправленных сегодня"""
        users = UserManager.load_users()
        today = datetime.now().strftime('%d.%m.%Y')
        today_sent = 0

        for user_id, data in users.items():
            if data['status'] == 'отправлено' and data['send_time'].startswith(today):
                today_sent += 1

        return today_sent


class BotSendThread(QThread):
    progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, user_ids, message, image_path=None, video_path=None, bot_token=None, parse_mode='HTML'):
        super().__init__()
        self.user_ids = user_ids
        self.message = message
        self.image_path = image_path
        self.video_path = video_path
        self.bot_token = bot_token
        self.parse_mode = parse_mode
        self.is_running = True

    def stop_sending(self):
        """Останавливает отправку"""
        self.is_running = False

    def run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.send_via_bot())
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                loop.close()

    async def send_via_bot(self):
        """Отправка сообщений через бота"""
        if not self.bot_token or self.bot_token == 'YOUR_BOT_TOKEN_HERE':
            raise Exception("Не установлен токен бота. Настройте токен в настройках.")

        total_users = len(self.user_ids)
        sent_count = 0
        failed_count = 0

        for index, user_id in enumerate(self.user_ids):
            if not self.is_running:
                return f"⏹️ Отправка остановлена. Отправлено: {sent_count}/{total_users}"

            try:
                self.progress.emit(f"📨 Отправка пользователю {user_id}...", index + 1, total_users)

                # Отправка через бота
                success = await self.send_to_user(user_id)

                if success:
                    sent_count += 1
                    UserManager.update_user_status(user_id, 'отправлено', datetime.now().strftime('%d.%m.%Y %H:%M:%S'))
                else:
                    failed_count += 1

                # Задержка между сообщениями
                await asyncio.sleep(1)

            except Exception as e:
                failed_count += 1
                self.progress.emit(f"❌ Ошибка у {user_id}: {str(e)}", index + 1, total_users)
                await asyncio.sleep(2)

        return f"✅ Отправка завершена! Успешно: {sent_count}, Ошибок: {failed_count}"

    async def send_to_user(self, user_id):
        """Отправка одного сообщения пользователю через бота"""
        import aiohttp
        from aiohttp import FormData

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/"

            # Если есть изображение
            if self.image_path and os.path.exists(self.image_path):
                form_data = FormData()
                form_data.add_field('chat_id', str(user_id))

                with open(self.image_path, 'rb') as img_file:
                    form_data.add_field('photo', img_file.read(), filename=os.path.basename(self.image_path))

                if self.message:
                    form_data.add_field('caption', self.message)
                    if self.parse_mode:
                        form_data.add_field('parse_mode', self.parse_mode)

                async with aiohttp.ClientSession() as session:
                    async with session.post(url + 'sendPhoto', data=form_data) as response:
                        result = await response.json()
                        return result.get('ok', False)

            # Если есть видео
            elif self.video_path and os.path.exists(self.video_path):
                form_data = FormData()
                form_data.add_field('chat_id', str(user_id))

                with open(self.video_path, 'rb') as vid_file:
                    form_data.add_field('video', vid_file.read(), filename=os.path.basename(self.video_path))

                if self.message:
                    form_data.add_field('caption', self.message)
                    if self.parse_mode:
                        form_data.add_field('parse_mode', self.parse_mode)

                async with aiohttp.ClientSession() as session:
                    async with session.post(url + 'sendVideo', data=form_data) as response:
                        result = await response.json()
                        return result.get('ok', False)

            # Если только текст
            elif self.message:
                data = {
                    'chat_id': user_id,
                    'text': self.message
                }

                if self.parse_mode:
                    data['parse_mode'] = self.parse_mode

                async with aiohttp.ClientSession() as session:
                    async with session.post(url + 'sendMessage', json=data) as response:
                        result = await response.json()
                        return result.get('ok', False)

            return False

        except Exception as e:
            print(f"Ошибка отправки через бота: {e}")
            return False


class UserSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_users = []
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Выбор пользователей для рассылки')
        self.setFixedSize(600, 500)
        layout = QVBoxLayout()

        # Поиск
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel('Поиск:'))
        self.search_edit = QLineEdit()
        self.search_edit.textChanged.connect(self.filter_users)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)

        # Список пользователей с чекбоксами
        self.users_list = QListWidget()
        layout.addWidget(self.users_list)

        # Кнопки выбора
        button_layout = QHBoxLayout()

        self.select_all_btn = QPushButton('Выбрать всех')
        self.select_all_btn.clicked.connect(self.select_all)
        button_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton('Снять выделение')
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        button_layout.addWidget(self.deselect_all_btn)

        self.select_unsent_btn = QPushButton('Выбрать неотправленных')
        self.select_unsent_btn.clicked.connect(self.select_unsent)
        button_layout.addWidget(self.select_unsent_btn)

        layout.addLayout(button_layout)

        # Кнопки подтверждения
        confirm_layout = QHBoxLayout()

        self.ok_btn = QPushButton('OK')
        self.ok_btn.setStyleSheet('background-color: #4CAF50; color: white;')
        self.ok_btn.clicked.connect(self.accept)
        confirm_layout.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton('Отмена')
        self.cancel_btn.setStyleSheet('background-color: #f44336; color: white;')
        self.cancel_btn.clicked.connect(self.reject)
        confirm_layout.addWidget(self.cancel_btn)

        layout.addLayout(confirm_layout)
        self.setLayout(layout)

        self.load_users()

    def load_users(self):
        """Загружает пользователей в список"""
        self.users_list.clear()
        users = UserManager.load_users()

        for user_id, data in users.items():
            username = data.get('username', '')
            first_name = data.get('first_name', '')
            last_name = data.get('last_name', '')
            status = data.get('status', 'не отправлено')

            # Формируем отображаемое имя
            display_name = f"ID: {user_id}"
            if username:
                display_name += f" | @{username}"
            if first_name or last_name:
                display_name += f" | {first_name} {last_name}".strip()
            display_name += f" | {status}"

            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, user_id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.users_list.addItem(item)

    def filter_users(self):
        """Фильтрует пользователей по поисковому запросу"""
        search_text = self.search_edit.text().lower()

        for i in range(self.users_list.count()):
            item = self.users_list.item(i)
            item_text = item.text().lower()
            item.setHidden(search_text not in item_text)

    def select_all(self):
        """Выбирает всех пользователей"""
        for i in range(self.users_list.count()):
            item = self.users_list.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.Checked)

    def deselect_all(self):
        """Снимает выделение со всех пользователей"""
        for i in range(self.users_list.count()):
            item = self.users_list.item(i)
            item.setCheckState(Qt.Unchecked)

    def select_unsent(self):
        """Выбирает только неотправленных пользователей"""
        for i in range(self.users_list.count()):
            item = self.users_list.item(i)
            if not item.isHidden() and "не отправлено" in item.text():
                item.setCheckState(Qt.Checked)

    def get_selected_users(self):
        """Возвращает список выбранных пользователей"""
        selected = []
        for i in range(self.users_list.count()):
            item = self.users_list.item(i)
            if item.checkState() == Qt.Checked:
                user_id = item.data(Qt.UserRole)
                selected.append(user_id)
        return selected

    def accept(self):
        """Подтверждение выбора"""
        self.selected_users = self.get_selected_users()
        if not self.selected_users:
            QMessageBox.warning(self, 'Ошибка', 'Выберите хотя бы одного пользователя')
            return
        super().accept()


class BotSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = SettingsManager.load_settings()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Настройки бота')
        self.setFixedSize(500, 450)
        layout = QVBoxLayout()

        # Токен бота
        layout.addWidget(QLabel('Токен бота:'))
        self.token_edit = QLineEdit()
        self.token_edit.setText(self.settings.get('bot_token', ''))
        self.token_edit.setPlaceholderText('Введите токен вашего бота...')
        layout.addWidget(self.token_edit)

        layout.addWidget(QLabel('Лимит сообщений в день:'))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 1000)
        self.limit_spin.setValue(self.settings.get('daily_limit', 10))
        layout.addWidget(self.limit_spin)

        layout.addWidget(QLabel('Минимальная задержка (секунды):'))
        self.min_delay_spin = QSpinBox()
        self.min_delay_spin.setRange(1, 86400)
        self.min_delay_spin.setValue(self.settings.get('min_delay', 3600))
        layout.addWidget(self.min_delay_spin)

        layout.addWidget(QLabel('Максимальная задержка (секунды):'))
        self.max_delay_spin = QSpinBox()
        self.max_delay_spin.setRange(1, 86400)
        self.max_delay_spin.setValue(self.settings.get('max_delay', 5400))
        layout.addWidget(self.max_delay_spin)

        # Настройки форматирования
        layout.addWidget(QLabel('Форматирование текста:'))
        self.parse_mode_combo = QComboBox()
        self.parse_mode_combo.addItem('HTML', 'HTML')
        self.parse_mode_combo.addItem('Markdown', 'Markdown')
        self.parse_mode_combo.addItem('MarkdownV2', 'MarkdownV2')
        self.parse_mode_combo.addItem('Без форматирования', 'None')

        current_mode = self.settings.get('parse_mode', 'HTML')
        index = self.parse_mode_combo.findData(current_mode)
        if index >= 0:
            self.parse_mode_combo.setCurrentIndex(index)
        layout.addWidget(self.parse_mode_combo)

        # Инструкция по форматированию
        format_info = QLabel(
            'Поддерживаемое форматирование:\n'
            '• HTML: <b>жирный</b>, <i>курсив</i>, <u>подчеркивание</u>\n'
            '• Markdown: *жирный*, _курсив_, `код`\n'
            '• MarkdownV2: *жирный*, _курсив_, __подчеркнутый__'
        )
        format_info.setStyleSheet('color: gray; font-size: 10px; background-color: #f5f5f5; padding: 5px;')
        format_info.setWordWrap(True)
        layout.addWidget(format_info)

        # Инструкция по получению токена
        info_label = QLabel(
            'Как получить токен бота:\n'
            '1. Найти @BotFather в Telegram\n'
            '2. Отправить команду /newbot\n'
            '3. Следовать инструкциям\n'
            '4. Скопировать полученный токен'
        )
        info_label.setStyleSheet('color: gray; font-size: 10px;')
        layout.addWidget(info_label)

        # Кнопки
        button_layout = QHBoxLayout()

        self.save_btn = QPushButton('Сохранить')
        self.save_btn.setStyleSheet('background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;')
        self.save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton('Отмена')
        self.cancel_btn.setStyleSheet('background-color: #f44336; color: white; font-weight: bold; padding: 8px;')
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def save_settings(self):
        token = self.token_edit.text().strip()
        if not token:
            QMessageBox.warning(self, 'Ошибка', 'Введите токен бота')
            return

        self.settings['bot_token'] = token
        self.settings['daily_limit'] = self.limit_spin.value()
        self.settings['min_delay'] = self.min_delay_spin.value()
        self.settings['max_delay'] = self.max_delay_spin.value()

        parse_mode = self.parse_mode_combo.currentData()
        if parse_mode == 'None':
            parse_mode = None
        self.settings['parse_mode'] = parse_mode

        if SettingsManager.save_settings(self.settings):
            QMessageBox.information(self, 'Успех', 'Настройки сохранены!')
            self.accept()
        else:
            QMessageBox.warning(self, 'Ошибка', 'Не удалось сохранить настройки')


class MarkdownHelperDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Помощник по форматированию')
        self.setFixedSize(500, 400)
        layout = QVBoxLayout()

        # HTML форматирование
        html_group = QGroupBox('HTML форматирование')
        html_layout = QVBoxLayout()

        html_examples = [
            ('Жирный текст', '<b>жирный текст</b>'),
            ('Курсив', '<i>курсив</i>'),
            ('Подчеркивание', '<u>подчеркивание</u>'),
            ('Зачеркивание', '<s>зачеркивание</s>'),
            ('Ссылка', '<a href="https://example.com">текст ссылки</a>'),
            ('Моноширинный', '<code>моноширинный</code>'),
            ('Преформатированный', '<pre>преформатированный</pre>')
        ]

        for desc, example in html_examples:
            example_layout = QHBoxLayout()
            example_layout.addWidget(QLabel(f"{desc}:"))
            example_edit = QLineEdit(example)
            example_edit.setReadOnly(True)
            example_edit.setStyleSheet('background-color: #f0f0f0;')
            copy_btn = QPushButton('Копировать')
            copy_btn.clicked.connect(lambda checked, text=example: self.copy_to_clipboard(text))
            example_layout.addWidget(example_edit)
            example_layout.addWidget(copy_btn)
            html_layout.addLayout(example_layout)

        html_group.setLayout(html_layout)
        layout.addWidget(html_group)

        # Markdown форматирование
        md_group = QGroupBox('Markdown форматирование')
        md_layout = QVBoxLayout()

        md_examples = [
            ('Жирный текст', '*жирный текст*'),
            ('Курсив', '_курсив_'),
            ('Моноширинный', '`моноширинный`'),
            ('Ссылка', '[текст ссылки](https://example.com)')
        ]

        for desc, example in md_examples:
            example_layout = QHBoxLayout()
            example_layout.addWidget(QLabel(f"{desc}:"))
            example_edit = QLineEdit(example)
            example_edit.setReadOnly(True)
            example_edit.setStyleSheet('background-color: #f0f0f0;')
            copy_btn = QPushButton('Копировать')
            copy_btn.clicked.connect(lambda checked, text=example: self.copy_to_clipboard(text))
            example_layout.addWidget(example_edit)
            example_layout.addWidget(copy_btn)
            md_layout.addLayout(example_layout)

        md_group.setLayout(md_layout)
        layout.addWidget(md_group)

        # Кнопка закрытия
        close_btn = QPushButton('Закрыть')
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.setLayout(layout)

    def copy_to_clipboard(self, text):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        QMessageBox.information(self, 'Успех', 'Текст скопирован в буфер обмена')


class TelegramBotApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = SettingsManager.load_settings()
        self.send_thread = None
        self.current_image_path = None
        self.current_video_path = None
        self.init_ui()
        self.refresh_users_list()

    def init_ui(self):
        self.setWindowTitle('Менеджер рассылки через Telegram Bot')
        self.setFixedSize(800, 700)

        central_widget = QWidget()
        layout = QVBoxLayout()

        # Вкладки
        self.tabs = QTabWidget()

        # Вкладка рассылки
        send_tab = QWidget()
        send_layout = QVBoxLayout()

        # Сообщение
        message_layout = QHBoxLayout()
        message_layout.addWidget(QLabel('Текст сообщения:'))

        self.format_help_btn = QPushButton('❓ Помощник по форматированию')
        self.format_help_btn.setStyleSheet('background-color: #FF9800; color: white; padding: 4px;')
        self.format_help_btn.clicked.connect(self.show_format_help)
        message_layout.addWidget(self.format_help_btn)

        send_layout.addLayout(message_layout)

        self.message_text = QTextEdit()
        self.message_text.setMinimumHeight(100)
        self.message_text.setPlaceholderText(
            'Введите текст сообщения...\n\n'
            'Примеры форматирования:\n'
            'HTML: <b>жирный</b> <i>курсив</i> <u>подчеркивание</u>\n'
            'Markdown: *жирный* _курсив_ `код`\n'
            'MarkdownV2: *жирный* _курсив_ __подчеркнутый__'
        )
        send_layout.addWidget(self.message_text)

        # Медиа файлы
        media_layout = QHBoxLayout()

        self.image_btn = QPushButton('📷 Выбрать изображение')
        self.image_btn.clicked.connect(self.select_image)
        media_layout.addWidget(self.image_btn)

        self.video_btn = QPushButton('🎥 Выбрать видео')
        self.video_btn.clicked.connect(self.select_video)
        media_layout.addWidget(self.video_btn)

        self.clear_media_btn = QPushButton('❌ Очистить медиа')
        self.clear_media_btn.clicked.connect(self.clear_media)
        media_layout.addWidget(self.clear_media_btn)

        send_layout.addLayout(media_layout)

        # Статус медиа
        self.media_status = QLabel('Медиа файлы не выбраны')
        self.media_status.setStyleSheet('color: gray;')
        send_layout.addWidget(self.media_status)

        # Кнопки отправки
        send_buttons_layout = QHBoxLayout()

        self.select_users_btn = QPushButton('👥 Выбрать пользователей')
        self.select_users_btn.setStyleSheet('background-color: #2196F3; color: white; font-weight: bold; padding: 8px;')
        self.select_users_btn.clicked.connect(self.select_users)
        send_buttons_layout.addWidget(self.select_users_btn)

        self.send_selected_btn = QPushButton('📤 Отправить выбранным')
        self.send_selected_btn.setStyleSheet(
            'background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;')
        self.send_selected_btn.clicked.connect(self.send_to_selected)
        send_buttons_layout.addWidget(self.send_selected_btn)

        self.send_unsent_btn = QPushButton('🚀 Отправить неотправленным')
        self.send_unsent_btn.setStyleSheet('background-color: #FF9800; color: white; font-weight: bold; padding: 8px;')
        self.send_unsent_btn.clicked.connect(self.send_to_unsent)
        send_buttons_layout.addWidget(self.send_unsent_btn)

        send_layout.addLayout(send_buttons_layout)

        # Кнопка остановки
        self.stop_send_btn = QPushButton('⏹️ Остановить отправку')
        self.stop_send_btn.setStyleSheet('background-color: #f44336; color: white; font-weight: bold; padding: 8px;')
        self.stop_send_btn.clicked.connect(self.stop_sending)
        self.stop_send_btn.setEnabled(False)
        send_layout.addWidget(self.stop_send_btn)

        send_tab.setLayout(send_layout)
        self.tabs.addTab(send_tab, '📨 Рассылка')

        # Вкладка пользователей
        users_tab = QWidget()
        users_layout = QVBoxLayout()

        # Управление пользователями
        users_manage_layout = QHBoxLayout()

        self.add_user_btn = QPushButton('➕ Добавить пользователя')
        self.add_user_btn.setStyleSheet('background-color: #4CAF50; color: white; padding: 6px;')
        self.add_user_btn.clicked.connect(self.add_user_dialog)
        users_manage_layout.addWidget(self.add_user_btn)

        self.import_users_btn = QPushButton('📥 Импорт пользователей')
        self.import_users_btn.setStyleSheet('background-color: #2196F3; color: white; padding: 6px;')
        self.import_users_btn.clicked.connect(self.import_users)
        users_manage_layout.addWidget(self.import_users_btn)

        self.bulk_import_btn = QPushButton('📝 Массовый импорт')
        self.bulk_import_btn.setStyleSheet('background-color: #9C27B0; color: white; padding: 6px;')
        self.bulk_import_btn.clicked.connect(self.bulk_import_dialog)
        users_manage_layout.addWidget(self.bulk_import_btn)

        self.export_users_btn = QPushButton('📤 Экспорт пользователей')
        self.export_users_btn.setStyleSheet('background-color: #FF9800; color: white; padding: 6px;')
        self.export_users_btn.clicked.connect(self.export_users)
        users_manage_layout.addWidget(self.export_users_btn)

        users_layout.addLayout(users_manage_layout)

        # Список пользователей
        self.users_list = QListWidget()
        users_layout.addWidget(self.users_list)

        users_tab.setLayout(users_layout)
        self.tabs.addTab(users_tab, '👥 Пользователи')

        layout.addWidget(self.tabs)

        # Прогресс бар
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        # Статус
        self.status_label = QLabel('Готов к работе')
        self.status_label.setStyleSheet('color: green;')
        layout.addWidget(self.status_label)

        # Кнопки управления
        buttons_layout = QHBoxLayout()

        self.settings_btn = QPushButton('⚙️ Настройки бота')
        self.settings_btn.setStyleSheet('background-color: #795548; color: white; font-weight: bold; padding: 8px;')
        self.settings_btn.clicked.connect(self.show_settings)
        buttons_layout.addWidget(self.settings_btn)

        self.format_help_main_btn = QPushButton('📝 Помощник по форматированию')
        self.format_help_main_btn.setStyleSheet(
            'background-color: #607D8B; color: white; font-weight: bold; padding: 8px;')
        self.format_help_main_btn.clicked.connect(self.show_format_help)
        buttons_layout.addWidget(self.format_help_main_btn)

        layout.addLayout(buttons_layout)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Таймер для обновления статуса
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(5000)

        self.update_status()

    def show_format_help(self):
        """Показывает диалог помощи по форматированию"""
        dialog = MarkdownHelperDialog(self)
        dialog.exec_()

    def select_image(self):
        """Выбор изображения"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Выберите изображение', '',
            'Images (*.png *.jpg *.jpeg *.bmp *.gif)'
        )
        if file_path:
            self.current_image_path = file_path
            self.current_video_path = None
            self.update_media_status()

    def select_video(self):
        """Выбор видео"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Выберите видео', '',
            'Videos (*.mp4 *.avi *.mov *.mkv)'
        )
        if file_path:
            self.current_video_path = file_path
            self.current_image_path = None
            self.update_media_status()

    def clear_media(self):
        """Очистка выбранных медиа файлов"""
        self.current_image_path = None
        self.current_video_path = None
        self.update_media_status()

    def update_media_status(self):
        """Обновление статуса медиа файлов"""
        if self.current_image_path:
            self.media_status.setText(f'📷 Изображение: {os.path.basename(self.current_image_path)}')
            self.media_status.setStyleSheet('color: green;')
        elif self.current_video_path:
            self.media_status.setText(f'🎥 Видео: {os.path.basename(self.current_video_path)}')
            self.media_status.setStyleSheet('color: green;')
        else:
            self.media_status.setText('Медиа файлы не выбраны')
            self.media_status.setStyleSheet('color: gray;')

    def select_users(self):
        """Открывает диалог выбора пользователей"""
        dialog = UserSelectionDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            selected_count = len(dialog.selected_users)
            self.status_label.setText(f'Выбрано пользователей: {selected_count}')
            self.selected_users = dialog.selected_users

    def send_to_selected(self):
        """Отправка выбранным пользователям"""
        if not hasattr(self, 'selected_users') or not self.selected_users:
            QMessageBox.warning(self, 'Ошибка', 'Сначала выберите пользователей')
            return

        self.start_sending(self.selected_users)

    def send_to_unsent(self):
        """Отправка неотправленным пользователям"""
        unsent_users = UserManager.get_unsent_users()
        if not unsent_users:
            QMessageBox.information(self, 'Информация', 'Нет неотправленных пользователей')
            return

        self.start_sending(unsent_users)

    def start_sending(self, user_ids):
        """Запуск отправки сообщений"""
        message = self.message_text.toPlainText().strip()

        if not message and not self.current_image_path and not self.current_video_path:
            QMessageBox.warning(self, 'Ошибка', 'Введите текст сообщения или выберите медиа файл')
            return

        if not self.settings.get('bot_token') or self.settings['bot_token'] == 'YOUR_BOT_TOKEN_HERE':
            QMessageBox.warning(self, 'Ошибка', 'Сначала настройте токен бота в настройках')
            return

        self.status_label.setText('Запуск отправки...')
        self.set_buttons_enabled(False)
        self.stop_send_btn.setEnabled(True)

        parse_mode = self.settings.get('parse_mode', 'HTML')
        if parse_mode == 'None':
            parse_mode = None

        self.send_thread = BotSendThread(
            user_ids,
            message,
            self.current_image_path,
            self.current_video_path,
            self.settings['bot_token'],
            parse_mode
        )
        self.send_thread.progress.connect(self.on_send_progress)
        self.send_thread.finished.connect(self.on_send_finished)
        self.send_thread.error.connect(self.on_send_error)
        self.send_thread.start()

    def stop_sending(self):
        """Остановка отправки"""
        if self.send_thread and self.send_thread.isRunning():
            self.send_thread.stop_sending()
            self.status_label.setText('Остановка отправки...')
            self.stop_send_btn.setEnabled(False)

    def on_send_progress(self, status, current, total):
        """Обновление прогресса отправки"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(status)

    def on_send_finished(self, message):
        """Завершение отправки"""
        self.set_buttons_enabled(True)
        self.stop_send_btn.setEnabled(False)
        self.status_label.setText(message)
        self.status_label.setStyleSheet('color: green;')
        self.refresh_users_list()
        QMessageBox.information(self, 'Отправка завершена', message)

    def on_send_error(self, error_message):
        """Ошибка отправки"""
        self.set_buttons_enabled(True)
        self.stop_send_btn.setEnabled(False)
        self.status_label.setText(f'Ошибка: {error_message}')
        self.status_label.setStyleSheet('color: red;')
        QMessageBox.critical(self, 'Ошибка', f'Ошибка отправки: {error_message}')

    def set_buttons_enabled(self, enabled):
        """Включение/выключение кнопок"""
        self.select_users_btn.setEnabled(enabled)
        self.send_selected_btn.setEnabled(enabled)
        self.send_unsent_btn.setEnabled(enabled)
        self.settings_btn.setEnabled(enabled)
        self.format_help_main_btn.setEnabled(enabled)
        self.format_help_btn.setEnabled(enabled)

    def add_user_dialog(self):
        """Диалог добавления пользователя"""
        dialog = QDialog(self)
        dialog.setWindowTitle('Добавить пользователя')
        dialog.setFixedSize(300, 200)
        layout = QVBoxLayout()

        layout.addWidget(QLabel('ID пользователя:'))
        user_id_edit = QLineEdit()
        layout.addWidget(user_id_edit)

        layout.addWidget(QLabel('Username (опционально):'))
        username_edit = QLineEdit()
        layout.addWidget(username_edit)

        layout.addWidget(QLabel('Имя (опционально):'))
        first_name_edit = QLineEdit()
        layout.addWidget(first_name_edit)

        layout.addWidget(QLabel('Фамилия (опционально):'))
        last_name_edit = QLineEdit()
        layout.addWidget(last_name_edit)

        button_layout = QHBoxLayout()
        add_btn = QPushButton('Добавить')
        add_btn.clicked.connect(lambda: self.add_user(
            user_id_edit.text(),
            username_edit.text(),
            first_name_edit.text(),
            last_name_edit.text(),
            dialog
        ))
        button_layout.addWidget(add_btn)

        cancel_btn = QPushButton('Отмена')
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec_()

    def add_user(self, user_id, username, first_name, last_name, dialog):
        """Добавление пользователя"""
        if not user_id:
            QMessageBox.warning(self, 'Ошибка', 'Введите ID пользователя')
            return

        if UserManager.add_user(user_id, username, first_name, last_name):
            dialog.accept()
            self.refresh_users_list()
            QMessageBox.information(self, 'Успех', 'Пользователь добавлен')
        else:
            QMessageBox.warning(self, 'Ошибка', 'Не удалось добавить пользователя')

    def import_users(self):
        """Импорт пользователей из файла"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Выберите файл для импорта', '',
            'Text files (*.txt);;All files (*.*)'
        )
        if file_path:
            try:
                imported_count = 0
                skipped_count = 0

                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue

                        # Пробуем разные форматы
                        user_id = None
                        username = ''

                        # Формат: "1. @Mila85,1128498988"
                        if '.' in line and '@' in line and ',' in line:
                            try:
                                # Разделяем по точке и запятой
                                parts = line.split('.', 1)
                                if len(parts) > 1:
                                    rest = parts[1].strip()
                                    # Ищем последнюю запятую (разделитель между username и ID)
                                    last_comma = rest.rfind(',')
                                    if last_comma != -1:
                                        username_part = rest[:last_comma].strip()
                                        id_part = rest[last_comma + 1:].strip()

                                        # Извлекаем username (убираем @ если есть)
                                        if username_part.startswith('@'):
                                            username = username_part[1:]
                                        else:
                                            username = username_part

                                        user_id = id_part

                            except Exception as e:
                                print(f"Ошибка парсинга строки {line_num}: {e}")

                        # Формат: "1128498988" или "@username"
                        elif line.isdigit():
                            user_id = line
                        elif line.startswith('@'):
                            username = line[1:]
                            # Нужно будет получить ID позже
                        else:
                            # Пробуем как чистый ID
                            if line.isdigit():
                                user_id = line
                            else:
                                username = line

                        if user_id:
                            if UserManager.add_user(user_id, username):
                                imported_count += 1
                            else:
                                skipped_count += 1

                self.refresh_users_list()
                QMessageBox.information(
                    self, 'Импорт завершен',
                    f'Успешно импортировано: {imported_count}\nПропущено: {skipped_count}'
                )

            except Exception as e:
                QMessageBox.critical(self, 'Ошибка', f'Ошибка импорта: {str(e)}')

    def bulk_import_dialog(self):
        """Диалог массового импорта"""
        dialog = QDialog(self)
        dialog.setWindowTitle('Массовый импорт пользователей')
        dialog.setFixedSize(500, 400)
        layout = QVBoxLayout()

        layout.addWidget(QLabel('Введите данные пользователей (каждый с новой строки):'))
        layout.addWidget(QLabel('Форматы: ID, @username, или ID,username'))

        text_edit = QTextEdit()
        text_edit.setPlaceholderText(
            'Примеры:\n'
            '123456789\n'
            '@username\n'
            '123456789,username\n'
            '123456789,@username'
        )
        layout.addWidget(text_edit)

        button_layout = QHBoxLayout()
        import_btn = QPushButton('Импортировать')
        import_btn.clicked.connect(lambda: self.bulk_import(text_edit.toPlainText(), dialog))
        button_layout.addWidget(import_btn)

        cancel_btn = QPushButton('Отмена')
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec_()

    def bulk_import(self, text, dialog):
        """Массовый импорт пользователей"""
        lines = text.strip().split('\n')
        imported_count = 0
        skipped_count = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue

            user_id = None
            username = ''

            if ',' in line:
                parts = line.split(',', 1)
                user_id = parts[0].strip()
                username = parts[1].strip()
                if username.startswith('@'):
                    username = username[1:]
            elif line.startswith('@'):
                username = line[1:]
            elif line.isdigit():
                user_id = line
            else:
                # Пробуем как username без @
                username = line

            if user_id or username:
                if UserManager.add_user(user_id or '', username):
                    imported_count += 1
                else:
                    skipped_count += 1

        dialog.accept()
        self.refresh_users_list()
        QMessageBox.information(
            self, 'Импорт завершен',
            f'Успешно импортировано: {imported_count}\nПропущено: {skipped_count}'
        )

    def export_users(self):
        """Экспорт пользователей в файл"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, 'Сохранить список пользователей', 'users_export.txt',
            'Text files (*.txt);;All files (*.*)'
        )
        if file_path:
            users = UserManager.load_users()
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    for user_id, data in users.items():
                        username = data.get('username', '')
                        first_name = data.get('first_name', '')
                        last_name = data.get('last_name', '')
                        status = data.get('status', 'не отправлено')
                        send_time = data.get('send_time', '')

                        line = f"{user_id},{username},{first_name},{last_name},{status},{send_time}\n"
                        f.write(line)

                QMessageBox.information(self, 'Успех', f'Пользователи экспортированы в {file_path}')
            except Exception as e:
                QMessageBox.critical(self, 'Ошибка', f'Ошибка экспорта: {str(e)}')

    def refresh_users_list(self):
        """Обновление списка пользователей"""
        self.users_list.clear()
        users = UserManager.load_users()

        sent_count = 0
        unsent_count = 0

        for user_id, data in users.items():
            username = data.get('username', '')
            first_name = data.get('first_name', '')
            last_name = data.get('last_name', '')
            status = data.get('status', 'не отправлено')
            send_time = data.get('send_time', '')

            display_text = f"ID: {user_id}"
            if username:
                display_text += f" | @{username}"
            if first_name or last_name:
                display_text += f" | {first_name} {last_name}".strip()
            display_text += f" | Статус: {status}"
            if send_time:
                display_text += f" | {send_time}"

            item = QListWidgetItem(display_text)

            if status == 'отправлено':
                item.setForeground(Qt.darkGreen)
                sent_count += 1
            else:
                item.setForeground(Qt.darkRed)
                unsent_count += 1

            self.users_list.addItem(item)

        # Обновляем заголовок вкладки
        self.tabs.setTabText(1, f'👥 Пользователи ({sent_count}/{unsent_count})')

    def show_settings(self):
        """Показ диалога настроек"""
        dialog = BotSettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.settings = SettingsManager.load_settings()
            self.update_status()

    def update_status(self):
        """Обновление статуса"""
        total_users = len(UserManager.load_users())
        unsent_users = len(UserManager.get_unsent_users())
        today_sent = UserManager.get_today_sent_count()
        daily_limit = self.settings.get('daily_limit', 10)

        status_text = (f"Всего пользователей: {total_users} | "
                       f"Неотправленных: {unsent_users} | "
                       f"Отправлено сегодня: {today_sent}/{daily_limit}")

        self.status_label.setText(status_text)

        if today_sent >= daily_limit:
            self.status_label.setStyleSheet('color: orange;')
        else:
            self.status_label.setStyleSheet('color: green;')


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Telegram Bot Sender')
    app.setApplicationVersion('1.0')

    # Устанавливаем стиль
    app.setStyle('Fusion')

    window = TelegramBotApp()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()