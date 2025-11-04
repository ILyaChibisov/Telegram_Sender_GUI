import sys
import asyncio
import os
import random
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError, ChatWriteForbiddenError, ChannelPrivateError, \
    InviteRequestSentError, UserAlreadyParticipantError
from telethon.tl.functions.messages import GetDialogsRequest, ImportChatInviteRequest, GetDiscussionMessageRequest, \
    SearchRequest
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest, GetFullChannelRequest, \
    GetChannelsRequest
from telethon.tl.types import InputPeerEmpty, Channel, ChatForbidden, Message, Chat, User, InputMessagesFilterEmpty
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout,
                             QHBoxLayout, QWidget, QComboBox, QTextEdit,
                             QPushButton, QLabel, QMessageBox, QLineEdit,
                             QDialog, QProgressBar, QListWidget, QListWidgetItem, QCheckBox, QSpinBox,
                             QSystemTrayIcon, QGroupBox, QScrollArea, QFileDialog, QSplitter)
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QFont, QIcon
import tempfile
import re

API_ID = '21339848'
API_HASH = '3bc2385cae1af7eb7bc29302e69233a6'

SESSION_FILE = os.path.join(tempfile.gettempdir(), 'telegram_session')
COMMENTS_FILE = 'comments_chats_list.txt'
SETTINGS_FILE = 'comments_settings.txt'


class SettingsManager:
    @staticmethod
    def load_settings():
        """Загружает настройки из файла"""
        settings = {
            'daily_limit': 10,
            'min_delay': 3600,
            'max_delay': 5400
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
                                else:
                                    settings[key] = int(value)
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


class CommentsManager:
    @staticmethod
    def load_chats():
        """Загружает чаты из файла"""
        chats = {}
        if os.path.exists(COMMENTS_FILE):
            try:
                with open(COMMENTS_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if ',' in line:
                            parts = line.split(',')
                            if len(parts) >= 9:
                                chat_id = parts[0]
                                chat_title = parts[1]
                                chat_type = parts[2]
                                access_type = parts[3]
                                can_comment = parts[4] == 'True'
                                can_video = parts[5] == 'True'
                                last_post_id = parts[6]
                                last_post_date = parts[7]
                                status = parts[8] if len(parts) > 8 else 'не отправлено'
                                send_time = parts[9] if len(parts) > 9 else ''
                                username = parts[10] if len(parts) > 10 else ''

                                chats[chat_id] = {
                                    'title': chat_title,
                                    'type': chat_type,
                                    'access_type': access_type,
                                    'can_comment': can_comment,
                                    'can_video': can_video,
                                    'last_post_id': last_post_id,
                                    'last_post_date': last_post_date,
                                    'status': status,
                                    'send_time': send_time,
                                    'username': username
                                }
            except Exception as e:
                print(f"Ошибка загрузки файла чатов: {e}")
        return chats

    @staticmethod
    def save_chats(chats):
        """Сохраняет чаты в файл"""
        try:
            with open(COMMENTS_FILE, 'w', encoding='utf-8') as f:
                for chat_id, data in chats.items():
                    title = data['title']
                    chat_type = data['type']
                    access_type = data['access_type']
                    can_comment = str(data['can_comment'])
                    can_video = str(data['can_video'])
                    last_post_id = data.get('last_post_id', '0')
                    last_post_date = data.get('last_post_date', '')
                    status = data['status']
                    send_time = data.get('send_time', '')
                    username = data.get('username', '')
                    f.write(
                        f"{chat_id},{title},{chat_type},{access_type},{can_comment},{can_video},{last_post_id},{last_post_date},{status},{send_time},{username}\n")
            return True
        except Exception as e:
            print(f"Ошибка сохранения файла чатов: {e}")
            return False

    @staticmethod
    def add_chats(new_chats):
        """Добавляет новые чаты в файл"""
        existing_chats = CommentsManager.load_chats()

        for chat_id, chat_data in new_chats.items():
            if chat_id not in existing_chats:
                existing_chats[chat_id] = chat_data

        return CommentsManager.save_chats(existing_chats)

    @staticmethod
    def update_chat_status(chat_id, status, send_time=''):
        """Обновляет статус чата"""
        chats = CommentsManager.load_chats()
        if chat_id in chats:
            chats[chat_id]['status'] = status
            if send_time:
                chats[chat_id]['send_time'] = send_time
            return CommentsManager.save_chats(chats)
        return False

    @staticmethod
    def delete_chats(chat_ids):
        """Удаляет чаты из файла"""
        chats = CommentsManager.load_chats()
        for chat_id in chat_ids:
            if chat_id in chats:
                del chats[chat_id]
        return CommentsManager.save_chats(chats)

    @staticmethod
    def get_unsent_chats():
        """Возвращает список чатов со статусом 'не отправлено'"""
        chats = CommentsManager.load_chats()
        unsent_chats = {chat_id: data for chat_id, data in chats.items()
                        if data['status'] == 'не отправлено'}
        return unsent_chats

    @staticmethod
    def get_today_sent_count():
        """Возвращает количество сообщений, отправленных сегодня"""
        chats = CommentsManager.load_chats()
        today = datetime.now().strftime('%d.%m.%Y')
        today_sent = 0

        for chat_id, data in chats.items():
            if data['status'] == 'отправлено' and data['send_time'].startswith(today):
                today_sent += 1

        return today_sent

    @staticmethod
    def was_sent_today(chat_id):
        """Проверяет, было ли отправлено сообщение в этот чат сегодня"""
        chats = CommentsManager.load_chats()
        if chat_id in chats:
            chat_data = chats[chat_id]
            if chat_data['status'] == 'отправлено':
                send_time = chat_data.get('send_time', '')
                today = datetime.now().strftime('%d.%m.%Y')
                return send_time.startswith(today)
        return False


class SendCodeThread(QThread):
    finished = pyqtSignal(bool, str, str)
    error = pyqtSignal(str)

    def __init__(self, phone):
        super().__init__()
        self.phone = phone

    def run(self):
        loop = None
        max_attempts = 3
        attempt = 0

        while attempt < max_attempts:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
                result = loop.run_until_complete(self.send_code(client))
                self.finished.emit(True, result[0], result[1])
                break

            except Exception as e:
                attempt += 1
                if attempt == max_attempts:
                    self.error.emit(str(e))
                else:
                    import time
                    time.sleep(2)
            finally:
                if loop and not loop.is_closed():
                    loop.close()

    async def send_code(self, client):
        for attempt in range(3):
            try:
                await client.connect()
                if client.is_connected():
                    break
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(1)

        if not client.is_connected():
            raise Exception("Не удалось подключиться к Telegram")

        result = await client.send_code_request(self.phone)
        await client.disconnect()
        return f"Код отправлен на {self.phone}", result.phone_code_hash


class SignInThread(QThread):
    finished = pyqtSignal(bool, str)
    need_password = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, phone, code, phone_code_hash, password=None):
        super().__init__()
        self.phone = phone
        self.code = code
        self.phone_code_hash = phone_code_hash
        self.password = password

    def run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
            result = loop.run_until_complete(self.sign_in(client))
            self.finished.emit(True, result)

        except SessionPasswordNeededError:
            self.need_password.emit()
        except Exception as e:
            self.error.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                loop.close()

    async def sign_in(self, client):
        await client.connect()
        if not client.is_connected():
            await client.connect()

        try:
            await client.sign_in(
                phone=self.phone,
                code=self.code,
                phone_code_hash=self.phone_code_hash
            )

            if await client.is_user_authorized():
                await client.disconnect()
                return "Авторизация успешна!"
            else:
                await client.disconnect()
                return "Ошибка авторизации"

        except SessionPasswordNeededError:
            if self.password:
                await client.sign_in(password=self.password)
                if await client.is_user_authorized():
                    await client.disconnect()
                    return "Авторизация с 2FA успешна!"
                else:
                    await client.disconnect()
                    return "Ошибка авторизации с паролем"
            else:
                await client.disconnect()
                raise SessionPasswordNeededError()


class AuthDialog(QDialog):
    authorization_success = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.phone_code_hash = None
        self.phone = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Авторизация Telegram')
        self.setFixedSize(400, 350)
        layout = QVBoxLayout()

        title_label = QLabel('Авторизация в Telegram')
        title_label.setStyleSheet('font-size: 16px; font-weight: bold;')
        layout.addWidget(title_label)

        layout.addWidget(QLabel('Номер телефона:'))
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText('+79123456789')
        layout.addWidget(self.phone_edit)

        self.send_code_btn = QPushButton('Прислать код')
        self.send_code_btn.setStyleSheet('background-color: #4CAF50; color: white; font-weight: bold;')
        self.send_code_btn.clicked.connect(self.send_code)
        layout.addWidget(self.send_code_btn)

        layout.addWidget(QLabel('_' * 50))

        layout.addWidget(QLabel('Код подтверждения:'))
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText('Введите код из Telegram')
        self.code_edit.setEnabled(False)
        layout.addWidget(self.code_edit)

        self.password_label = QLabel('Пароль 2FA (если установлен):')
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText('Введите пароль двухфакторной аутентификации')
        self.password_label.setVisible(False)
        self.password_edit.setVisible(False)
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_edit)

        self.auth_btn = QPushButton('Авторизоваться')
        self.auth_btn.setStyleSheet('background-color: #2196F3; color: white; font-weight: bold;')
        self.auth_btn.clicked.connect(self.sign_in)
        self.auth_btn.setEnabled(False)
        layout.addWidget(self.auth_btn)

        self.status_label = QLabel('Введите номер телефона и нажмите "Прислать код"')
        self.status_label.setStyleSheet('color: blue;')
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def send_code(self):
        phone = self.phone_edit.text().strip()

        if not phone:
            QMessageBox.warning(self, 'Ошибка', 'Введите номер телефона')
            return

        if not phone.startswith('+'):
            QMessageBox.warning(self, 'Ошибка', 'Номер должен начинаться с + и кода страны')
            return

        self.phone = phone
        self.send_code_btn.setEnabled(False)
        self.phone_edit.setEnabled(False)
        self.status_label.setText('Отправка кода...')

        self.send_code_thread = SendCodeThread(phone)
        self.send_code_thread.finished.connect(self.on_code_sent)
        self.send_code_thread.error.connect(self.on_send_code_error)
        self.send_code_thread.start()

    def on_code_sent(self, success, message, phone_code_hash):
        if success:
            self.phone_code_hash = phone_code_hash
            self.status_label.setText(message)
            self.status_label.setStyleSheet('color: green;')

            self.code_edit.setEnabled(True)
            self.auth_btn.setEnabled(True)
            self.send_code_btn.setEnabled(True)
            self.send_code_btn.setText('Отправить код повторно')

    def on_send_code_error(self, error_message):
        self.status_label.setText(f'Ошибка: {error_message}')
        self.status_label.setStyleSheet('color: red;')
        self.send_code_btn.setEnabled(True)
        self.phone_edit.setEnabled(True)
        QMessageBox.critical(self, 'Ошибка отправки кода', error_message)

    def sign_in(self):
        code = self.code_edit.text().strip()

        if not code:
            QMessageBox.warning(self, 'Ошибка', 'Введите код подтверждения')
            return

        password = self.password_edit.text().strip() if self.password_edit.isVisible() else None

        self.auth_btn.setEnabled(False)
        self.code_edit.setEnabled(False)
        if self.password_edit.isVisible():
            self.password_edit.setEnabled(False)

        self.status_label.setText('Авторизация...')

        self.sign_in_thread = SignInThread(
            self.phone, code, self.phone_code_hash, password
        )
        self.sign_in_thread.finished.connect(self.on_auth_result)
        self.sign_in_thread.need_password.connect(self.on_need_password)
        self.sign_in_thread.error.connect(self.on_sign_in_error)
        self.sign_in_thread.start()

    def on_auth_result(self, success, message):
        if success:
            self.status_label.setText(message)
            self.status_label.setStyleSheet('color: green;')
            QMessageBox.information(self, 'Успех', message)
            self.authorization_success.emit()
            self.accept()
        else:
            self.status_label.setText(f'Ошибка: {message}')
            self.status_label.setStyleSheet('color: red;')
            QMessageBox.critical(self, 'Ошибка авторизации', message)

    def on_need_password(self):
        self.status_label.setText('Требуется пароль 2FA')
        self.password_label.setVisible(True)
        self.password_edit.setVisible(True)
        self.password_edit.setEnabled(True)
        self.auth_btn.setEnabled(True)
        self.code_edit.setEnabled(True)
        QMessageBox.information(self, 'Требуется 2FA', 'Введите пароль двухфакторной аутентификации')

    def on_sign_in_error(self, error_message):
        self.status_label.setText(f'Ошибка: {error_message}')
        self.status_label.setStyleSheet('color: red;')
        self.auth_btn.setEnabled(True)
        self.code_edit.setEnabled(True)
        if self.password_edit.isVisible():
            self.password_edit.setEnabled(True)
        QMessageBox.critical(self, 'Ошибка авторизации', error_message)


class ChatListWidget(QWidget):
    def __init__(self, chat_id, chat_data, parent=None):
        super().__init__(parent)
        self.chat_id = chat_id
        self.chat_data = chat_data
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)

        self.checkbox = QCheckBox()
        layout.addWidget(self.checkbox)

        # Создаем информационную строку
        access_color = "green" if self.chat_data['access_type'] == "Открытый" else "orange"
        comment_icon = "✅" if self.chat_data['can_comment'] else "❌"
        video_icon = "✅" if self.chat_data['can_video'] else "❌"

        status_color = "green" if self.chat_data['status'] == 'отправлено' else "orange"
        send_time = self.chat_data.get('send_time', '')
        today_sent = CommentsManager.was_sent_today(self.chat_id)

        if today_sent:
            status_text = f"<span style='color: red;'>[СЕГОДНЯ ОТПРАВЛЕНО]</span>"
        else:
            status_text = f"<span style='color: {status_color};'>{self.chat_data['status']}</span>"

        info_text = f"{self.chat_data['title']} - {self.chat_data['type']} "
        info_text += f"<span style='color: {access_color};'>({self.chat_data['access_type']})</span> "
        info_text += f"Коммент:{comment_icon} Видео:{video_icon} | {status_text}"

        if send_time:
            info_text += f" | {send_time}"

        chat_info = QLabel(info_text)
        chat_info.setToolTip(f"ID: {self.chat_id}\n"
                             f"Название: {self.chat_data['title']}\n"
                             f"Тип: {self.chat_data['type']}\n"
                             f"Доступ: {self.chat_data['access_type']}\n"
                             f"Можно комментировать: {'Да' if self.chat_data['can_comment'] else 'Нет'}\n"
                             f"Можно видео: {'Да' if self.chat_data['can_video'] else 'Нет'}\n"
                             f"Статус: {self.chat_data['status']}\n"
                             f"Время отправки: {send_time if send_time else 'Не отправлялось'}")
        layout.addWidget(chat_info)

        self.setLayout(layout)


class SelectChatsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_chats = set()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Выбор групп/каналов для рассылки')
        self.setFixedSize(800, 600)
        layout = QVBoxLayout()

        # Заголовок
        title_label = QLabel('Выберите группы/каналы для рассылки комментариев:')
        title_label.setStyleSheet('font-size: 14px; font-weight: bold;')
        layout.addWidget(title_label)

        # Область с чатами
        self.chats_scroll = QScrollArea()
        self.chats_widget = QWidget()
        self.chats_layout = QVBoxLayout(self.chats_widget)
        self.chats_scroll.setWidget(self.chats_widget)
        self.chats_scroll.setWidgetResizable(True)
        layout.addWidget(self.chats_scroll)

        # Кнопки управления
        buttons_layout = QHBoxLayout()

        self.select_all_btn = QPushButton('✅ Выбрать все')
        self.select_all_btn.setStyleSheet('background-color: #4CAF50; color: white;')
        self.select_all_btn.clicked.connect(self.select_all)
        buttons_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton('❌ Снять все')
        self.deselect_all_btn.setStyleSheet('background-color: #f44336; color: white;')
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        buttons_layout.addWidget(self.deselect_all_btn)

        buttons_layout.addStretch()

        self.ok_btn = QPushButton('Сохранить выбор')
        self.ok_btn.setStyleSheet('background-color: #2196F3; color: white; font-weight: bold;')
        self.ok_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton('Отмена')
        self.cancel_btn.setStyleSheet('background-color: #607D8B; color: white;')
        self.cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_btn)

        layout.addLayout(buttons_layout)
        self.setLayout(layout)

    def load_chats(self):
        """Загружает чаты из файла"""
        # Очищаем предыдущие результаты
        for i in reversed(range(self.chats_layout.count())):
            widget = self.chats_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        chats = CommentsManager.load_chats()
        for chat_id, chat_data in chats.items():
            chat_widget = ChatListWidget(chat_id, chat_data)
            self.chats_layout.addWidget(chat_widget)

        if not chats:
            no_chats_label = QLabel('Нет сохраненных групп/каналов. Сначала выполните поиск и сохраните группы.')
            no_chats_label.setStyleSheet('color: gray; font-style: italic; padding: 20px;')
            no_chats_label.setAlignment(Qt.AlignCenter)
            self.chats_layout.addWidget(no_chats_label)

    def select_all(self):
        """Выбирает все чаты"""
        for i in range(self.chats_layout.count()):
            widget = self.chats_layout.itemAt(i).widget()
            if isinstance(widget, ChatListWidget):
                widget.checkbox.setChecked(True)

    def deselect_all(self):
        """Снимает выбор со всех чатов"""
        for i in range(self.chats_layout.count()):
            widget = self.chats_layout.itemAt(i).widget()
            if isinstance(widget, ChatListWidget):
                widget.checkbox.setChecked(False)

    def get_selected_chats(self):
        """Возвращает список выбранных чатов"""
        selected = []
        for i in range(self.chats_layout.count()):
            widget = self.chats_layout.itemAt(i).widget()
            if isinstance(widget, ChatListWidget) and widget.checkbox.isChecked():
                selected.append(widget.chat_id)
        return selected


class CommentsSearchThread(QThread):
    finished = pyqtSignal(dict)
    progress = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, search_query, limit=50):
        super().__init__()
        self.search_query = search_query
        self.limit = limit
        self.client = None

    def run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            self.client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
            result = loop.run_until_complete(self.search_groups_channels())
            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                loop.close()

    async def search_groups_channels(self):
        """Улучшенный поиск групп и каналов"""
        found_chats = {}
        count = 0

        existing_chats = CommentsManager.load_chats()

        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                await self.client.disconnect()
                raise Exception("Пользователь не авторизован")

            self.progress.emit("🔍 Начинаем улучшенный поиск групп и каналов...")

            # 1. ПОИСК В СУЩЕСТВУЮЩИХ ДИАЛОГАХ
            self.progress.emit("🔍 Ищем в ваших диалогах...")
            dialogs = await self.client.get_dialogs(limit=100)

            for dialog in dialogs:
                if count >= self.limit:
                    break

                entity = dialog.entity
                if await self.process_entity(entity, found_chats, existing_chats, dialog.name):
                    count = len(found_chats)

            # 2. УЛУЧШЕННЫЙ ГЛОБАЛЬНЫЙ ПОИСК ЧЕРЕЗ ИЗВЕСТНЫЕ USERNAME
            if self.search_query and count < self.limit:
                self.progress.emit(f"🔍 Глобальный поиск '{self.search_query}'...")

                # Попробуем найти по популярным username паттернам
                search_variants = self.generate_search_variants(self.search_query)

                for username in search_variants:
                    if count >= self.limit:
                        break
                    try:
                        # Убираем @ если есть
                        username = username.replace('@', '').strip()
                        if not username:
                            continue

                        self.progress.emit(f"🔍 Пробуем: {username}")
                        entity = await self.client.get_entity(username)
                        if await self.process_entity(entity, found_chats, existing_chats):
                            count = len(found_chats)
                            self.progress.emit(f"✅ Найден через username: {username}")

                    except Exception as e:
                        continue

            # 3. ПОИСК ЧЕРЕЗ РЕКОМЕНДАЦИИ И ПОПУЛЯРНЫЕ КАНАЛЫ
            if count < self.limit:
                await self.search_popular_channels(found_chats, existing_chats, count)
                count = len(found_chats)

            await self.client.disconnect()

            if not found_chats:
                self.progress.emit("❌ Группы/каналы с комментариями не найдены. Попробуйте другой запрос.")
            else:
                self.progress.emit(f"🎯 Поиск завершен. Найдено: {len(found_chats)}")

            return found_chats

        except Exception as e:
            try:
                await self.client.disconnect()
            except:
                pass
            raise e

    def generate_search_variants(self, query):
        """Генерирует варианты для поиска по username"""
        variants = []
        query = query.lower().strip()

        # Базовые варианты
        variants.extend([
            query,
            f"{query}_channel",
            f"{query}channel",
            f"{query}_chat",
            f"{query}chat",
            f"{query}_group",
            f"{query}group",
            f"{query}_news",
            f"{query}news",
            f"{query}_official",
            f"{query}official",
            f"{query}_russia",
            f"{query}russia",
            f"{query}_world",
            f"{query}world",
            f"the{query}",
            f"my{query}",
            f"best{query}",
        ])

        # Для русского языка
        if any(char in query for char in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'):
            variants.extend([
                f"{query}_ru",
                f"{query}ru",
                f"{query}_russian",
                f"{query}russian",
            ])

        return variants

    async def search_popular_channels(self, found_chats, existing_chats, current_count):
        """Поиск популярных каналов по категориям"""
        popular_channels = [
            # Новости
            "rian_ru", "rt_russian", "tass_agency", "meduzaproject", "bbcrussian",
            # Технологии
            "tjournal", "vcru", "roemru", "habr", "droid_news",
            # Крипта
            "cryptorussia", "bitcoin", "etherium", "cryptonews", "blockchain",
            # Спорт
            "sport24", "sportsru", "championat", "sportbox", "eurosport",
            # Музыка
            "muztv", "europaplus", "nashe", "rockradio", "hiphop",
            # Юмор
            "mdk", "pikabu", "lepra", "bashim", "joyreactor",
            # Авто
            "drive2", "autonews", "car_news", "topgear", "autoreview",
            # Игры
            "stopgame", "igromania", "kanobu", "gamer", "steam",
            # Кино
            "kinomania", "kino", "film", "cinema", "movie",
            # Еда
            "edaproject", "gastronom", "cook", "food", "restaurant",
            # Путешествия
            "travel", "tourism", "journey", "adventure", "backpacker",
        ]

        self.progress.emit("🔍 Ищем популярные каналы...")

        for username in popular_channels:
            if len(found_chats) >= self.limit:
                break

            try:
                entity = await self.client.get_entity(username)
                if await self.process_entity(entity, found_chats, existing_chats):
                    self.progress.emit(f"✅ Найден популярный канал: {username}")
            except Exception:
                continue

    async def process_entity(self, entity, found_chats, existing_chats, dialog_name=None):
        """Обрабатывает сущность (группу/канал) с ГАРАНТИРОВАННЫМ удалением тестовых сообщений"""
        try:
            # Пропускаем личные чаты
            if isinstance(entity, User):
                return False

            chat_id = str(entity.id)

            # Пропускаем чаты, которые уже есть в списке
            if chat_id in existing_chats or chat_id in found_chats:
                return False

            # Определяем тип чата
            chat_type = None
            if isinstance(entity, Channel):
                if entity.broadcast:
                    chat_type = "Канал"
                else:
                    chat_type = "Группа"
            elif isinstance(entity, Chat):
                chat_type = "Группа"

            # Пропускаем если не группа и не канал
            if not chat_type:
                return False

            chat_title = getattr(entity, 'title', dialog_name)
            if not chat_title:
                return False

            # Фильтрация по поисковому запросу (если есть)
            if self.search_query and self.search_query.lower() not in chat_title.lower():
                return False

            # Проверяем возможность комментирования
            can_comment = False
            can_video = False
            last_post_id = 0
            last_post_date = ""
            username = getattr(entity, 'username', '')
            access_type = "Закрытый"

            # Пробуем вступить в открытые чаты
            if username:
                try:
                    await self.client(JoinChannelRequest(username))
                    access_type = "Открытый"
                    self.progress.emit(f"✅ Вступили в: {chat_title}")
                except UserAlreadyParticipantError:
                    access_type = "Уже участник"
                except Exception as e:
                    access_type = "Закрытый"

            # Получаем последние сообщения для проверки комментирования
            try:
                messages = await self.client.get_messages(entity, limit=10)
                working_post_found = False

                for message in messages:
                    if not message:
                        continue

                    try:
                        # Пробуем отправить тестовый комментарий
                        test_comment = await self.client.send_message(
                            entity,
                            "💬 Тестовый комментарий",
                            comment_to=message.id
                        )

                        # ГАРАНТИРОВАННОЕ УДАЛЕНИЕ тестового комментария
                        await asyncio.sleep(2)  # Ждем отправки
                        try:
                            await self.client.delete_messages(entity, [test_comment.id])
                            self.progress.emit(f"✅ Тестовый комментарий удален в {chat_title}")
                        except Exception as e:
                            self.progress.emit(f"⚠️ Не удалось удалить тестовый комментарий в {chat_title}: {str(e)}")
                            # Продолжаем работу, но предупреждаем пользователя

                        can_comment = True
                        last_post_id = message.id
                        last_post_date = message.date.strftime('%d.%m.%Y %H:%M') if message.date else ""
                        working_post_found = True

                        # Проверяем возможность отправки видео
                        try:
                            # Создаем временный файл для теста
                            with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
                                f.write(b"test video content")
                                test_file = f.name

                            # Отправляем тестовое видео
                            test_video = await self.client.send_file(
                                entity,
                                test_file,
                                caption="Тест видео",
                                comment_to=message.id
                            )

                            # ГАРАНТИРОВАННОЕ УДАЛЕНИЕ тестового видео
                            await asyncio.sleep(2)
                            try:
                                await self.client.delete_messages(entity, [test_video.id])
                                self.progress.emit(f"✅ Тестовое видео удалено в {chat_title}")
                            except Exception as e:
                                self.progress.emit(f"⚠️ Не удалось удалить тестовое видео в {chat_title}: {str(e)}")

                            can_video = True

                            # Удаляем временный файл
                            try:
                                os.unlink(test_file)
                            except:
                                pass

                        except Exception as e:
                            can_video = False
                            # Удаляем временный файл если он создался
                            if 'test_file' in locals() and os.path.exists(test_file):
                                try:
                                    os.unlink(test_file)
                                except:
                                    pass

                        break  # Нашли рабочий пост

                    except Exception as e:
                        continue

                if not working_post_found:
                    self.progress.emit(f"⚠️ В {chat_title} не найдено постов для комментирования")
                    return False

            except Exception as e:
                self.progress.emit(f"⚠️ Не удалось проверить {chat_title}: {str(e)}")
                return False

            # Сохраняем чат если можно комментировать
            if can_comment:
                found_chats[chat_id] = {
                    'title': chat_title,
                    'type': chat_type,
                    'access_type': access_type,
                    'can_comment': can_comment,
                    'can_video': can_video,
                    'last_post_id': last_post_id,
                    'last_post_date': last_post_date,
                    'status': 'не отправлено',
                    'send_time': '',
                    'username': username
                }
                self.progress.emit(
                    f"💬 Найден: {len(found_chats)} - {chat_title} ({chat_type}) [Видео: {'✅' if can_video else '❌'}]")
                return True

            return False

        except Exception as e:
            self.progress.emit(f"⚠️ Ошибка обработки {getattr(entity, 'title', 'чата')}: {str(e)}")
            return False


class LeaveChatsThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, chat_ids_to_keep):
        super().__init__()
        self.chat_ids_to_keep = chat_ids_to_keep

    def run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
            result = loop.run_until_complete(self.leave_unused_chats(client))
            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                loop.close()

    async def leave_unused_chats(self, client):
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            raise Exception("Пользователь не авторизован")

        try:
            left_count = 0
            dialogs = await client.get_dialogs(limit=100)

            for dialog in dialogs:
                if not dialog.is_channel and not dialog.is_group:
                    continue

                entity = dialog.entity
                chat_id = str(entity.id)

                if chat_id not in self.chat_ids_to_keep:
                    try:
                        if hasattr(entity, 'username') and entity.username:
                            await client(LeaveChannelRequest(entity))
                            self.progress.emit(f"🚪 Выходим из: {dialog.name}")
                            left_count += 1
                            await asyncio.sleep(1)
                    except Exception as e:
                        self.progress.emit(f"⚠️ Не удалось выйти из {dialog.name}: {str(e)}")

            await client.disconnect()
            return left_count

        except Exception as e:
            await client.disconnect()
            raise e


class SendCommentThread(QThread):
    finished = pyqtSignal(bool, str)
    error = pyqtSignal(str)

    def __init__(self, chat_id, message, video_path=None, delay=2, delete_after_send=True, force_text_only=False):
        super().__init__()
        self.chat_id = chat_id
        self.message = message
        self.video_path = video_path
        self.delay = delay
        self.delete_after_send = delete_after_send
        self.force_text_only = force_text_only

    def run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
            result = loop.run_until_complete(self.send_comment(client))
            self.finished.emit(True, result)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                loop.close()

    async def send_comment(self, client):
        await client.connect()
        if not client.is_connected():
            await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            raise Exception("Пользователь не авторизован")

        try:
            await asyncio.sleep(self.delay)

            entity = await client.get_entity(int(self.chat_id))

            chats = CommentsManager.load_chats()
            chat_info = chats.get(self.chat_id, {})
            post_id = chat_info.get('last_post_id', 0)
            can_video = chat_info.get('can_video', False)

            if not post_id or post_id == '0':
                await client.disconnect()
                raise Exception("Не найден пост для комментирования")

            sent_message = None

            # УМНАЯ ОТПРАВКА
            if self.video_path and os.path.exists(self.video_path) and can_video and not self.force_text_only:
                if self.message.strip():
                    sent_message = await client.send_file(entity, self.video_path,
                                                          caption=self.message,
                                                          comment_to=int(post_id))
                else:
                    sent_message = await client.send_file(entity, self.video_path,
                                                          comment_to=int(post_id))
            else:
                sent_message = await client.send_message(entity, self.message,
                                                         comment_to=int(post_id))

            # ГАРАНТИРОВАННОЕ УДАЛЕНИЕ тестовых сообщений
            if self.delete_after_send and sent_message:
                await asyncio.sleep(3)  # Увеличиваем время ожидания для гарантии отправки
                try:
                    await client.delete_messages(entity, [sent_message.id])
                    # Дополнительная проверка что сообщение удалено
                    try:
                        check_msg = await client.get_messages(entity, ids=[sent_message.id])
                        if check_msg:
                            self.progress.emit(f"⚠️ Сообщение возможно не удалено в {chat_info.get('title', 'чате')}")
                    except:
                        pass  # Сообщение не найдено - значит удалено
                except Exception as e:
                    raise Exception(f"Не удалось удалить тестовое сообщение: {str(e)}")

            await asyncio.sleep(1)
            await client.disconnect()

            # Обновляем статус только если это НЕ тестовое сообщение
            if not self.delete_after_send:
                send_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
                CommentsManager.update_chat_status(self.chat_id, 'отправлено', send_time)

            chat_title = chat_info.get('title', 'чат')
            media_type = "видео+текст" if (self.video_path and can_video and not self.force_text_only) else "текст"

            if self.delete_after_send:
                return f"✅ Тестовый комментарий ({media_type}) отправлен и УДАЛЕН в {chat_title}"
            else:
                return f"✅ Комментарий ({media_type}) отправлен в {chat_title}"

        except FloodWaitError as e:
            wait_time = e.seconds
            await client.disconnect()
            raise Exception(f"⏳ Лимит Telegram! Подождите {wait_time} секунд")
        except Exception as e:
            await client.disconnect()
            raise Exception(f"❌ Ошибка: {str(e)}")


class AutoCommentsThread(QThread):
    progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, message, video_path, selected_chats, min_delay=3600, max_delay=5400, daily_limit=10):
        super().__init__()
        self.message = message
        self.video_path = video_path
        self.selected_chats = selected_chats
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.daily_limit = daily_limit
        self.is_running = True

    def stop_sending(self):
        self.is_running = False

    def run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
            result = loop.run_until_complete(self.send_comments_loop(client))
            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                loop.close()

    async def send_comments_loop(self, client):
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            raise Exception("Пользователь не авторизован")

        try:
            sent_today = CommentsManager.get_today_sent_count()
            remaining_limit = max(0, self.daily_limit - sent_today)

            if remaining_limit == 0:
                await client.disconnect()
                return f"❌ Достигнут дневной лимит ({self.daily_limit} сообщений). Отправка остановлена."

            chats_to_send = []
            for chat_id in self.selected_chats:
                if not CommentsManager.was_sent_today(chat_id):
                    chats_to_send.append(chat_id)

            if not chats_to_send:
                await client.disconnect()
                return "❌ Нет чатов для отправки (все чаты уже получили сообщение сегодня)."

            total_chats = len(chats_to_send)
            sent_count = 0
            failed_count = 0

            for i, chat_id in enumerate(chats_to_send):
                if not self.is_running:
                    await client.disconnect()
                    return f"⏸️ Отправка остановлена пользователем. Отправлено: {sent_count}"

                if sent_count >= remaining_limit:
                    await client.disconnect()
                    return f"✅ Достигнут дневной лимит ({self.daily_limit}). Отправлено: {sent_count}"

                chat_info = CommentsManager.load_chats().get(chat_id, {})
                chat_title = chat_info.get('title', 'чат')

                try:
                    post_id = chat_info.get('last_post_id', 0)
                    can_video = chat_info.get('can_video', False)

                    if not post_id or post_id == '0':
                        self.progress.emit(f"⚠️ Пропускаем {chat_title}: нет поста для комментирования",
                                           sent_count, failed_count)
                        failed_count += 1
                        continue

                    entity = await client.get_entity(int(chat_id))
                    sent_message = None

                    if self.video_path and os.path.exists(self.video_path) and can_video:
                        if self.message.strip():
                            sent_message = await client.send_file(entity, self.video_path,
                                                                  caption=self.message,
                                                                  comment_to=int(post_id))
                            media_type = "видео+текст"
                        else:
                            sent_message = await client.send_file(entity, self.video_path,
                                                                  comment_to=int(post_id))
                            media_type = "видео"
                    else:
                        sent_message = await client.send_message(entity, self.message,
                                                                 comment_to=int(post_id))
                        media_type = "текст"

                    send_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
                    CommentsManager.update_chat_status(chat_id, 'отправлено', send_time)

                    sent_count += 1
                    self.progress.emit(f"✅ Отправлено в {chat_title} ({media_type})", sent_count, failed_count)

                    if i < len(chats_to_send) - 1 and sent_count < remaining_limit:
                        delay = random.randint(self.min_delay, self.max_delay)
                        hours = delay // 3600
                        minutes = (delay % 3600) // 60

                        self.progress.emit(f"⏰ Следующее сообщение через: {hours}ч {minutes}м", sent_count,
                                           failed_count)

                        for sec in range(delay):
                            if not self.is_running:
                                await client.disconnect()
                                return f"⏸️ Отправка остановлена пользователем. Отправлено: {sent_count}"
                            await asyncio.sleep(1)

                except FloodWaitError as e:
                    wait_time = e.seconds
                    hours = wait_time // 3600
                    minutes = (wait_time % 3600) // 60
                    self.progress.emit(f"⏳ Лимит! Ждем {hours}ч {minutes}м", sent_count, failed_count)
                    failed_count += 1

                    for sec in range(wait_time):
                        if not self.is_running:
                            await client.disconnect()
                            return f"⏸️ Отправка остановлена пользователем. Отправлено: {sent_count}"
                        await asyncio.sleep(1)

                except Exception as e:
                    error_msg = str(e)
                    self.progress.emit(f"❌ Ошибка в {chat_title}: {error_msg}", sent_count, failed_count)
                    failed_count += 1
                    await asyncio.sleep(5)

            await client.disconnect()
            return f"✅ Рассылка завершена! Успешно: {sent_count}, Ошибок: {failed_count}"

        except Exception as e:
            await client.disconnect()
            raise e


class CommentsSenderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = SettingsManager.load_settings()
        self.auto_thread = None
        self.selected_chats_for_sending = set()
        self.found_chats = {}
        self.init_ui()
        self.load_chats()
        self.check_auth()

    def init_ui(self):
        self.setWindowTitle('Telegram - Автоматические комментарии в группах и каналах')
        self.setFixedSize(1200, 900)

        central_widget = QWidget()
        main_layout = QHBoxLayout()

        # Левая панель - поиск и управление чатами
        left_panel = QWidget()
        left_panel.setMaximumWidth(500)
        left_layout = QVBoxLayout()

        # Авторизация
        self.auth_btn = QPushButton('🔐 Авторизация')
        self.auth_btn.setStyleSheet('background-color: #FF9800; color: white; font-weight: bold; padding: 10px;')
        self.auth_btn.clicked.connect(self.auth_button_clicked)
        left_layout.addWidget(self.auth_btn)

        # Поиск чатов
        search_group = QGroupBox('Улучшенный поиск групп и каналов')
        search_layout = QVBoxLayout()

        search_input_layout = QHBoxLayout()
        search_input_layout.addWidget(QLabel('Ключевое слово:'))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('Например: новости, музыка, спорт')
        self.search_edit.returnPressed.connect(self.search_chats)
        search_input_layout.addWidget(self.search_edit)

        self.search_btn = QPushButton('🔍 Найти')
        self.search_btn.setStyleSheet('background-color: #2196F3; color: white; font-weight: bold;')
        self.search_btn.clicked.connect(self.search_chats)
        search_input_layout.addWidget(self.search_btn)

        search_layout.addLayout(search_input_layout)

        # Информация о поиске
        search_info = QLabel(
            '💡 Ищет в ваших диалогах + популярные каналы + глобальный поиск\n✅ Тестовые сообщения автоматически удаляются')
        search_info.setStyleSheet('color: #666; font-size: 11px; padding: 5px;')
        search_layout.addWidget(search_info)

        search_group.setLayout(search_layout)
        left_layout.addWidget(search_group)

        # Список найденных чатов
        left_layout.addWidget(QLabel('Найденные группы/каналы:'))

        self.found_chats_scroll = QScrollArea()
        self.found_chats_widget = QWidget()
        self.found_chats_layout = QVBoxLayout(self.found_chats_widget)
        self.found_chats_scroll.setWidget(self.found_chats_widget)
        self.found_chats_scroll.setWidgetResizable(True)
        self.found_chats_scroll.setMinimumHeight(200)
        left_layout.addWidget(self.found_chats_scroll)

        # Кнопки управления найденными чатами
        found_chats_buttons = QHBoxLayout()

        self.save_selected_btn = QPushButton('💾 Добавить выбранные в список')
        self.save_selected_btn.setStyleSheet('background-color: #4CAF50; color: white; font-weight: bold;')
        self.save_selected_btn.clicked.connect(self.save_selected_chats)
        found_chats_buttons.addWidget(self.save_selected_btn)

        self.clear_search_btn = QPushButton('🗑️ Очистить')
        self.clear_search_btn.setStyleSheet('background-color: #f44336; color: white; font-weight: bold;')
        self.clear_search_btn.clicked.connect(self.clear_search_results)
        found_chats_buttons.addWidget(self.clear_search_btn)

        left_layout.addLayout(found_chats_buttons)

        # Управление сохраненными чатами
        saved_chats_group = QGroupBox('Сохраненные группы/каналы')
        saved_layout = QVBoxLayout()

        saved_buttons = QHBoxLayout()

        self.select_chats_btn = QPushButton('📋 Выбрать для рассылки')
        self.select_chats_btn.setStyleSheet('background-color: #FF9800; color: white; font-weight: bold;')
        self.select_chats_btn.clicked.connect(self.select_chats_for_sending)
        saved_buttons.addWidget(self.select_chats_btn)

        self.delete_chats_btn = QPushButton('🗑️ Удалить выбранные')
        self.delete_chats_btn.setStyleSheet('background-color: #f44336; color: white; font-weight: bold;')
        self.delete_chats_btn.clicked.connect(self.delete_selected_chats)
        saved_buttons.addWidget(self.delete_chats_btn)

        saved_layout.addLayout(saved_buttons)

        # Информация о выбранных чатах
        self.selected_chats_info = QLabel('Выбрано для рассылки: 0')
        self.selected_chats_info.setStyleSheet('color: #2196F3; font-weight: bold; padding: 5px;')
        saved_layout.addWidget(self.selected_chats_info)

        saved_chats_group.setLayout(saved_layout)
        left_layout.addWidget(saved_chats_group)

        left_panel.setLayout(left_layout)
        main_layout.addWidget(left_panel)

        # Правая панель - сообщение и управление рассылкой
        right_panel = QWidget()
        right_layout = QVBoxLayout()

        # Сообщение и видео
        message_group = QGroupBox('Комментарий для рассылки')
        message_layout = QVBoxLayout()

        self.message_text = QTextEdit()
        self.message_text.setMinimumHeight(150)
        self.message_text.setPlaceholderText('Введите текст комментария для рассылки...')
        message_layout.addWidget(self.message_text)

        video_layout = QHBoxLayout()
        self.video_btn = QPushButton('🎥 Загрузить видео')
        self.video_btn.setStyleSheet('background-color: #9C27B0; color: white; font-weight: bold;')
        self.video_btn.clicked.connect(self.load_video)
        video_layout.addWidget(self.video_btn)

        self.video_label = QLabel('Видео не выбрано')
        video_layout.addWidget(self.video_label)

        self.clear_video_btn = QPushButton('❌ Очистить видео')
        self.clear_video_btn.setStyleSheet('background-color: #795548; color: white;')
        self.clear_video_btn.clicked.connect(self.clear_video)
        video_layout.addWidget(self.clear_video_btn)

        message_layout.addLayout(video_layout)

        smart_send_info = QLabel(
            '💡 Умная отправка: в чаты с видео будет отправлено видео+текст, в остальные - только текст\n✅ Тестовые сообщения автоматически удаляются')
        smart_send_info.setStyleSheet(
            'color: #666; font-size: 11px; padding: 5px; background-color: #f0f0f0; border-radius: 5px;')
        message_layout.addWidget(smart_send_info)

        message_group.setLayout(message_layout)
        right_layout.addWidget(message_group)

        # Статистика и управление
        stats_group = QGroupBox('Статистика и управление рассылкой')
        stats_layout = QVBoxLayout()

        stats_info_layout = QHBoxLayout()

        self.stats_label = QLabel('Всего в списке: 0 | Отправлено сегодня: 0/0')
        stats_info_layout.addWidget(self.stats_label)

        self.settings_btn = QPushButton('⚙️ Настройки')
        self.settings_btn.setStyleSheet('background-color: #607D8B; color: white;')
        self.settings_btn.clicked.connect(self.show_settings)
        stats_info_layout.addWidget(self.settings_btn)

        stats_layout.addLayout(stats_info_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        stats_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel('')
        self.progress_label.setVisible(False)
        stats_layout.addWidget(self.progress_label)

        send_buttons_layout = QHBoxLayout()

        self.send_test_button = QPushButton('🧪 Тестовый комментарий')
        self.send_test_button.setStyleSheet('background-color: #FF5722; color: white; font-weight: bold; padding: 8px;')
        self.send_test_button.clicked.connect(self.send_test_comment)
        send_buttons_layout.addWidget(self.send_test_button)

        self.send_selected_btn = QPushButton('📤 Отправить выбранным')
        self.send_selected_btn.setStyleSheet(
            'background-color: #FF9800; color: white; font-weight: bold; padding: 8px;')
        self.send_selected_btn.clicked.connect(self.send_to_selected)
        send_buttons_layout.addWidget(self.send_selected_btn)

        self.auto_send_btn = QPushButton('🤖 Автоматическая рассылка')
        self.auto_send_btn.setStyleSheet('background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;')
        self.auto_send_btn.clicked.connect(self.toggle_auto_send)
        send_buttons_layout.addWidget(self.auto_send_btn)

        self.stop_btn = QPushButton('⏹️ Остановить')
        self.stop_btn.setStyleSheet('background-color: #f44336; color: white; font-weight: bold; padding: 8px;')
        self.stop_btn.clicked.connect(self.stop_sending)
        self.stop_btn.setVisible(False)
        send_buttons_layout.addWidget(self.stop_btn)

        stats_layout.addLayout(send_buttons_layout)
        stats_group.setLayout(stats_layout)
        right_layout.addWidget(stats_group)

        right_panel.setLayout(right_layout)
        main_layout.addWidget(right_panel)

        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        self.update_stats()

    def check_auth(self):
        """Проверяет авторизацию используя тот же файл сессии"""
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

            async def check_auth_internal():
                try:
                    await client.connect()
                    if not client.is_connected():
                        return False
                    return await client.is_user_authorized()
                except Exception:
                    return False
                finally:
                    try:
                        await client.disconnect()
                    except:
                        pass

            is_authorized = loop.run_until_complete(check_auth_internal())

            if is_authorized:
                self.auth_btn.setText('✅ Авторизован')
                self.auth_btn.setStyleSheet(
                    'background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;')
                return True
            else:
                self.auth_btn.setText('🔐 Авторизация')
                self.auth_btn.setStyleSheet(
                    'background-color: #FF9800; color: white; font-weight: bold; padding: 10px;')
                return False

        except Exception as e:
            print(f"Ошибка проверки авторизации: {e}")
            self.auth_btn.setText('🔐 Авторизация')
            self.auth_btn.setStyleSheet('background-color: #FF9800; color: white; font-weight: bold; padding: 10px;')
            return False
        finally:
            if loop and not loop.is_closed():
                loop.close()

    def auth_button_clicked(self):
        """Обработчик нажатия кнопки авторизации"""
        if self.check_auth():  # Если уже авторизован
            reply = QMessageBox.question(self, 'Выход', 'Вы уверены, что хотите выйти?',
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.logout()
        else:
            self.show_auth_dialog()

    def logout(self):
        """Выход из системы"""
        try:
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)
            self.auth_btn.setText('🔐 Авторизация')
            self.auth_btn.setStyleSheet('background-color: #FF9800; color: white; font-weight: bold; padding: 10px;')
            QMessageBox.information(self, 'Выход', 'Вы успешно вышли из системы')
        except Exception as e:
            QMessageBox.warning(self, 'Ошибка', f'Ошибка при выходе: {str(e)}')

    def show_auth_dialog(self):
        auth_dialog = AuthDialog(self)
        auth_dialog.authorization_success.connect(self.on_auth_success)
        auth_dialog.exec_()

    def on_auth_success(self):
        """Обработчик успешной авторизации"""
        self.check_auth()
        QMessageBox.information(self, 'Успех', 'Авторизация прошла успешно!')

    def load_settings(self):
        """Загружает настройки и сохраняет в self.settings"""
        self.settings = SettingsManager.load_settings()

    def show_settings(self):
        settings_dialog = QDialog(self)
        settings_dialog.setWindowTitle('Настройки')
        settings_dialog.setFixedSize(400, 300)
        layout = QVBoxLayout()

        layout.addWidget(QLabel('Лимит сообщений в день:'))
        limit_spin = QSpinBox()
        limit_spin.setRange(1, 100)
        limit_spin.setValue(self.settings['daily_limit'])
        layout.addWidget(limit_spin)

        layout.addWidget(QLabel('Минимальная задержка (секунды):'))
        min_delay_spin = QSpinBox()
        min_delay_spin.setRange(60, 86400)
        min_delay_spin.setValue(self.settings['min_delay'])
        layout.addWidget(min_delay_spin)

        layout.addWidget(QLabel('Максимальная задержка (секунды):'))
        max_delay_spin = QSpinBox()
        max_delay_spin.setRange(60, 86400)
        max_delay_spin.setValue(self.settings['max_delay'])
        layout.addWidget(max_delay_spin)

        button_layout = QHBoxLayout()

        save_btn = QPushButton('Сохранить')
        save_btn.setStyleSheet('background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;')

        def save_settings():
            self.settings['daily_limit'] = limit_spin.value()
            self.settings['min_delay'] = min_delay_spin.value()
            self.settings['max_delay'] = max_delay_spin.value()

            if SettingsManager.save_settings(self.settings):
                QMessageBox.information(settings_dialog, 'Успех', 'Настройки сохранены!')
                settings_dialog.accept()
                self.update_stats()
            else:
                QMessageBox.warning(settings_dialog, 'Ошибка', 'Не удалось сохранить настройки')

        save_btn.clicked.connect(save_settings)
        button_layout.addWidget(save_btn)

        cancel_btn = QPushButton('Отмена')
        cancel_btn.setStyleSheet('background-color: #f44336; color: white; font-weight: bold; padding: 8px;')
        cancel_btn.clicked.connect(settings_dialog.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)
        settings_dialog.setLayout(layout)
        settings_dialog.exec_()

    def load_chats(self):
        self.chats_data = CommentsManager.load_chats()
        self.update_stats()

    def update_stats(self):
        chats = CommentsManager.load_chats()
        total_chats = len(chats)
        today_sent = CommentsManager.get_today_sent_count()
        daily_limit = self.settings['daily_limit']

        self.stats_label.setText(f'Всего в списке: {total_chats} | Отправлено сегодня: {today_sent}/{daily_limit}')
        self.selected_chats_info.setText(f'Выбрано для рассылки: {len(self.selected_chats_for_sending)}')

    def search_chats(self):
        if not self.check_auth():
            QMessageBox.warning(self, 'Ошибка', 'Сначала авторизуйтесь!')
            return

        search_query = self.search_edit.text().strip()

        if not search_query:
            QMessageBox.warning(self, 'Ошибка', 'Введите поисковый запрос')
            return

        self.search_btn.setEnabled(False)
        self.search_btn.setText('Поиск...')

        self.search_thread = CommentsSearchThread(search_query, 30)
        self.search_thread.finished.connect(self.on_search_finished)
        self.search_thread.progress.connect(self.on_search_progress)
        self.search_thread.error.connect(self.on_search_error)
        self.search_thread.start()

    def on_search_progress(self, message):
        self.statusBar().showMessage(message)

    def on_search_finished(self, found_chats):
        self.search_btn.setEnabled(True)
        self.search_btn.setText('🔍 Найти')
        self.statusBar().showMessage(f'Найдено новых групп/каналов: {len(found_chats)}')

        # Очищаем предыдущие результаты
        for i in reversed(range(self.found_chats_layout.count())):
            widget = self.found_chats_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Добавляем новые чаты
        self.found_chats = found_chats
        for chat_id, chat_data in found_chats.items():
            chat_widget = ChatListWidget(chat_id, chat_data)
            self.found_chats_layout.addWidget(chat_widget)

        if not found_chats:
            no_chats_label = QLabel(
                'Новые группы/каналы не найдены. Попробуйте другой запрос.\n\nПримеры поиска:\n• "новости"\n• "крипта"\n• "технологии"\n• "спорт"\n• "музыка"')
            no_chats_label.setStyleSheet('color: gray; font-style: italic; padding: 20px;')
            no_chats_label.setAlignment(Qt.AlignCenter)
            self.found_chats_layout.addWidget(no_chats_label)

    def on_search_error(self, error_message):
        self.search_btn.setEnabled(True)
        self.search_btn.setText('🔍 Найти')
        QMessageBox.critical(self, 'Ошибка поиска', error_message)

    def save_selected_chats(self):
        if not hasattr(self, 'found_chats'):
            QMessageBox.warning(self, 'Ошибка', 'Сначала выполните поиск групп/каналов')
            return

        selected_chats = {}
        for i in range(self.found_chats_layout.count()):
            widget = self.found_chats_layout.itemAt(i).widget()
            if isinstance(widget, ChatListWidget) and widget.checkbox.isChecked():
                selected_chats[widget.chat_id] = widget.chat_data

        if not selected_chats:
            QMessageBox.warning(self, 'Ошибка', 'Выберите хотя бы одну группу/канал')
            return

        if CommentsManager.add_chats(selected_chats):
            QMessageBox.information(self, 'Успех', f'Добавлено в список: {len(selected_chats)}')
            self.load_chats()
        else:
            QMessageBox.warning(self, 'Ошибка', 'Не удалось добавить группы/каналы в список')

    def clear_search_results(self):
        for i in reversed(range(self.found_chats_layout.count())):
            widget = self.found_chats_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        if hasattr(self, 'found_chats'):
            del self.found_chats

        self.search_edit.clear()
        self.statusBar().showMessage('Результаты поиска очищены')

    def select_chats_for_sending(self):
        """Открывает диалог выбора чатов для рассылки"""
        dialog = SelectChatsDialog(self)
        dialog.load_chats()
        if dialog.exec_() == QDialog.Accepted:
            self.selected_chats_for_sending = set(dialog.get_selected_chats())
            self.selected_chats_info.setText(f'Выбрано для рассылки: {len(self.selected_chats_for_sending)}')
            QMessageBox.information(self, 'Успех',
                                    f'Выбрано {len(self.selected_chats_for_sending)} групп/каналов для рассылки')

    def delete_selected_chats(self):
        """Удаляет выбранные чаты"""
        dialog = SelectChatsDialog(self)
        dialog.load_chats()
        dialog.setWindowTitle('Выберите группы/каналы для удаления')
        if dialog.exec_() == QDialog.Accepted:
            chats_to_delete = dialog.get_selected_chats()

        if not chats_to_delete:
            return

        reply = QMessageBox.question(self, 'Подтверждение',
                                     f'Вы уверены, что хотите удалить {len(chats_to_delete)} групп/каналов из списка?',
                                     QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            if CommentsManager.delete_chats(chats_to_delete):
                # Обновляем список выбранных чатов
                self.selected_chats_for_sending = self.selected_chats_for_sending - set(chats_to_delete)
                self.load_chats()
                QMessageBox.information(self, 'Успех', f'Удалено {len(chats_to_delete)} групп/каналов')
            else:
                QMessageBox.warning(self, 'Ошибка', 'Не удалось удалить группы/каналы')

    def load_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Выберите видео файл', '',
            'Video Files (*.mp4 *.avi *.mov *.mkv *.webm)'
        )

        if file_path:
            self.video_path = file_path
            file_name = os.path.basename(file_path)
            self.video_label.setText(f'Видео: {file_name}')
            QMessageBox.information(self, 'Успех', f'Видео загружено: {file_name}')

    def clear_video(self):
        self.video_path = None
        self.video_label.setText('Видео не выбрано')

    def send_test_comment(self):
        """Отправляет тестовый комментарий и сразу удаляет его"""
        if not self.check_auth():
            QMessageBox.warning(self, 'Ошибка', 'Сначала авторизуйтесь!')
            return

        selected_chats = self.get_selected_chats_for_test()
        if not selected_chats:
            QMessageBox.warning(self, 'Ошибка', 'Выберите хотя бы один чат для тестового комментария')
            return

        message = self.message_text.toPlainText().strip()
        if not message and not hasattr(self, 'video_path'):
            QMessageBox.warning(self, 'Ошибка', 'Введите сообщение или загрузите видео')
            return

        video_path = getattr(self, 'video_path', None)

        # Отправляем в первый выбранный чат
        chat_id = selected_chats[0]
        chat_info = CommentsManager.load_chats().get(chat_id, {})
        chat_title = chat_info.get('title', 'чат')

        self.statusBar().showMessage(f'🧪 Отправляем тестовый комментарий в {chat_title}...')

        # Для тестового комментария устанавливаем delete_after_send=True
        self.send_thread = SendCommentThread(chat_id, message, video_path, delete_after_send=True)
        self.send_thread.finished.connect(self.on_test_send_finished)
        self.send_thread.error.connect(self.on_test_send_error)
        self.send_thread.start()

    def get_selected_chats_for_test(self):
        """Возвращает список выбранных чатов для тестирования"""
        # Если есть выбранные чаты для рассылки, используем их
        if self.selected_chats_for_sending:
            return list(self.selected_chats_for_sending)[:1]  # Берем только первый

        # Иначе показываем диалог выбора
        dialog = SelectChatsDialog(self)
        dialog.load_chats()
        if dialog.exec_() == QDialog.Accepted:
            selected = dialog.get_selected_chats()
            return selected[:1] if selected else []

        return []

    def on_test_send_finished(self, success, message):
        self.statusBar().showMessage(message)
        if success:
            QMessageBox.information(self, 'Успех', message)
        else:
            QMessageBox.warning(self, 'Предупреждение', message)

    def on_test_send_error(self, error_message):
        self.statusBar().showMessage(f'❌ Ошибка: {error_message}')
        QMessageBox.critical(self, 'Ошибка отправки', error_message)

    def send_to_selected(self):
        if not self.check_auth():
            QMessageBox.warning(self, 'Ошибка', 'Сначала авторизуйтесь!')
            return

        if not self.selected_chats_for_sending:
            QMessageBox.warning(self, 'Ошибка', 'Сначала выберите группы/каналы для отправки')
            return

        message = self.message_text.toPlainText().strip()
        if not message and not hasattr(self, 'video_path'):
            QMessageBox.warning(self, 'Ошибка', 'Введите сообщение или загрузите видео')
            return

        # Фильтруем чаты: только те, в которые еще не отправляли сегодня
        chat_ids = []
        for chat_id in self.selected_chats_for_sending:
            if not CommentsManager.was_sent_today(chat_id):
                chat_ids.append(chat_id)

        if not chat_ids:
            QMessageBox.warning(self, 'Ошибка', 'Во все выбранные группы/каналы уже отправляли сегодня')
            return

        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_bar.setMaximum(len(chat_ids))
        self.progress_bar.setValue(0)

        self.send_chats_sequentially(chat_ids, message, 0)

    def send_chats_sequentially(self, chat_ids, message, current_index):
        if current_index >= len(chat_ids):
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)
            self.update_stats()
            QMessageBox.information(self, 'Завершено', 'Рассылка комментариев завершена!')
            return

        chat_id = chat_ids[current_index]
        chat_title = CommentsManager.load_chats()[chat_id]['title']

        self.progress_label.setText(f'Отправка в {chat_title} ({current_index + 1}/{len(chat_ids)})')
        self.progress_bar.setValue(current_index)

        video_path = getattr(self, 'video_path', None)
        # Для обычной рассылки delete_after_send=False (сообщения остаются)
        self.send_thread = SendCommentThread(chat_id, message, video_path, delete_after_send=False)
        self.send_thread.finished.connect(
            lambda success, result: self.on_single_send_finished(success, result, chat_ids, message, current_index)
        )
        self.send_thread.error.connect(
            lambda error: self.on_single_send_error(error, chat_ids, message, current_index)
        )
        self.send_thread.start()

    def on_single_send_finished(self, success, result, chat_ids, message, current_index):
        self.statusBar().showMessage(result)
        # Следующее сообщение с задержкой
        QTimer.singleShot(2000, lambda: self.send_chats_sequentially(chat_ids, message, current_index + 1))

    def on_single_send_error(self, error_message, chat_ids, message, current_index):
        self.statusBar().showMessage(f'Ошибка: {error_message}')
        # Продолжаем со следующим чатом
        QTimer.singleShot(2000, lambda: self.send_chats_sequentially(chat_ids, message, current_index + 1))

    def toggle_auto_send(self):
        if self.auto_thread and self.auto_thread.isRunning():
            self.stop_sending()
        else:
            self.start_auto_send()

    def start_auto_send(self):
        if not self.check_auth():
            QMessageBox.warning(self, 'Ошибка', 'Сначала авторизуйтесь!')
            return

        if not self.selected_chats_for_sending:
            QMessageBox.warning(self, 'Ошибка', 'Сначала выберите группы/каналы для отправки')
            return

        message = self.message_text.toPlainText().strip()
        if not message and not hasattr(self, 'video_path'):
            QMessageBox.warning(self, 'Ошибка', 'Введите сообщение или загрузите видео')
            return

        video_path = getattr(self, 'video_path', None)

        self.auto_send_btn.setVisible(False)
        self.stop_btn.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)

        self.auto_thread = AutoCommentsThread(
            message,
            video_path,
            list(self.selected_chats_for_sending),
            self.settings['min_delay'],
            self.settings['max_delay'],
            self.settings['daily_limit']
        )
        self.auto_thread.progress.connect(self.on_auto_send_progress)
        self.auto_thread.finished.connect(self.on_auto_send_finished)
        self.auto_thread.error.connect(self.on_auto_send_error)
        self.auto_thread.start()

    def stop_sending(self):
        if self.auto_thread and self.auto_thread.isRunning():
            self.auto_thread.stop_sending()
            self.auto_thread.wait()

        self.auto_send_btn.setVisible(True)
        self.stop_btn.setVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)

    def on_auto_send_progress(self, message, current, total):
        self.progress_label.setText(message)
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
        self.statusBar().showMessage(message)
        self.update_stats()

    def on_auto_send_finished(self, message):
        self.auto_send_btn.setVisible(True)
        self.stop_btn.setVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)

        self.statusBar().showMessage(message)
        QMessageBox.information(self, 'Авторассылка', message)
        self.update_stats()

    def on_auto_send_error(self, error_message):
        self.auto_send_btn.setVisible(True)
        self.stop_btn.setVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)

        QMessageBox.critical(self, 'Ошибка авторассылки', error_message)
        self.update_stats()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Telegram Comments Sender')

    window = CommentsSenderApp()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()