import sys
import asyncio
import os
import random
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError, ChatWriteForbiddenError, ChannelPrivateError, \
    InviteRequestSentError, UserAlreadyParticipantError
from telethon.tl.functions.messages import GetDialogsRequest, ImportChatInviteRequest, GetDiscussionMessageRequest
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest, GetFullChannelRequest, \
    GetGroupsForDiscussionRequest
from telethon.tl.types import InputPeerEmpty, Channel, ChatForbidden, Message, Chat, User
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

# ИСПРАВЛЕНО: Используем тот же файл сессии что и в sender_in_open_chats.py
SESSION_FILE = os.path.join(tempfile.gettempdir(), 'telegram_session')  # Теперь тот же файл
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


class CommentsSearchThread(QThread):
    finished = pyqtSignal(dict)
    progress = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, search_query, limit=50):
        super().__init__()
        self.search_query = search_query
        self.limit = limit

    def run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
            result = loop.run_until_complete(self.search_comments_chats(client))
            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                loop.close()

    async def search_comments_chats(self, client):
        """Улучшенный поиск каналов и групп с возможностью комментирования"""
        found_chats = {}
        count = 0

        existing_chats = CommentsManager.load_chats()

        try:
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                raise Exception("Пользователь не авторизован")

            self.progress.emit("🔍 Начинаем расширенный поиск каналов и групп...")

            # Метод 1: Поиск через диалоги
            self.progress.emit("📂 Ищем в ваших диалогах...")
            dialogs = await client.get_dialogs(limit=150)

            for dialog in dialogs:
                if count >= self.limit:
                    break

                entity = dialog.entity

                # Пропускаем личные чаты
                if isinstance(entity, User):
                    continue

                chat_title = getattr(entity, 'title', '').lower()

                # Фильтрация по поисковому запросу
                if self.search_query and self.search_query.lower() not in chat_title:
                    continue

                try:
                    chat_id = str(entity.id)

                    # Пропускаем чаты, которые уже есть в списке
                    if chat_id in existing_chats:
                        continue

                    if chat_id in found_chats:
                        continue

                    # Определяем тип чата
                    if isinstance(entity, Channel):
                        if entity.broadcast:
                            chat_type = "Канал"
                        elif entity.megagroup:
                            chat_type = "Супергруппа"
                        else:
                            chat_type = "Группа"
                    else:
                        chat_type = "Группа"

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
                            await client(JoinChannelRequest(username))
                            access_type = "Открытый"
                        except UserAlreadyParticipantError:
                            access_type = "Уже участник"
                        except Exception:
                            access_type = "Закрытый"

                    # Получаем последние сообщения для проверки комментирования
                    try:
                        messages = await client.get_messages(entity, limit=5)

                        for message in messages:
                            if not message:
                                continue

                            try:
                                # Пробуем отправить тестовый комментарий
                                test_comment = await client.send_message(
                                    entity,
                                    "💬 Тестовый комментарий",
                                    comment_to=message.id
                                )
                                await asyncio.sleep(1)
                                await client.delete_messages(entity, [test_comment.id])

                                can_comment = True
                                last_post_id = message.id
                                last_post_date = message.date.strftime('%d.%m.%Y %H:%M') if message.date else ""

                                # Проверяем возможность отправки видео
                                try:
                                    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
                                        f.write(b"test video content")
                                        test_file = f.name

                                    test_video = await client.send_file(
                                        entity,
                                        test_file,
                                        caption="Тест видео",
                                        comment_to=message.id
                                    )
                                    await asyncio.sleep(1)
                                    await client.delete_messages(entity, [test_video.id])
                                    can_video = True
                                    os.unlink(test_file)
                                except Exception:
                                    can_video = False
                                    if os.path.exists(test_file):
                                        try:
                                            os.unlink(test_file)
                                        except:
                                            pass

                                break  # Нашли рабочий пост

                            except Exception as e:
                                continue

                    except Exception as e:
                        self.progress.emit(f"⚠️ Не удалось проверить {dialog.name}: {str(e)}")
                        continue

                    # Сохраняем чат если можно комментировать
                    if can_comment:
                        found_chats[chat_id] = {
                            'title': dialog.name,
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
                        count += 1
                        self.progress.emit(f"💬 Найден: {count} - {dialog.name}")

                except Exception as e:
                    continue

            # Метод 2: Глобальный поиск
            if count < self.limit:
                self.progress.emit("🌐 Запускаем глобальный поиск...")

                # Популярные каналы для поиска
                search_queries = [
                    self.search_query,
                    'новости', 'технологии', 'политика', 'спорт',
                    'экономика', 'культура', 'образование', 'наука'
                ]

                for query in search_queries:
                    if count >= self.limit:
                        break

                    if not query:
                        continue

                    try:
                        self.progress.emit(f"🔎 Ищем по запросу: {query}")
                        search_results = await client.get_dialogs()

                        # Также используем поиск по каналам
                        try:
                            found_entities = await client.get_participants(query, limit=20)
                        except:
                            found_entities = []

                        all_entities = list(search_results) + list(found_entities)

                        for entity in all_entities:
                            if count >= self.limit:
                                break

                            if hasattr(entity, 'title'):
                                chat_title = entity.title.lower()
                                if self.search_query and self.search_query.lower() not in chat_title:
                                    continue

                                try:
                                    chat_id = str(entity.id)

                                    if chat_id in existing_chats or chat_id in found_chats:
                                        continue

                                    # Проверяем возможность комментирования (аналогично первому методу)
                                    can_comment = False
                                    last_post_id = 0

                                    try:
                                        messages = await client.get_messages(entity, limit=3)
                                        for message in messages:
                                            try:
                                                test_comment = await client.send_message(
                                                    entity,
                                                    "💬 Тест",
                                                    comment_to=message.id
                                                )
                                                await asyncio.sleep(1)
                                                await client.delete_messages(entity, [test_comment.id])
                                                can_comment = True
                                                last_post_id = message.id
                                                break
                                            except:
                                                continue
                                    except:
                                        pass

                                    if can_comment:
                                        found_chats[chat_id] = {
                                            'title': entity.title,
                                            'type': "Канал",
                                            'access_type': "Открытый",
                                            'can_comment': can_comment,
                                            'can_video': False,
                                            'last_post_id': last_post_id,
                                            'last_post_date': datetime.now().strftime('%d.%m.%Y %H:%M'),
                                            'status': 'не отправлено',
                                            'send_time': '',
                                            'username': getattr(entity, 'username', '')
                                        }
                                        count += 1
                                        self.progress.emit(f"🌐 Найден: {count} - {entity.title}")

                                except Exception as e:
                                    continue

                    except Exception as e:
                        self.progress.emit(f"⚠️ Ошибка поиска '{query}': {str(e)}")
                        continue

            # Метод 3: Поиск в популярных каналах
            if count < self.limit:
                self.progress.emit("📢 Проверяем популярные каналы...")

                popular_channels = [
                    'tgraphio', 'rednotes', 'breakingmash', 'rian_ru',
                    'meduzaproject', 'bbcrussian', 'rt_russian', 'lentach',
                    'tass_agency', 'rian_ru', 'rbc_news'
                ]

                for channel in popular_channels:
                    if count >= self.limit:
                        break

                    try:
                        entity = await client.get_entity(channel)
                        chat_id = str(entity.id)

                        if chat_id in existing_chats or chat_id in found_chats:
                            continue

                        # Проверяем комментирование
                        can_comment = False
                        last_post_id = 0

                        try:
                            messages = await client.get_messages(entity, limit=3)
                            for message in messages:
                                try:
                                    test_comment = await client.send_message(
                                        entity,
                                        "💬 Тест",
                                        comment_to=message.id
                                    )
                                    await asyncio.sleep(1)
                                    await client.delete_messages(entity, [test_comment.id])
                                    can_comment = True
                                    last_post_id = message.id
                                    break
                                except:
                                    continue
                        except:
                            pass

                        if can_comment:
                            found_chats[chat_id] = {
                                'title': getattr(entity, 'title', channel),
                                'type': "Канал",
                                'access_type': "Открытый",
                                'can_comment': can_comment,
                                'can_video': False,
                                'last_post_id': last_post_id,
                                'last_post_date': datetime.now().strftime('%d.%m.%Y %H:%M'),
                                'status': 'не отправлено',
                                'send_time': '',
                                'username': channel
                            }
                            count += 1
                            self.progress.emit(f"📢 Найден: {count} - {channel}")

                    except Exception as e:
                        continue

            await client.disconnect()

            if not found_chats:
                self.progress.emit("❌ Чаты с комментариями не найдены. Попробуйте другой запрос.")
            else:
                self.progress.emit(f"🎯 Поиск завершен. Найдено чатов: {len(found_chats)}")

            return found_chats

        except Exception as e:
            try:
                await client.disconnect()
            except:
                pass
            raise e


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

    def __init__(self, chat_id, message, video_path=None, delay=2):
        super().__init__()
        self.chat_id = chat_id
        self.message = message
        self.video_path = video_path
        self.delay = delay

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

            if self.video_path and os.path.exists(self.video_path) and can_video:
                if self.message.strip():
                    await client.send_file(entity, self.video_path,
                                           caption=self.message,
                                           comment_to=int(post_id))
                else:
                    await client.send_file(entity, self.video_path,
                                           comment_to=int(post_id))
            else:
                await client.send_message(entity, self.message,
                                          comment_to=int(post_id))

            await asyncio.sleep(1)
            await client.disconnect()

            send_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
            CommentsManager.update_chat_status(self.chat_id, 'отправлено', send_time)

            chat_title = chat_info.get('title', 'чат')
            return f"✅ Комментарий отправлен в {chat_title}"

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
            result = loop.run_until_complete(self.auto_send_comments(client))
            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                loop.close()

    def is_working_time(self):
        now = datetime.now()
        current_hour = now.hour
        return 11 <= current_hour < 21

    def get_today_sent_count(self):
        return CommentsManager.get_today_sent_count()

    def can_send_today(self):
        return self.get_today_sent_count() < self.daily_limit

    async def auto_send_comments(self, client):
        await client.connect()
        if not client.is_connected():
            await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            raise Exception("Пользователь не авторизован")

        try:
            while self.is_running:
                if not self.is_working_time():
                    wait_until = datetime.now().replace(hour=11, minute=0, second=0, microsecond=0)
                    if datetime.now().hour >= 21:
                        wait_until += timedelta(days=1)

                    wait_seconds = (wait_until - datetime.now()).total_seconds()
                    self.progress.emit(
                        f"⏳ Вне времени работы (11:00-21:00). Ждем до {wait_until.strftime('%H:%M')}",
                        0, 1
                    )

                    for sec in range(int(wait_seconds)):
                        if not self.is_running:
                            await client.disconnect()
                            return "⏹️ Автоматическая рассылка комментариев остановлена"
                        await asyncio.sleep(1)
                    continue

                selected_chats = {chat_id: CommentsManager.load_chats()[chat_id]
                                  for chat_id in self.selected_chats
                                  if chat_id in CommentsManager.load_chats() and
                                  CommentsManager.load_chats()[chat_id]['status'] == 'не отправлено'}

                total_chats = len(selected_chats)

                if total_chats == 0:
                    await client.disconnect()
                    return "❌ Нет выбранных чатов для комментирования"

                today_sent = self.get_today_sent_count()
                remaining_limit = self.daily_limit - today_sent

                if remaining_limit <= 0:
                    tomorrow = datetime.now() + timedelta(days=1)
                    wait_until = tomorrow.replace(hour=11, minute=0, second=0, microsecond=0)
                    wait_seconds = (wait_until - datetime.now()).total_seconds()

                    self.progress.emit(
                        f"📅 Достигнут дневной лимит ({self.daily_limit} комментариев). Ждем до завтра 11:00",
                        0, 1
                    )

                    for sec in range(int(wait_seconds)):
                        if not self.is_running:
                            await client.disconnect()
                            return "⏹️ Автоматическая рассылка комментариев остановлена"
                        await asyncio.sleep(1)
                    continue

                sent_count = 0
                chat_ids = list(selected_chats.keys())[:remaining_limit]

                for i, chat_id in enumerate(chat_ids):
                    if not self.is_running:
                        await client.disconnect()
                        return "⏹️ Автоматическая рассылка комментариев остановлена"

                    chat_info = selected_chats[chat_id]
                    chat_title = chat_info['title']
                    post_id = chat_info.get('last_post_id', 0)

                    if not post_id or post_id == '0':
                        self.progress.emit(
                            f"⏭️ Пропускаем {chat_title} - нет поста для комментирования",
                            i, len(chat_ids)
                        )
                        continue

                    can_video = chat_info.get('can_video', False)
                    if self.video_path and not can_video:
                        self.progress.emit(
                            f"⏭️ Пропускаем {chat_title} - нельзя отправить видео в комментарий",
                            i, len(chat_ids)
                        )
                        continue

                    if sent_count > 0:
                        delay_seconds = random.randint(self.min_delay, self.max_delay)
                        delay_minutes = delay_seconds // 60
                        delay_secs = delay_seconds % 60

                        self.progress.emit(
                            f"⏰ Ожидание {delay_minutes} мин {delay_secs} сек перед комментарием в {chat_title}",
                            i, len(chat_ids)
                        )

                        for sec in range(delay_seconds):
                            if not self.is_running:
                                await client.disconnect()
                                return "⏹️ Автоматическая рассылка комментариев остановлена"
                            if not self.is_working_time():
                                break
                            await asyncio.sleep(1)

                        if not self.is_running:
                            await client.disconnect()
                            return "⏹️ Автоматическая рассылка комментариев остановлена"

                        if not self.is_working_time():
                            self.progress.emit(
                                f"⏸️ Время работы закончилось. Ждем до завтра 11:00",
                                i, len(chat_ids)
                            )
                            break

                    try:
                        entity = await client.get_entity(int(chat_id))

                        if self.video_path and os.path.exists(self.video_path) and can_video:
                            if self.message.strip():
                                await client.send_file(entity, self.video_path,
                                                       caption=self.message,
                                                       comment_to=int(post_id))
                            else:
                                await client.send_file(entity, self.video_path,
                                                       comment_to=int(post_id))
                        else:
                            await client.send_message(entity, self.message,
                                                      comment_to=int(post_id))

                        send_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
                        CommentsManager.update_chat_status(chat_id, 'отправлено', send_time)

                        sent_count += 1
                        today_sent += 1

                        self.progress.emit(
                            f"✅ Комментарий отправлен в {chat_title} ({sent_count}/{remaining_limit} за сегодня)",
                            i + 1, len(chat_ids)
                        )

                        await asyncio.sleep(2)

                    except FloodWaitError as e:
                        wait_time = e.seconds
                        self.progress.emit(
                            f"⏳ Лимит Telegram! Ждем {wait_time} секунд",
                            i, len(chat_ids)
                        )

                        for sec in range(wait_time):
                            if not self.is_running:
                                await client.disconnect()
                                return "⏹️ Автоматическая рассылка комментариев остановлена"
                            await asyncio.sleep(1)

                    except Exception as e:
                        self.progress.emit(
                            f"❌ Ошибка в {chat_title}: {str(e)}",
                            i, len(chat_ids)
                        )

                if sent_count == 0:
                    self.progress.emit(
                        "❌ Не удалось отправить ни одного комментария",
                        0, 1
                    )

                if sent_count < remaining_limit:
                    next_delay = random.randint(self.min_delay, self.max_delay)
                    next_delay_minutes = next_delay // 60
                    next_delay_secs = next_delay % 60

                    self.progress.emit(
                        f"⏰ Следующий цикл через {next_delay_minutes} мин {next_delay_secs} сек",
                        0, 1
                    )

                    for sec in range(next_delay):
                        if not self.is_running:
                            await client.disconnect()
                            return "⏹️ Автоматическая рассылка комментариев остановлена"
                        await asyncio.sleep(1)

            await client.disconnect()
            return "⏹️ Автоматическая рассылка комментариев остановлена"

        except Exception as e:
            await client.disconnect()
            raise e


class CommentsSenderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.auto_thread = None
        self.init_ui()
        self.load_settings()
        self.load_chats()
        self.check_auth()

    def init_ui(self):
        self.setWindowTitle('Telegram - Автоматические комментарии в открытых группах')
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Заголовок
        title_label = QLabel('📢 Автоматические комментарии в открытых группах')
        title_label.setStyleSheet('font-size: 18px; font-weight: bold; color: #2E86AB; margin: 10px;')
        layout.addWidget(title_label)

        # Статус авторизации
        auth_layout = QHBoxLayout()
        self.auth_status_label = QLabel('🔐 Статус авторизации: Проверка...')
        self.auth_status_label.setStyleSheet('font-size: 12px; color: orange;')
        auth_layout.addWidget(self.auth_status_label)
        auth_layout.addStretch()
        self.auth_button = QPushButton('Авторизоваться')
        self.auth_button.setStyleSheet('background-color: #4CAF50; color: white; font-weight: bold;')
        self.auth_button.clicked.connect(self.auth_button_clicked)
        auth_layout.addWidget(self.auth_button)
        layout.addLayout(auth_layout)

        # Разделитель
        layout.addWidget(QLabel('_' * 100))

        # Поиск и добавление чатов
        search_group = QGroupBox('🔍 Поиск и добавление чатов с комментариями')
        search_layout = QVBoxLayout(search_group)

        search_input_layout = QHBoxLayout()
        search_input_layout.addWidget(QLabel('Поиск:'))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('Введите ключевое слово для поиска каналов с комментариями...')
        search_input_layout.addWidget(self.search_edit)

        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(10, 200)
        self.limit_spin.setValue(50)
        self.limit_spin.setSuffix(' чатов')
        search_input_layout.addWidget(QLabel('Лимит:'))
        search_input_layout.addWidget(self.limit_spin)

        self.search_button = QPushButton('Найти чаты')
        self.search_button.setStyleSheet('background-color: #2196F3; color: white; font-weight: bold;')
        self.search_button.clicked.connect(self.search_comments_chats)
        search_input_layout.addWidget(self.search_button)

        search_layout.addLayout(search_input_layout)

        self.search_progress_label = QLabel('')
        self.search_progress_label.setStyleSheet('color: blue; font-size: 11px;')
        search_layout.addWidget(self.search_progress_label)

        layout.addWidget(search_group)

        # Список чатов
        chats_group = QGroupBox('📋 Список чатов для комментирования')
        chats_layout = QVBoxLayout(chats_group)

        # Фильтры
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel('Фильтр:'))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(['Все', 'Не отправлено', 'Отправлено', 'С видео', 'Без видео'])
        self.filter_combo.currentTextChanged.connect(self.filter_chats)
        filter_layout.addWidget(self.filter_combo)

        filter_layout.addStretch()
        self.select_all_checkbox = QCheckBox('Выбрать все')
        self.select_all_checkbox.stateChanged.connect(self.toggle_select_all)
        filter_layout.addWidget(self.select_all_checkbox)

        self.delete_selected_button = QPushButton('Удалить выбранные')
        self.delete_selected_button.setStyleSheet('background-color: #f44336; color: white;')
        self.delete_selected_button.clicked.connect(self.delete_selected_chats)
        filter_layout.addWidget(self.delete_selected_button)

        self.leave_unused_button = QPushButton('Выйти из лишних чатов')
        self.leave_unused_button.setStyleSheet('background-color: #FF9800; color: white;')
        self.leave_unused_button.clicked.connect(self.leave_unused_chats)
        filter_layout.addWidget(self.leave_unused_button)

        chats_layout.addLayout(filter_layout)

        # Список чатов
        self.chats_list = QListWidget()
        self.chats_list.itemChanged.connect(self.on_chat_item_changed)
        chats_layout.addWidget(self.chats_list)

        layout.addWidget(chats_group)

        # Статистика
        stats_layout = QHBoxLayout()
        self.stats_label = QLabel('Всего: 0 | Не отправлено: 0 | Отправлено: 0 | Сегодня: 0')
        self.stats_label.setStyleSheet('font-size: 12px; color: #666;')
        stats_layout.addWidget(self.stats_label)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # Настройки сообщения
        message_group = QGroupBox('💬 Настройки комментария')
        message_layout = QVBoxLayout(message_group)

        self.message_edit = QTextEdit()
        self.message_edit.setPlaceholderText('Введите текст комментария...')
        self.message_edit.setMaximumHeight(80)
        message_layout.addWidget(self.message_edit)

        video_layout = QHBoxLayout()
        self.video_path_edit = QLineEdit()
        self.video_path_edit.setPlaceholderText('Путь к видеофайлу (опционально)...')
        video_layout.addWidget(self.video_path_edit)

        self.browse_video_button = QPushButton('Обзор')
        self.browse_video_button.clicked.connect(self.browse_video)
        video_layout.addWidget(self.browse_video_button)

        message_layout.addLayout(video_layout)
        layout.addWidget(message_group)

        # Настройки отправки
        settings_group = QGroupBox('⚙️ Настройки отправки')
        settings_layout = QHBoxLayout(settings_group)

        settings_layout.addWidget(QLabel('Дневной лимит:'))
        self.daily_limit_spin = QSpinBox()
        self.daily_limit_spin.setRange(1, 100)
        self.daily_limit_spin.setValue(10)
        settings_layout.addWidget(self.daily_limit_spin)

        settings_layout.addWidget(QLabel('Мин. задержка (сек):'))
        self.min_delay_spin = QSpinBox()
        self.min_delay_spin.setRange(60, 36000)
        self.min_delay_spin.setValue(3600)
        settings_layout.addWidget(self.min_delay_spin)

        settings_layout.addWidget(QLabel('Макс. задержка (сек):'))
        self.max_delay_spin = QSpinBox()
        self.max_delay_spin.setRange(60, 36000)
        self.max_delay_spin.setValue(5400)
        settings_layout.addWidget(self.max_delay_spin)

        self.save_settings_button = QPushButton('Сохранить настройки')
        self.save_settings_button.setStyleSheet('background-color: #607D8B; color: white;')
        self.save_settings_button.clicked.connect(self.save_settings)
        settings_layout.addWidget(self.save_settings_button)

        settings_layout.addStretch()
        layout.addWidget(settings_group)

        # Прогресс
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel('')
        self.progress_label.setStyleSheet('color: blue; font-size: 11px;')
        layout.addWidget(self.progress_label)

        # Кнопки управления
        buttons_layout = QHBoxLayout()

        self.send_test_button = QPushButton('📤 Тестовый комментарий')
        self.send_test_button.setStyleSheet('background-color: #FF9800; color: white; font-weight: bold;')
        self.send_test_button.clicked.connect(self.send_test_comment)
        buttons_layout.addWidget(self.send_test_button)

        self.start_auto_button = QPushButton('🚀 Старт авто-комментариев')
        self.start_auto_button.setStyleSheet('background-color: #4CAF50; color: white; font-weight: bold;')
        self.start_auto_button.clicked.connect(self.start_auto_comments)
        buttons_layout.addWidget(self.start_auto_button)

        self.stop_auto_button = QPushButton('⏹️ Стоп')
        self.stop_auto_button.setStyleSheet('background-color: #f44336; color: white; font-weight: bold;')
        self.stop_auto_button.clicked.connect(self.stop_auto_comments)
        self.stop_auto_button.setEnabled(False)
        buttons_layout.addWidget(self.stop_auto_button)

        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        # Статус
        self.status_label = QLabel('Готов к работе')
        self.status_label.setStyleSheet('color: green; font-weight: bold; margin: 5px;')
        layout.addWidget(self.status_label)

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
                self.auth_status_label.setText('🔐 Статус авторизации: Авторизован')
                self.auth_status_label.setStyleSheet('font-size: 12px; color: green;')
                self.auth_button.setText('Переавторизоваться')
                return True
            else:
                self.auth_status_label.setText('🔐 Статус авторизации: Не авторизован')
                self.auth_status_label.setStyleSheet('font-size: 12px; color: red;')
                self.auth_button.setText('Авторизоваться')
                return False

        except Exception as e:
            print(f"Ошибка проверки авторизации: {e}")
            self.auth_status_label.setText('🔐 Статус авторизации: Ошибка проверки')
            self.auth_status_label.setStyleSheet('font-size: 12px; color: red;')
            self.auth_button.setText('Авторизоваться')
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
            self.auth_status_label.setText('🔐 Статус авторизации: Не авторизован')
            self.auth_status_label.setStyleSheet('font-size: 12px; color: red;')
            self.auth_button.setText('Авторизоваться')
            QMessageBox.information(self, 'Выход', 'Вы успешно вышли из системы')
        except Exception as e:
            QMessageBox.warning(self, 'Ошибка', f'Ошибка при выходе: {str(e)}')

    def show_auth_dialog(self):
        auth_dialog = AuthDialog(self)
        auth_dialog.authorization_success.connect(self.on_auth_success)
        auth_dialog.exec_()

    def on_auth_success(self):
        """Обработчик успешной авторизации"""
        self.check_auth()  # Обновляем статус
        QMessageBox.information(self, 'Успех', 'Авторизация прошла успешно!')

    def load_settings(self):
        settings = SettingsManager.load_settings()
        self.daily_limit_spin.setValue(settings['daily_limit'])
        self.min_delay_spin.setValue(settings['min_delay'])
        self.max_delay_spin.setValue(settings['max_delay'])

    def save_settings(self):
        settings = {
            'daily_limit': self.daily_limit_spin.value(),
            'min_delay': self.min_delay_spin.value(),
            'max_delay': self.max_delay_spin.value()
        }

        if SettingsManager.save_settings(settings):
            QMessageBox.information(self, 'Успех', 'Настройки сохранены!')
        else:
            QMessageBox.warning(self, 'Ошибка', 'Не удалось сохранить настройки')

    def load_chats(self):
        self.chats_data = CommentsManager.load_chats()
        self.update_chats_list()
        self.update_stats()

    def update_chats_list(self):
        self.chats_list.clear()

        filter_text = self.filter_combo.currentText()

        for chat_id, data in self.chats_data.items():
            title = data['title']
            chat_type = data['type']
            access_type = data['access_type']
            can_comment = data['can_comment']
            can_video = data['can_video']
            status = data['status']
            send_time = data.get('send_time', '')
            username = data.get('username', '')

            # Применяем фильтр
            if filter_text == 'Не отправлено' and status != 'не отправлено':
                continue
            elif filter_text == 'Отправлено' and status != 'отправлено':
                continue
            elif filter_text == 'С видео' and not can_video:
                continue
            elif filter_text == 'Без видео' and can_video:
                continue

            item_text = f"{title} | {chat_type} | {access_type} | "
            if can_video:
                item_text += "📹 | "
            else:
                item_text += "💬 | "

            item_text += f"Статус: {status}"

            if send_time:
                item_text += f" | {send_time}"

            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, chat_id)

            if status == 'отправлено':
                item.setBackground(Qt.green)
            elif status == 'не отправлено':
                item.setBackground(Qt.yellow)

            if can_comment:
                item.setCheckState(Qt.Unchecked)
            else:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)

            self.chats_list.addItem(item)

    def filter_chats(self):
        self.update_chats_list()

    def toggle_select_all(self, state):
        for i in range(self.chats_list.count()):
            item = self.chats_list.item(i)
            if item.flags() & Qt.ItemIsEnabled:
                item.setCheckState(Qt.Checked if state else Qt.Unchecked)

    def on_chat_item_changed(self, item):
        # Обновляем статистику при изменении выбора
        self.update_stats()

    def get_selected_chats(self):
        selected_chats = []
        for i in range(self.chats_list.count()):
            item = self.chats_list.item(i)
            if item.checkState() == Qt.Checked:
                chat_id = item.data(Qt.UserRole)
                selected_chats.append(chat_id)
        return selected_chats

    def update_stats(self):
        total = len(self.chats_data)
        unsent = sum(1 for data in self.chats_data.values() if data['status'] == 'не отправлено')
        sent = sum(1 for data in self.chats_data.values() if data['status'] == 'отправлено')
        today_sent = CommentsManager.get_today_sent_count()
        selected = len(self.get_selected_chats())

        self.stats_label.setText(
            f'Всего: {total} | Не отправлено: {unsent} | Отправлено: {sent} | Сегодня: {today_sent} | Выбрано: {selected}')

    def search_comments_chats(self):
        # Сначала проверяем авторизацию
        if not self.check_auth():
            QMessageBox.warning(self, 'Ошибка', 'Сначала авторизуйтесь!')
            return

        search_query = self.search_edit.text().strip()
        limit = self.limit_spin.value()

        if not search_query:
            QMessageBox.warning(self, 'Ошибка', 'Введите поисковый запрос')
            return

        self.search_button.setEnabled(False)
        self.search_progress_label.setText('🔍 Начинаем поиск каналов с комментариями...')

        self.search_thread = CommentsSearchThread(search_query, limit)
        self.search_thread.progress.connect(self.on_search_progress)
        self.search_thread.finished.connect(self.on_search_finished)
        self.search_thread.error.connect(self.on_search_error)
        self.search_thread.start()

    def on_search_progress(self, message):
        self.search_progress_label.setText(message)

    def on_search_finished(self, found_chats):
        if found_chats:
            if CommentsManager.add_chats(found_chats):
                self.load_chats()
                self.search_progress_label.setText(
                    f'✅ Найдено и добавлено {len(found_chats)} чатов с комментариями')
                QMessageBox.information(self, 'Успех',
                                        f'Найдено и добавлено {len(found_chats)} чатов с комментариями!')
            else:
                self.search_progress_label.setText('❌ Ошибка сохранения чатов')
                QMessageBox.warning(self, 'Ошибка', 'Не удалось сохранить найденные чаты')
        else:
            self.search_progress_label.setText('❌ Чаты с комментариями не найдены')
            QMessageBox.information(self, 'Информация', 'Чаты с комментариями не найдены')

        self.search_button.setEnabled(True)

    def on_search_error(self, error_message):
        self.search_progress_label.setText(f'❌ Ошибка поиска: {error_message}')
        QMessageBox.critical(self, 'Ошибка поиска', error_message)
        self.search_button.setEnabled(True)

    def delete_selected_chats(self):
        selected_items = self.chats_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, 'Ошибка', 'Выберите чаты для удаления')
            return

        chat_ids = [item.data(Qt.UserRole) for item in selected_items]

        reply = QMessageBox.question(self, 'Подтверждение',
                                     f'Вы уверены, что хотите удалить {len(chat_ids)} чатов?',
                                     QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            if CommentsManager.delete_chats(chat_ids):
                self.load_chats()
                QMessageBox.information(self, 'Успех', f'Удалено {len(chat_ids)} чатов')
            else:
                QMessageBox.warning(self, 'Ошибка', 'Не удалось удалить чаты')

    def leave_unused_chats(self):
        # Сначала проверяем авторизацию
        if not self.check_auth():
            QMessageBox.warning(self, 'Ошибка', 'Сначала авторизуйтесь!')
            return

        chat_ids_to_keep = list(self.chats_data.keys())

        if not chat_ids_to_keep:
            QMessageBox.warning(self, 'Ошибка', 'Нет чатов для сохранения')
            return

        reply = QMessageBox.question(self, 'Подтверждение',
                                     'Вы уверены, что хотите выйти из всех чатов, кроме сохраненных в списке?',
                                     QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.leave_thread = LeaveChatsThread(chat_ids_to_keep)
            self.leave_thread.progress.connect(self.on_leave_progress)
            self.leave_thread.finished.connect(self.on_leave_finished)
            self.leave_thread.error.connect(self.on_leave_error)
            self.leave_thread.start()

    def on_leave_progress(self, message):
        self.status_label.setText(message)

    def on_leave_finished(self, count):
        self.status_label.setText(f'✅ Выход завершен. Покинуто чатов: {count}')
        QMessageBox.information(self, 'Успех', f'Выход завершен. Покинуто чатов: {count}')

    def on_leave_error(self, error_message):
        self.status_label.setText(f'❌ Ошибка выхода: {error_message}')
        QMessageBox.critical(self, 'Ошибка', error_message)

    def browse_video(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Выберите видеофайл', '',
                                                   'Video Files (*.mp4 *.avi *.mov *.mkv)')
        if file_path:
            self.video_path_edit.setText(file_path)

    def send_test_comment(self):
        # Сначала проверяем авторизацию
        if not self.check_auth():
            QMessageBox.warning(self, 'Ошибка', 'Сначала авторизуйтесь!')
            return

        selected_chats = self.get_selected_chats()
        if not selected_chats:
            QMessageBox.warning(self, 'Ошибка', 'Выберите хотя бы один чат для тестового комментария')
            return

        message = self.message_edit.toPlainText().strip()
        if not message:
            QMessageBox.warning(self, 'Ошибка', 'Введите текст комментария')
            return

        video_path = self.video_path_edit.text().strip()
        if video_path and not os.path.exists(video_path):
            QMessageBox.warning(self, 'Ошибка', 'Указанный видеофайл не существует')
            return

        # Отправляем в первый выбранный чат
        chat_id = selected_chats[0]
        chat_info = self.chats_data.get(chat_id, {})
        chat_title = chat_info.get('title', 'чат')

        self.status_label.setText(f'📤 Отправляем тестовый комментарий в {chat_title}...')

        self.send_thread = SendCommentThread(chat_id, message, video_path)
        self.send_thread.finished.connect(self.on_send_finished)
        self.send_thread.error.connect(self.on_send_error)
        self.send_thread.start()

    def on_send_finished(self, success, message):
        self.status_label.setText(message)
        if success:
            QMessageBox.information(self, 'Успех', message)
            self.load_chats()
        else:
            QMessageBox.warning(self, 'Предупреждение', message)

    def on_send_error(self, error_message):
        self.status_label.setText(f'❌ Ошибка: {error_message}')
        QMessageBox.critical(self, 'Ошибка отправки', error_message)

    def start_auto_comments(self):
        # Сначала проверяем авторизацию
        if not self.check_auth():
            QMessageBox.warning(self, 'Ошибка', 'Сначала авторизуйтесь!')
            return

        selected_chats = self.get_selected_chats()
        if not selected_chats:
            QMessageBox.warning(self, 'Ошибка', 'Выберите чаты для автоматических комментариев')
            return

        message = self.message_edit.toPlainText().strip()
        if not message:
            QMessageBox.warning(self, 'Ошибка', 'Введите текст комментария')
            return

        video_path = self.video_path_edit.text().strip()
        if video_path and not os.path.exists(video_path):
            QMessageBox.warning(self, 'Ошибка', 'Указанный видеофайл не существует')
            return

        settings = {
            'daily_limit': self.daily_limit_spin.value(),
            'min_delay': self.min_delay_spin.value(),
            'max_delay': self.max_delay_spin.value()
        }

        self.status_label.setText('🚀 Запуск автоматической рассылки комментариев...')
        self.progress_bar.setVisible(True)
        self.start_auto_button.setEnabled(False)
        self.stop_auto_button.setEnabled(True)

        self.auto_thread = AutoCommentsThread(
            message=message,
            video_path=video_path,
            selected_chats=selected_chats,
            min_delay=settings['min_delay'],
            max_delay=settings['max_delay'],
            daily_limit=settings['daily_limit']
        )

        self.auto_thread.progress.connect(self.on_auto_progress)
        self.auto_thread.finished.connect(self.on_auto_finished)
        self.auto_thread.error.connect(self.on_auto_error)
        self.auto_thread.start()

    def on_auto_progress(self, message, current, total):
        self.progress_label.setText(message)
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)

    def on_auto_finished(self, message):
        self.status_label.setText(message)
        self.progress_bar.setVisible(False)
        self.progress_label.setText('')
        self.start_auto_button.setEnabled(True)
        self.stop_auto_button.setEnabled(False)
        self.load_chats()

        if "остановлена" not in message:
            QMessageBox.information(self, 'Завершено', message)

    def on_auto_error(self, error_message):
        self.status_label.setText(f'❌ Ошибка: {error_message}')
        self.progress_bar.setVisible(False)
        self.progress_label.setText('')
        self.start_auto_button.setEnabled(True)
        self.stop_auto_button.setEnabled(False)
        QMessageBox.critical(self, 'Ошибка', error_message)

    def stop_auto_comments(self):
        if self.auto_thread and self.auto_thread.isRunning():
            self.auto_thread.stop_sending()
            self.status_label.setText('⏹️ Останавливаем рассылку...')


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Telegram Comments Sender')

    window = CommentsSenderApp()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()