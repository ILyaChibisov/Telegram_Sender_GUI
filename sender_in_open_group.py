import sys
import asyncio
import os
import random
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError, ChatWriteForbiddenError, ChannelPrivateError, \
    InviteRequestSentError, UserAlreadyParticipantError
from telethon.tl.functions.messages import GetDialogsRequest, ImportChatInviteRequest, GetDiscussionMessageRequest
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest, GetFullChannelRequest
from telethon.tl.types import InputPeerEmpty, Channel, ChatForbidden, Message
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

SESSION_FILE = os.path.join(tempfile.gettempdir(), 'telegram_comments_session')
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
        """Поиск каналов и групп с возможностью комментирования"""
        found_chats = {}
        count = 0

        existing_chats = CommentsManager.load_chats()

        try:
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                raise Exception("Пользователь не авторизован")

            self.progress.emit("🔍 Начинаем поиск каналов с комментариями...")

            # Получаем диалоги
            dialogs = await client.get_dialogs(limit=100)

            for dialog in dialogs:
                if count >= self.limit:
                    break

                if not dialog.is_channel:
                    continue

                entity = dialog.entity
                chat_title = dialog.name.lower()

                # Фильтрация по поисковому запросу
                if self.search_query and self.search_query.lower() not in chat_title:
                    continue

                try:
                    chat_id = str(entity.id)

                    # Пропускаем чаты, которые уже есть в списке
                    if chat_id in existing_chats:
                        self.progress.emit(f"⏭️ Пропускаем {dialog.name} - уже в списке")
                        continue

                    if chat_id in found_chats:
                        continue

                    # Получаем полную информацию о канале
                    full_chat = await client(GetFullChannelRequest(entity))

                    # Проверяем, есть ли обсуждение (комментарии)
                    has_comments = False
                    last_post_id = 0
                    last_post_date = ""
                    can_comment = False
                    can_video = False
                    username = getattr(entity, 'username', '')

                    # Проверяем, включены ли комментарии
                    if hasattr(full_chat, 'linked_chat_id') and full_chat.linked_chat_id:
                        has_comments = True

                        # Получаем последние сообщения для поиска поста для комментирования
                        messages = await client.get_messages(entity, limit=10)

                        for message in messages:
                            if not isinstance(message, Message) or message.message == '':
                                continue

                            # Проверяем, можно ли комментировать это сообщение
                            try:
                                # Пробуем получить информацию об обсуждении
                                if hasattr(message, 'id'):
                                    # Пробуем отправить тестовый комментарий
                                    try:
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

                                        # Проверяем возможность отправки видео в комментарии
                                        try:
                                            with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
                                                f.write(b"test video content")
                                                test_file = f.name

                                            test_video = await client.send_file(
                                                entity,
                                                test_file,
                                                caption="Тест видео в комментарии",
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

                                        break  # Нашли подходящий пост, выходим

                                    except Exception as e:
                                        continue

                            except Exception as e:
                                continue

                    # Определяем тип чата
                    if hasattr(entity, 'broadcast') and entity.broadcast:
                        chat_type = "Канал"
                    elif hasattr(entity, 'megagroup') and entity.megagroup:
                        chat_type = "Супергруппа"
                    else:
                        chat_type = "Группа"

                    # Пробуем вступить в чат
                    access_type = "Закрытый"
                    try:
                        if hasattr(entity, 'username') and entity.username:
                            try:
                                await client(JoinChannelRequest(entity.username))
                                access_type = "Открытый"
                            except UserAlreadyParticipantError:
                                access_type = "Уже участник"
                    except Exception:
                        pass

                    # Сохраняем найденный чат
                    if has_comments and can_comment:
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
                        self.progress.emit(f"💬 Найден: {count} - {dialog.name} (пост от {last_post_date})")

                except Exception as e:
                    continue

            # Дополнительный поиск в популярных каналах с комментариями
            popular_comment_channels = [
                '@tgraphio', '@rednotes', '@breakingmash',
                '@rian_ru', '@meduzaproject', '@bbcrussian'
            ]

            for channel in popular_comment_channels:
                if count >= self.limit:
                    break

                try:
                    entity = await client.get_entity(channel)
                    chat_id = str(entity.id)

                    if chat_id in existing_chats or chat_id in found_chats:
                        continue

                    # Проверяем наличие комментариев
                    full_chat = await client(GetFullChannelRequest(entity))
                    has_comments = hasattr(full_chat, 'linked_chat_id') and full_chat.linked_chat_id

                    if has_comments:
                        # Аналогичная проверка возможности комментирования
                        messages = await client.get_messages(entity, limit=5)
                        can_comment = False
                        last_post_id = 0
                        last_post_date = ""
                        can_video = False

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
                                last_post_date = message.date.strftime('%d.%m.%Y %H:%M') if message.date else ""
                                break
                            except:
                                continue

                        if can_comment:
                            found_chats[chat_id] = {
                                'title': getattr(entity, 'title', channel),
                                'type': "Канал",
                                'access_type': "Открытый",
                                'can_comment': can_comment,
                                'can_video': can_video,
                                'last_post_id': last_post_id,
                                'last_post_date': last_post_date,
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
                self.progress.emit("❌ Каналы с комментариями не найдены. Попробуйте другой запрос.")
            else:
                self.progress.emit(f"🎯 Поиск завершен. Найдено каналов с комментариями: {len(found_chats)}")

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
                        remaining_limit = self.daily_limit - today_sent

                        self.progress.emit(
                            f"✅ Комментарий отправлен в {chat_title} ({sent_count}/{remaining_limit})",
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
                        CommentsManager.update_chat_status(chat_id, 'ошибка')

                if sent_count == 0:
                    self.progress.emit(
                        "❌ Не удалось отправить ни одного комментария",
                        0, 1
                    )
                    break

                if sent_count < len(chat_ids):
                    self.progress.emit(
                        f"⏳ Все комментарии отправлены. Ждем следующего дня...",
                        len(chat_ids), len(chat_ids)
                    )

                    tomorrow = datetime.now() + timedelta(days=1)
                    wait_until = tomorrow.replace(hour=11, minute=0, second=0, microsecond=0)
                    wait_seconds = (wait_until - datetime.now()).total_seconds()

                    for sec in range(int(wait_seconds)):
                        if not self.is_running:
                            await client.disconnect()
                            return "⏹️ Автоматическая рассылка комментариев остановлена"
                        await asyncio.sleep(1)

            await client.disconnect()
            return "✅ Автоматическая рассылка комментариев завершена"

        except Exception as e:
            await client.disconnect()
            raise e


class CommentsMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_chats()
        self.load_settings()
        self.check_auth_status()

    def init_ui(self):
        self.setWindowTitle('Telegram Comments Bot - Автоматическая рассылка комментариев')
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)

        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 800])

        # Левая панель - управление
        auth_group = QGroupBox("Авторизация")
        auth_layout = QVBoxLayout()
        self.auth_status_label = QLabel("❌ Не авторизован")
        self.auth_status_label.setStyleSheet("color: red; font-weight: bold;")
        auth_layout.addWidget(self.auth_status_label)

        self.auth_btn = QPushButton("Авторизоваться")
        self.auth_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.auth_btn.clicked.connect(self.show_auth_dialog)
        auth_layout.addWidget(self.auth_btn)

        self.logout_btn = QPushButton("Выйти")
        self.logout_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.logout_btn.clicked.connect(self.logout)
        auth_layout.addWidget(self.logout_btn)
        auth_group.setLayout(auth_layout)
        left_layout.addWidget(auth_group)

        # Поиск чатов
        search_group = QGroupBox("Поиск чатов с комментариями")
        search_layout = QVBoxLayout()

        search_layout.addWidget(QLabel("Поисковый запрос:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Введите запрос для поиска (например: новости, спорт)")
        search_layout.addWidget(self.search_edit)

        search_layout.addWidget(QLabel("Лимит поиска:"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 100)
        self.limit_spin.setValue(20)
        search_layout.addWidget(self.limit_spin)

        self.search_btn = QPushButton("🔍 Начать поиск")
        self.search_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        self.search_btn.clicked.connect(self.start_search)
        search_layout.addWidget(self.search_btn)

        self.progress_label = QLabel("Готов к поиску...")
        self.progress_label.setStyleSheet("color: blue;")
        search_layout.addWidget(self.progress_label)

        search_group.setLayout(search_layout)
        left_layout.addWidget(search_group)

        # Управление списком
        list_group = QGroupBox("Управление списком чатов")
        list_layout = QVBoxLayout()

        self.leave_chats_btn = QPushButton("🚪 Выйти из неиспользуемых чатов")
        self.leave_chats_btn.setStyleSheet("background-color: #FF9800; color: white;")
        self.leave_chats_btn.clicked.connect(self.leave_unused_chats)
        list_layout.addWidget(self.leave_chats_btn)

        self.delete_chats_btn = QPushButton("🗑️ Удалить выбранные чаты")
        self.delete_chats_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.delete_chats_btn.clicked.connect(self.delete_selected_chats)
        list_layout.addWidget(self.delete_chats_btn)

        self.select_all_btn = QPushButton("☑️ Выбрать все")
        self.select_all_btn.clicked.connect(self.select_all_chats)
        list_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("◻️ Снять выделение")
        self.deselect_all_btn.clicked.connect(self.deselect_all_chats)
        list_layout.addWidget(self.deselect_all_btn)

        list_group.setLayout(list_layout)
        left_layout.addWidget(list_group)

        # Настройки
        settings_group = QGroupBox("Настройки рассылки")
        settings_layout = QVBoxLayout()

        settings_layout.addWidget(QLabel("Дневной лимит комментариев:"))
        self.daily_limit_spin = QSpinBox()
        self.daily_limit_spin.setRange(1, 50)
        self.daily_limit_spin.setValue(10)
        settings_layout.addWidget(self.daily_limit_spin)

        settings_layout.addWidget(QLabel("Мин. задержка (секунды):"))
        self.min_delay_spin = QSpinBox()
        self.min_delay_spin.setRange(60, 36000)
        self.min_delay_spin.setValue(3600)
        settings_layout.addWidget(self.min_delay_spin)

        settings_layout.addWidget(QLabel("Макс. задержка (секунды):"))
        self.max_delay_spin = QSpinBox()
        self.max_delay_spin.setRange(60, 36000)
        self.max_delay_spin.setValue(5400)
        settings_layout.addWidget(self.max_delay_spin)

        self.save_settings_btn = QPushButton("💾 Сохранить настройки")
        self.save_settings_btn.setStyleSheet("background-color: #607D8B; color: white;")
        self.save_settings_btn.clicked.connect(self.save_settings)
        settings_layout.addWidget(self.save_settings_btn)

        settings_group.setLayout(settings_layout)
        left_layout.addWidget(settings_group)

        left_layout.addStretch()

        # Правая панель - список чатов и рассылка
        chats_group = QGroupBox("Список чатов для комментариев")
        chats_layout = QVBoxLayout()

        self.chats_list = QListWidget()
        self.chats_list.setSelectionMode(QListWidget.MultiSelection)
        chats_layout.addWidget(self.chats_list)

        chats_group.setLayout(chats_layout)
        right_layout.addWidget(chats_group)

        # Сообщение для комментариев
        message_group = QGroupBox("Сообщение для комментариев")
        message_layout = QVBoxLayout()

        self.message_edit = QTextEdit()
        self.message_edit.setPlaceholderText("Введите текст комментария...")
        self.message_edit.setMaximumHeight(100)
        message_layout.addWidget(self.message_edit)

        video_layout = QHBoxLayout()
        self.video_check = QCheckBox("Добавить видео")
        video_layout.addWidget(self.video_check)

        self.video_path_edit = QLineEdit()
        self.video_path_edit.setPlaceholderText("Путь к видеофайлу...")
        video_layout.addWidget(self.video_path_edit)

        self.video_browse_btn = QPushButton("Обзор")
        self.video_browse_btn.clicked.connect(self.browse_video)
        video_layout.addWidget(self.video_browse_btn)

        message_layout.addLayout(video_layout)
        message_group.setLayout(message_layout)
        right_layout.addWidget(message_group)

        # Управление рассылкой
        send_group = QGroupBox("Управление рассылкой комментариев")
        send_layout = QVBoxLayout()

        stats_layout = QHBoxLayout()
        self.stats_label = QLabel("Статистика: всего 0, выбрано 0, отправлено 0, сегодня 0")
        stats_layout.addWidget(self.stats_label)

        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.clicked.connect(self.load_chats)
        stats_layout.addWidget(self.refresh_btn)

        send_layout.addLayout(stats_layout)

        self.test_send_btn = QPushButton("🧪 Тестовый комментарий")
        self.test_send_btn.setStyleSheet("background-color: #FFC107; color: black; font-weight: bold;")
        self.test_send_btn.clicked.connect(self.send_test_comment)
        send_layout.addWidget(self.test_send_btn)

        self.auto_send_btn = QPushButton("🚀 Запустить авто-рассылку")
        self.auto_send_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.auto_send_btn.clicked.connect(self.start_auto_send)
        send_layout.addWidget(self.auto_send_btn)

        self.stop_send_btn = QPushButton("⏹️ Остановить рассылку")
        self.stop_send_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.stop_send_btn.clicked.connect(self.stop_auto_send)
        self.stop_send_btn.setEnabled(False)
        send_layout.addWidget(self.stop_send_btn)

        self.send_progress = QProgressBar()
        send_layout.addWidget(self.send_progress)

        self.send_status_label = QLabel("Готов к работе...")
        self.send_status_label.setStyleSheet("color: blue;")
        send_layout.addWidget(self.send_status_label)

        send_group.setLayout(send_layout)
        right_layout.addWidget(send_group)

        # Лог
        log_group = QGroupBox("Лог выполнения")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        right_layout.addWidget(log_group)

        self.auto_send_thread = None

    def check_auth_status(self):
        """Проверяет статус авторизации"""
        if os.path.exists(SESSION_FILE):
            self.auth_status_label.setText("✅ Авторизован")
            self.auth_status_label.setStyleSheet("color: green; font-weight: bold;")
            self.auth_btn.setEnabled(False)
            self.logout_btn.setEnabled(True)
        else:
            self.auth_status_label.setText("❌ Не авторизован")
            self.auth_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.auth_btn.setEnabled(True)
            self.logout_btn.setEnabled(False)

    def show_auth_dialog(self):
        """Показывает диалог авторизации"""
        dialog = AuthDialog(self)
        dialog.authorization_success.connect(self.on_auth_success)
        dialog.exec_()

    def on_auth_success(self):
        """Обработчик успешной авторизации"""
        self.check_auth_status()
        self.log_message("✅ Авторизация успешна!")

    def logout(self):
        """Выход из аккаунта"""
        try:
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)
            self.check_auth_status()
            self.log_message("✅ Выход выполнен успешно!")
        except Exception as e:
            self.log_message(f"❌ Ошибка выхода: {str(e)}")

    def load_settings(self):
        """Загружает настройки"""
        settings = SettingsManager.load_settings()
        self.daily_limit_spin.setValue(settings['daily_limit'])
        self.min_delay_spin.setValue(settings['min_delay'])
        self.max_delay_spin.setValue(settings['max_delay'])

    def save_settings(self):
        """Сохраняет настройки"""
        settings = {
            'daily_limit': self.daily_limit_spin.value(),
            'min_delay': self.min_delay_spin.value(),
            'max_delay': self.max_delay_spin.value()
        }

        if SettingsManager.save_settings(settings):
            self.log_message("✅ Настройки сохранены!")
        else:
            self.log_message("❌ Ошибка сохранения настроек!")

    def load_chats(self):
        """Загружает список чатов"""
        self.chats_list.clear()
        chats = CommentsManager.load_chats()

        total_chats = len(chats)
        selected_count = 0
        sent_count = sum(1 for chat in chats.values() if chat['status'] == 'отправлено')
        today_sent = CommentsManager.get_today_sent_count()

        for chat_id, chat_data in chats.items():
            title = chat_data['title']
            chat_type = chat_data['type']
            access_type = chat_data['access_type']
            can_comment = chat_data['can_comment']
            can_video = chat_data['can_video']
            status = chat_data['status']
            last_post_date = chat_data.get('last_post_date', '')
            username = chat_data.get('username', '')

            item_text = f"{title} [{chat_type}]"
            if username:
                item_text += f" (@{username})"
            item_text += f" - {access_type}"

            if can_comment:
                item_text += " 💬"
            if can_video:
                item_text += " 🎥"

            item_text += f" | {status}"
            if last_post_date:
                item_text += f" | пост: {last_post_date}"

            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, chat_id)

            # Цветовая маркировка статуса
            if status == 'отправлено':
                item.setBackground(Qt.green)
            elif status == 'ошибка':
                item.setBackground(Qt.red)
            elif status == 'не отправлено':
                item.setBackground(Qt.yellow)

            self.chats_list.addItem(item)

        self.update_stats(total_chats, selected_count, sent_count, today_sent)

    def update_stats(self, total, selected, sent, today_sent):
        """Обновляет статистику"""
        self.stats_label.setText(
            f"Статистика: всего {total}, выбрано {selected}, отправлено {sent}, сегодня {today_sent}/{self.daily_limit_spin.value()}"
        )

    def log_message(self, message):
        """Добавляет сообщение в лог"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.append(f"[{timestamp}] {message}")
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def start_search(self):
        """Запускает поиск чатов"""
        if not os.path.exists(SESSION_FILE):
            QMessageBox.warning(self, 'Ошибка', 'Сначала авторизуйтесь!')
            return

        search_query = self.search_edit.text().strip()
        limit = self.limit_spin.value()

        self.search_btn.setEnabled(False)
        self.progress_label.setText("🔍 Поиск запущен...")

        self.search_thread = CommentsSearchThread(search_query, limit)
        self.search_thread.progress.connect(self.on_search_progress)
        self.search_thread.finished.connect(self.on_search_finished)
        self.search_thread.error.connect(self.on_search_error)
        self.search_thread.start()

    def on_search_progress(self, message):
        """Обработчик прогресса поиска"""
        self.progress_label.setText(message)
        self.log_message(message)

    def on_search_finished(self, found_chats):
        """Обработчик завершения поиска"""
        if found_chats:
            if CommentsManager.add_chats(found_chats):
                self.load_chats()
                self.log_message(f"✅ Найдено и добавлено {len(found_chats)} чатов с комментариями!")
            else:
                self.log_message("❌ Ошибка сохранения найденных чатов!")
        else:
            self.log_message("❌ Чаты с комментариями не найдены!")

        self.search_btn.setEnabled(True)
        self.progress_label.setText("Поиск завершен")

    def on_search_error(self, error_message):
        """Обработчик ошибки поиска"""
        self.log_message(f"❌ Ошибка поиска: {error_message}")
        self.search_btn.setEnabled(True)
        self.progress_label.setText("Ошибка поиска")

    def leave_unused_chats(self):
        """Выход из неиспользуемых чатов"""
        if not os.path.exists(SESSION_FILE):
            QMessageBox.warning(self, 'Ошибка', 'Сначала авторизуйтесь!')
            return

        chats = CommentsManager.load_chats()
        chat_ids_to_keep = list(chats.keys())

        reply = QMessageBox.question(
            self, 'Подтверждение',
            f'Вы уверены, что хотите выйти из всех чатов, кроме {len(chat_ids_to_keep)} сохраненных?',
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.leave_chats_btn.setEnabled(False)
            self.log_message("🚪 Начинаем выход из неиспользуемых чатов...")

            self.leave_thread = LeaveChatsThread(chat_ids_to_keep)
            self.leave_thread.progress.connect(self.log_message)
            self.leave_thread.finished.connect(self.on_leave_finished)
            self.leave_thread.error.connect(self.on_leave_error)
            self.leave_thread.start()

    def on_leave_finished(self, count):
        """Обработчик завершения выхода из чатов"""
        self.log_message(f"✅ Выход из {count} чатов завершен!")
        self.leave_chats_btn.setEnabled(True)

    def on_leave_error(self, error_message):
        """Обработчик ошибки выхода из чатов"""
        self.log_message(f"❌ Ошибка выхода из чатов: {error_message}")
        self.leave_chats_btn.setEnabled(True)

    def delete_selected_chats(self):
        """Удаляет выбранные чаты из списка"""
        selected_items = self.chats_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, 'Ошибка', 'Выберите чаты для удаления!')
            return

        chat_ids = [item.data(Qt.UserRole) for item in selected_items]

        reply = QMessageBox.question(
            self, 'Подтверждение',
            f'Вы уверены, что хотите удалить {len(chat_ids)} чатов из списка?',
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if CommentsManager.delete_chats(chat_ids):
                self.load_chats()
                self.log_message(f"✅ Удалено {len(chat_ids)} чатов из списка!")
            else:
                self.log_message("❌ Ошибка удаления чатов!")

    def select_all_chats(self):
        """Выбирает все чаты в списке"""
        for i in range(self.chats_list.count()):
            item = self.chats_list.item(i)
            item.setSelected(True)

    def deselect_all_chats(self):
        """Снимает выделение со всех чатов"""
        for i in range(self.chats_list.count()):
            item = self.chats_list.item(i)
            item.setSelected(False)

    def browse_video(self):
        """Открывает диалог выбора видеофайла"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите видеофайл", "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.webm);;All Files (*)"
        )

        if file_path:
            self.video_path_edit.setText(file_path)

    def send_test_comment(self):
        """Отправляет тестовый комментарий"""
        if not os.path.exists(SESSION_FILE):
            QMessageBox.warning(self, 'Ошибка', 'Сначала авторизуйтесь!')
            return

        selected_items = self.chats_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, 'Ошибка', 'Выберите чат для тестового комментария!')
            return

        if len(selected_items) > 1:
            QMessageBox.warning(self, 'Ошибка', 'Выберите только один чат для теста!')
            return

        message = self.message_edit.toPlainText().strip()
        if not message:
            QMessageBox.warning(self, 'Ошибка', 'Введите текст комментария!')
            return

        chat_id = selected_items[0].data(Qt.UserRole)
        video_path = self.video_path_edit.text().strip() if self.video_check.isChecked() else None

        if self.video_check.isChecked() and (not video_path or not os.path.exists(video_path)):
            QMessageBox.warning(self, 'Ошибка', 'Видеофайл не найден!')
            return

        self.test_send_btn.setEnabled(False)
        self.log_message("🧪 Отправляем тестовый комментарий...")

        self.send_thread = SendCommentThread(chat_id, message, video_path)
        self.send_thread.finished.connect(self.on_send_finished)
        self.send_thread.error.connect(self.on_send_error)
        self.send_thread.start()

    def on_send_finished(self, success, message):
        """Обработчик завершения отправки"""
        self.log_message(message)
        self.test_send_btn.setEnabled(True)
        self.load_chats()

    def on_send_error(self, error_message):
        """Обработчик ошибки отправки"""
        self.log_message(f"❌ Ошибка отправки: {error_message}")
        self.test_send_btn.setEnabled(True)

    def start_auto_send(self):
        """Запускает автоматическую рассылку"""
        if not os.path.exists(SESSION_FILE):
            QMessageBox.warning(self, 'Ошибка', 'Сначала авторизуйтесь!')
            return

        selected_items = self.chats_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, 'Ошибка', 'Выберите чаты для рассылки!')
            return

        message = self.message_edit.toPlainText().strip()
        if not message:
            QMessageBox.warning(self, 'Ошибка', 'Введите текст комментария!')
            return

        video_path = self.video_path_edit.text().strip() if self.video_check.isChecked() else None
        if self.video_check.isChecked() and (not video_path or not os.path.exists(video_path)):
            QMessageBox.warning(self, 'Ошибка', 'Видеофайл не найден!')
            return

        chat_ids = [item.data(Qt.UserRole) for item in selected_items]

        settings = {
            'daily_limit': self.daily_limit_spin.value(),
            'min_delay': self.min_delay_spin.value(),
            'max_delay': self.max_delay_spin.value()
        }

        self.auto_send_btn.setEnabled(False)
        self.stop_send_btn.setEnabled(True)
        self.send_progress.setValue(0)

        self.log_message("🚀 Запускаем автоматическую рассылку комментариев...")

        self.auto_send_thread = AutoCommentsThread(
            message, video_path, chat_ids,
            settings['min_delay'], settings['max_delay'], settings['daily_limit']
        )
        self.auto_send_thread.progress.connect(self.on_auto_send_progress)
        self.auto_send_thread.finished.connect(self.on_auto_send_finished)
        self.auto_send_thread.error.connect(self.on_auto_send_error)
        self.auto_send_thread.start()

    def on_auto_send_progress(self, message, current, total):
        """Обработчик прогресса автоматической рассылки"""
        self.send_status_label.setText(message)
        self.log_message(message)

        if total > 0:
            progress = int((current / total) * 100)
            self.send_progress.setValue(progress)

    def on_auto_send_finished(self, message):
        """Обработчик завершения автоматической рассылки"""
        self.log_message(message)
        self.send_status_label.setText("Рассылка завершена")
        self.auto_send_btn.setEnabled(True)
        self.stop_send_btn.setEnabled(False)
        self.send_progress.setValue(100)
        self.load_chats()

    def on_auto_send_error(self, error_message):
        """Обработчик ошибки автоматической рассылки"""
        self.log_message(f"❌ Ошибка рассылки: {error_message}")
        self.send_status_label.setText("Ошибка рассылки")
        self.auto_send_btn.setEnabled(True)
        self.stop_send_btn.setEnabled(False)
        self.send_progress.setValue(0)

    def stop_auto_send(self):
        """Останавливает автоматическую рассылку"""
        if self.auto_send_thread and self.auto_send_thread.isRunning():
            self.auto_send_thread.stop_sending()
            self.log_message("⏹️ Останавливаем рассылку...")
            self.stop_send_btn.setEnabled(False)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Telegram Comments Bot")

    window = CommentsMainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()