import sys
import asyncio
import os
import random
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError, ChatWriteForbiddenError, ChannelPrivateError, \
    InviteRequestSentError, UserAlreadyParticipantError
from telethon.tl.functions.messages import GetDialogsRequest, ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.types import InputPeerEmpty, Channel, ChatForbidden
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
CHATS_FILE = 'chats_list.txt'
SETTINGS_FILE = 'settings.txt'


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


class ChatsManager:
    @staticmethod
    def load_chats():
        """Загружает чаты из файла"""
        chats = {}
        if os.path.exists(CHATS_FILE):
            try:
                with open(CHATS_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if ',' in line:
                            parts = line.split(',')
                            if len(parts) >= 6:
                                chat_id = parts[0]
                                chat_title = parts[1]
                                chat_type = parts[2]
                                access_type = parts[3]
                                can_text = parts[4] == 'True'
                                can_video = parts[5] == 'True'
                                status = parts[6] if len(parts) > 6 else 'не отправлено'
                                send_time = parts[7] if len(parts) > 7 else ''
                                username = parts[8] if len(parts) > 8 else ''

                                chats[chat_id] = {
                                    'title': chat_title,
                                    'type': chat_type,
                                    'access_type': access_type,
                                    'can_text': can_text,
                                    'can_video': can_video,
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
            with open(CHATS_FILE, 'w', encoding='utf-8') as f:
                for chat_id, data in chats.items():
                    title = data['title']
                    chat_type = data['type']
                    access_type = data['access_type']
                    can_text = str(data['can_text'])
                    can_video = str(data['can_video'])
                    status = data['status']
                    send_time = data.get('send_time', '')
                    username = data.get('username', '')
                    f.write(
                        f"{chat_id},{title},{chat_type},{access_type},{can_text},{can_video},{status},{send_time},{username}\n")
            return True
        except Exception as e:
            print(f"Ошибка сохранения файла чатов: {e}")
            return False

    @staticmethod
    def add_chats(new_chats):
        """Добавляет новые чаты в файл"""
        existing_chats = ChatsManager.load_chats()

        for chat_id, chat_data in new_chats.items():
            if chat_id not in existing_chats:
                existing_chats[chat_id] = chat_data

        return ChatsManager.save_chats(existing_chats)

    @staticmethod
    def update_chat_status(chat_id, status, send_time=''):
        """Обновляет статус чата"""
        chats = ChatsManager.load_chats()
        if chat_id in chats:
            chats[chat_id]['status'] = status
            if send_time:
                chats[chat_id]['send_time'] = send_time
            return ChatsManager.save_chats(chats)
        return False

    @staticmethod
    def delete_chats(chat_ids):
        """Удаляет чаты из файла"""
        chats = ChatsManager.load_chats()
        for chat_id in chat_ids:
            if chat_id in chats:
                del chats[chat_id]
        return ChatsManager.save_chats(chats)

    @staticmethod
    def get_unsent_chats():
        """Возвращает список чатов со статусом 'не отправлено'"""
        chats = ChatsManager.load_chats()
        unsent_chats = {chat_id: data for chat_id, data in chats.items()
                        if data['status'] == 'не отправлено'}
        return unsent_chats

    @staticmethod
    def get_today_sent_count():
        """Возвращает количество сообщений, отправленных сегодня"""
        chats = ChatsManager.load_chats()
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


class GlobalSearchThread(QThread):
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
            result = loop.run_until_complete(self.global_search(client))
            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                loop.close()

    async def global_search(self, client):
        """Улучшенный глобальный поиск чатов"""
        found_chats = {}
        count = 0

        # Загружаем существующие чаты для проверки дубликатов
        existing_chats = ChatsManager.load_chats()

        try:
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                raise Exception("Пользователь не авторизован")

            self.progress.emit("🔍 Начинаем глобальный поиск...")

            # Метод 1: Поиск через метод поиска Telegram
            try:
                self.progress.emit("🌐 Ищем через глобальный поиск...")
                search_results = await client.get_dialogs(limit=100)

                for dialog in search_results:
                    if count >= self.limit:
                        break

                    if not dialog.is_channel and not dialog.is_group:
                        continue

                    entity = dialog.entity
                    chat_title = dialog.name.lower()

                    # Фильтрация по поисковому запросу
                    if self.search_query and self.search_query.lower() not in chat_title:
                        continue

                    try:
                        # Получаем полную информацию о чате
                        full_chat = await client.get_entity(entity.id)

                        chat_id = str(full_chat.id)

                        # Пропускаем чаты, которые уже есть в списке
                        if chat_id in existing_chats:
                            self.progress.emit(f"⏭️ Пропускаем {dialog.name} - уже в списке")
                            continue

                        if chat_id in found_chats:
                            continue

                        # Определяем тип чата
                        if hasattr(full_chat, 'broadcast') and full_chat.broadcast:
                            chat_type = "Канал"
                        elif hasattr(full_chat, 'megagroup') and full_chat.megagroup:
                            chat_type = "Супергруппа"
                        else:
                            chat_type = "Группа"

                        # Пробуем вступить в чат и проверить доступность
                        access_type = "Закрытый"
                        can_text = False
                        can_video = False
                        username = getattr(full_chat, 'username', '')

                        try:
                            # Пробуем вступить в чат
                            if hasattr(full_chat, 'username') and full_chat.username:
                                try:
                                    await client(JoinChannelRequest(full_chat.username))
                                    self.progress.emit(f"✅ Вступили в: {dialog.name}")
                                    access_type = "Открытый"
                                except UserAlreadyParticipantError:
                                    access_type = "Уже участник"
                                except Exception as e:
                                    self.progress.emit(f"❌ Не удалось вступить в {dialog.name}: {str(e)}")

                            # Проверяем возможность отправки сообщений
                            try:
                                test_message = await client.send_message(full_chat, "Привет!", silent=True)
                                await asyncio.sleep(1)
                                await client.delete_messages(full_chat, [test_message.id])
                                can_text = True

                                # Проверяем возможность отправки видео
                                try:
                                    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
                                        f.write(b"test video content")
                                        test_file = f.name

                                    test_video = await client.send_file(full_chat, test_file, caption="Тест видео")
                                    await asyncio.sleep(1)
                                    await client.delete_messages(full_chat, [test_video.id])
                                    can_video = True
                                    os.unlink(test_file)
                                except Exception as e:
                                    can_video = False
                                    if os.path.exists(test_file):
                                        try:
                                            os.unlink(test_file)
                                        except:
                                            pass

                            except Exception as e:
                                can_text = False

                        except Exception as e:
                            self.progress.emit(f"⚠️ Ошибка проверки {dialog.name}: {str(e)}")

                        # Сохраняем найденный чат
                        found_chats[chat_id] = {
                            'title': dialog.name,
                            'type': chat_type,
                            'access_type': access_type,
                            'can_text': can_text,
                            'can_video': can_video,
                            'status': 'не отправлено',
                            'send_time': '',
                            'username': username
                        }
                        count += 1
                        self.progress.emit(f"✅ Найден новый: {count} - {dialog.name} ({access_type})")

                    except Exception as e:
                        continue

            except Exception as e:
                self.progress.emit(f"⚠️ Ошибка поиска: {str(e)}")

            # Метод 2: Поиск через известные публичные каналы
            try:
                self.progress.emit("📢 Ищем в популярных каналах...")
                popular_channels = [
                    '@telegram', '@telegramtips', '@tgchannel',
                    '@test', '@news', '@breakingnews'
                ]

                for channel in popular_channels:
                    if count >= self.limit:
                        break

                    try:
                        entity = await client.get_entity(channel)
                        chat_id = str(entity.id)

                        # Пропускаем чаты, которые уже есть в списке
                        if chat_id in existing_chats:
                            self.progress.emit(f"⏭️ Пропускаем {channel} - уже в списке")
                            continue

                        if chat_id in found_chats:
                            continue

                        # Проверяем соответствие поисковому запросу
                        chat_title = getattr(entity, 'title', '').lower()
                        if self.search_query and self.search_query.lower() not in chat_title:
                            continue

                        # Аналогичная проверка доступности
                        access_type = "Открытый"
                        can_text = False
                        can_video = False
                        username = getattr(entity, 'username', '')

                        try:
                            await client(JoinChannelRequest(channel))

                            # Проверка отправки сообщений
                            try:
                                test_message = await client.send_message(entity, "Привет!", silent=True)
                                await asyncio.sleep(1)
                                await client.delete_messages(entity, [test_message.id])
                                can_text = True
                            except:
                                can_text = False

                        except UserAlreadyParticipantError:
                            access_type = "Уже участник"
                        except Exception as e:
                            access_type = "Закрытый"

                        found_chats[chat_id] = {
                            'title': getattr(entity, 'title', channel),
                            'type': "Канал",
                            'access_type': access_type,
                            'can_text': can_text,
                            'can_video': can_video,
                            'status': 'не отправлено',
                            'send_time': '',
                            'username': username
                        }
                        count += 1
                        self.progress.emit(f"📢 Найден новый: {count} - {channel}")

                    except Exception as e:
                        continue

            except Exception as e:
                self.progress.emit(f"⚠️ Ошибка поиска в популярных каналах: {str(e)}")

            await client.disconnect()

            if not found_chats:
                self.progress.emit("❌ Новые чаты не найдены. Попробуйте другой запрос.")
            else:
                self.progress.emit(f"🎯 Поиск завершен. Найдено новых чатов: {len(found_chats)}")

            return found_chats

        except Exception as e:
            try:
                await client.disconnect()
            except:
                pass
            raise e


class LeaveChatsThread(QThread):
    """Поток для выхода из чатов, которые не были добавлены в список рассылки"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, chat_ids_to_keep):
        super().__init__()
        self.chat_ids_to_keep = chat_ids_to_keep  # ID чатов, которые нужно сохранить

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
        """Выходит из чатов, которые не входят в список для сохранения"""
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            raise Exception("Пользователь не авторизован")

        try:
            left_count = 0

            # Получаем все текущие диалоги
            dialogs = await client.get_dialogs(limit=100)

            for dialog in dialogs:
                if not dialog.is_channel and not dialog.is_group:
                    continue

                entity = dialog.entity
                chat_id = str(entity.id)

                # Если чат не в списке для сохранения - выходим из него
                if chat_id not in self.chat_ids_to_keep:
                    try:
                        if hasattr(entity, 'username') and entity.username:
                            await client(LeaveChannelRequest(entity))
                            self.progress.emit(f"🚪 Выходим из: {dialog.name}")
                            left_count += 1
                            await asyncio.sleep(1)  # Задержка между выходами
                    except Exception as e:
                        self.progress.emit(f"⚠️ Не удалось выйти из {dialog.name}: {str(e)}")

            await client.disconnect()
            return left_count

        except Exception as e:
            await client.disconnect()
            raise e


class SendToChatThread(QThread):
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
            result = loop.run_until_complete(self.send_to_chat(client))
            self.finished.emit(True, result)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                loop.close()

    async def send_to_chat(self, client):
        await client.connect()
        if not client.is_connected():
            await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            raise Exception("Пользователь не авторизован")

        try:
            await asyncio.sleep(self.delay)

            # Получаем entity чата
            entity = await client.get_entity(int(self.chat_id))

            # Получаем информацию о чате
            chats = ChatsManager.load_chats()
            chat_info = chats.get(self.chat_id, {})
            can_video = chat_info.get('can_video', False)

            if self.video_path and os.path.exists(self.video_path) and can_video:
                # Отправляем видео с комментарием
                if self.message.strip():
                    await client.send_file(entity, self.video_path, caption=self.message)
                else:
                    await client.send_file(entity, self.video_path)
            else:
                # Отправляем только текст
                await client.send_message(entity, self.message)

            await asyncio.sleep(1)
            await client.disconnect()

            # Обновляем статус
            send_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
            ChatsManager.update_chat_status(self.chat_id, 'отправлено', send_time)

            chat_title = chat_info.get('title', 'чат')
            return f"✅ Сообщение отправлено в {chat_title}"

        except FloodWaitError as e:
            wait_time = e.seconds
            await client.disconnect()
            raise Exception(f"⏳ Лимит Telegram! Подождите {wait_time} секунд")
        except Exception as e:
            await client.disconnect()
            raise Exception(f"❌ Ошибка: {str(e)}")


class AutoSendThread(QThread):
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
            result = loop.run_until_complete(self.auto_send_messages(client))
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
        return ChatsManager.get_today_sent_count()

    def can_send_today(self):
        return self.get_today_sent_count() < self.daily_limit

    async def auto_send_messages(self, client):
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
                            return "⏹️ Автоматическая рассылка остановлена"
                        await asyncio.sleep(1)
                    continue

                # Используем выбранные чаты
                selected_chats = {chat_id: ChatsManager.load_chats()[chat_id]
                                  for chat_id in self.selected_chats
                                  if chat_id in ChatsManager.load_chats() and
                                  ChatsManager.load_chats()[chat_id]['status'] == 'не отправлено'}

                total_chats = len(selected_chats)

                if total_chats == 0:
                    await client.disconnect()
                    return "❌ Нет выбранных чатов для рассылки"

                today_sent = self.get_today_sent_count()
                remaining_limit = self.daily_limit - today_sent

                if remaining_limit <= 0:
                    tomorrow = datetime.now() + timedelta(days=1)
                    wait_until = tomorrow.replace(hour=11, minute=0, second=0, microsecond=0)
                    wait_seconds = (wait_until - datetime.now()).total_seconds()

                    self.progress.emit(
                        f"📅 Достигнут дневной лимит ({self.daily_limit} сообщений). Ждем до завтра 11:00",
                        0, 1
                    )

                    for sec in range(int(wait_seconds)):
                        if not self.is_running:
                            await client.disconnect()
                            return "⏹️ Автоматическая рассылка остановлена"
                        await asyncio.sleep(1)
                    continue

                # Отправляем сообщения
                sent_count = 0
                chat_ids = list(selected_chats.keys())[:remaining_limit]

                for i, chat_id in enumerate(chat_ids):
                    if not self.is_running:
                        await client.disconnect()
                        return "⏹️ Автоматическая рассылка остановлена"

                    chat_info = selected_chats[chat_id]
                    chat_title = chat_info['title']

                    # Проверяем, можно ли отправлять видео
                    can_video = chat_info.get('can_video', False)
                    if self.video_path and not can_video:
                        self.progress.emit(
                            f"⏭️ Пропускаем {chat_title} - нельзя отправить видео",
                            i, len(chat_ids)
                        )
                        continue

                    if sent_count > 0:
                        delay_seconds = random.randint(self.min_delay, self.max_delay)
                        delay_minutes = delay_seconds // 60
                        delay_secs = delay_seconds % 60

                        self.progress.emit(
                            f"⏰ Ожидание {delay_minutes} мин {delay_secs} сек перед отправкой в {chat_title}",
                            i, len(chat_ids)
                        )

                        for sec in range(delay_seconds):
                            if not self.is_running:
                                await client.disconnect()
                                return "⏹️ Автоматическая рассылка остановлена"
                            if not self.is_working_time():
                                break
                            await asyncio.sleep(1)

                        if not self.is_running:
                            await client.disconnect()
                            return "⏹️ Автоматическая рассылка остановлена"

                        if not self.is_working_time():
                            self.progress.emit(
                                f"⏳ Время работы истекло (11:00-21:00). Продолжим завтра",
                                i, len(chat_ids)
                            )
                            break

                    self.progress.emit(
                        f"📨 Отправка в {chat_title} ({i + 1}/{len(chat_ids)})", i, len(chat_ids))

                    try:
                        entity = await client.get_entity(int(chat_id))

                        if self.video_path and os.path.exists(self.video_path) and can_video:
                            if self.message.strip():
                                await client.send_file(entity, self.video_path, caption=self.message)
                            else:
                                await client.send_file(entity, self.video_path)
                        else:
                            await client.send_message(entity, self.message)

                        send_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
                        ChatsManager.update_chat_status(chat_id, 'отправлено', send_time)

                        sent_count += 1
                        await asyncio.sleep(2)

                    except FloodWaitError as e:
                        wait_time = e.seconds
                        self.progress.emit(
                            f"⏳ Лимит! Ждем {wait_time} сек. Пропускаем {chat_title}",
                            i, len(chat_ids)
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    except Exception as e:
                        self.progress.emit(
                            f"❌ Ошибка с {chat_title}: {str(e)}",
                            i, len(chat_ids)
                        )
                        await asyncio.sleep(10)
                        continue

                if sent_count > 0:
                    tomorrow = datetime.now() + timedelta(days=1)
                    wait_until = tomorrow.replace(hour=11, minute=0, second=0, microsecond=0)
                    wait_seconds = (wait_until - datetime.now()).total_seconds()

                    self.progress.emit(
                        f"✅ Отправлено {sent_count} сообщений сегодня. Ждем до завтра 11:00",
                        0, 1
                    )

                    for sec in range(int(wait_seconds)):
                        if not self.is_running:
                            await client.disconnect()
                            return "⏹️ Автоматическая рассылка остановлена"
                        await asyncio.sleep(1)

            await client.disconnect()
            return "⏹️ Автоматическая рассылка остановлена"

        except Exception as e:
            await client.disconnect()
            raise e


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = SettingsManager.load_settings()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Настройки')
        self.setFixedSize(400, 300)
        layout = QVBoxLayout()

        layout.addWidget(QLabel('Лимит сообщений в день:'))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 100)
        self.limit_spin.setValue(self.settings['daily_limit'])
        layout.addWidget(self.limit_spin)

        layout.addWidget(QLabel('Минимальная задержка (секунды):'))
        self.min_delay_spin = QSpinBox()
        self.min_delay_spin.setRange(60, 86400)
        self.min_delay_spin.setValue(self.settings['min_delay'])
        layout.addWidget(self.min_delay_spin)

        layout.addWidget(QLabel('Максимальная задержка (секунды):'))
        self.max_delay_spin = QSpinBox()
        self.max_delay_spin.setRange(60, 86400)
        self.max_delay_spin.setValue(self.settings['max_delay'])
        layout.addWidget(self.max_delay_spin)

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
        self.settings['daily_limit'] = self.limit_spin.value()
        self.settings['min_delay'] = self.min_delay_spin.value()
        self.settings['max_delay'] = self.max_delay_spin.value()

        if SettingsManager.save_settings(self.settings):
            QMessageBox.information(self, 'Успех', 'Настройки сохранены!')
            self.accept()
        else:
            QMessageBox.warning(self, 'Ошибка', 'Не удалось сохранить настройки')


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
        text_icon = "✅" if self.chat_data['can_text'] else "❌"
        video_icon = "✅" if self.chat_data['can_video'] else "❌"

        info_text = f"{self.chat_data['title']} - {self.chat_data['type']} "
        info_text += f"<span style='color: {access_color};'>({self.chat_data['access_type']})</span> "
        info_text += f"Текст:{text_icon} Видео:{video_icon}"

        chat_info = QLabel(info_text)
        chat_info.setToolTip(f"ID: {self.chat_id}\n"
                             f"Название: {self.chat_data['title']}\n"
                             f"Тип: {self.chat_data['type']}\n"
                             f"Доступ: {self.chat_data['access_type']}\n"
                             f"Можно текст: {'Да' if self.chat_data['can_text'] else 'Нет'}\n"
                             f"Можно видео: {'Да' if self.chat_data['can_video'] else 'Нет'}")
        layout.addWidget(chat_info)

        self.setLayout(layout)


class SelectChatsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_chats = set()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Выбор чатов для рассылки')
        self.setFixedSize(800, 600)
        layout = QVBoxLayout()

        # Заголовок
        title_label = QLabel('Выберите чаты для рассылки:')
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

        chats = ChatsManager.load_chats()
        for chat_id, chat_data in chats.items():
            chat_widget = ChatListWidget(chat_id, chat_data)
            self.chats_layout.addWidget(chat_widget)

        if not chats:
            no_chats_label = QLabel('Нет сохраненных чатов. Сначала выполните поиск и сохраните чаты.')
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


class TelegramBotApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = SettingsManager.load_settings()
        self.auto_send_thread = None
        self.leave_chats_thread = None
        self.is_authorized = False
        self.selected_chats_for_sending = set()
        self.video_path = None
        self.init_ui()
        self.check_authorization()

    def init_ui(self):
        self.setWindowTitle('Менеджер рассылки в Telegram чаты')
        self.setFixedSize(1200, 900)

        central_widget = QWidget()
        main_layout = QHBoxLayout()

        # Левая панель - поиск и управление чатами
        left_panel = QWidget()
        left_panel.setMaximumWidth(400)
        left_layout = QVBoxLayout()

        # Авторизация
        self.auth_btn = QPushButton('🔐 Авторизация')
        self.auth_btn.setStyleSheet('background-color: #FF9800; color: white; font-weight: bold; padding: 10px;')
        self.auth_btn.clicked.connect(self.auth_button_clicked)
        left_layout.addWidget(self.auth_btn)

        # Поиск чатов
        search_group = QGroupBox('Поиск чатов')
        search_layout = QVBoxLayout()

        search_input_layout = QHBoxLayout()
        search_input_layout.addWidget(QLabel('Ключевое слово:'))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('Введите часть названия чата')
        self.search_edit.returnPressed.connect(self.search_chats)
        search_input_layout.addWidget(self.search_edit)

        self.search_btn = QPushButton('🔍 Найти')
        self.search_btn.setStyleSheet('background-color: #2196F3; color: white; font-weight: bold;')
        self.search_btn.clicked.connect(self.search_chats)
        search_input_layout.addWidget(self.search_btn)

        search_layout.addLayout(search_input_layout)

        # Информация о тестовых сообщениях
        test_info = QLabel('💡 Тестовые сообщения "Привет!" автоматически удаляются')
        test_info.setStyleSheet('color: #666; font-size: 11px; padding: 5px;')
        search_layout.addWidget(test_info)

        search_group.setLayout(search_layout)
        left_layout.addWidget(search_group)

        # Список найденных чатов
        left_layout.addWidget(QLabel('Найденные чаты:'))

        self.found_chats_scroll = QScrollArea()
        self.found_chats_widget = QWidget()
        self.found_chats_layout = QVBoxLayout(self.found_chats_widget)
        self.found_chats_scroll.setWidget(self.found_chats_widget)
        self.found_chats_scroll.setWidgetResizable(True)
        self.found_chats_scroll.setMinimumHeight(200)
        left_layout.addWidget(self.found_chats_scroll)

        # Кнопки управления найденными чатами
        found_chats_buttons = QHBoxLayout()

        self.save_selected_btn = QPushButton('💾 Сохранить отмеченные')
        self.save_selected_btn.setStyleSheet('background-color: #4CAF50; color: white; font-weight: bold;')
        self.save_selected_btn.clicked.connect(self.save_selected_chats)
        found_chats_buttons.addWidget(self.save_selected_btn)

        self.clear_search_btn = QPushButton('🗑️ Очистить')
        self.clear_search_btn.setStyleSheet('background-color: #f44336; color: white; font-weight: bold;')
        self.clear_search_btn.clicked.connect(self.clear_search_results)
        found_chats_buttons.addWidget(self.clear_search_btn)

        left_layout.addLayout(found_chats_buttons)

        # Управление сохраненными чатами
        saved_chats_group = QGroupBox('Сохраненные чаты')
        saved_layout = QVBoxLayout()

        saved_buttons = QHBoxLayout()

        self.select_chats_btn = QPushButton('📋 Выбрать чаты для отправки')
        self.select_chats_btn.setStyleSheet('background-color: #FF9800; color: white; font-weight: bold;')
        self.select_chats_btn.clicked.connect(self.select_chats_for_sending)
        saved_buttons.addWidget(self.select_chats_btn)

        self.delete_chats_btn = QPushButton('🗑️ Удалить выбранные')
        self.delete_chats_btn.setStyleSheet('background-color: #f44336; color: white; font-weight: bold;')
        self.delete_chats_btn.clicked.connect(self.delete_selected_chats)
        saved_buttons.addWidget(self.delete_chats_btn)

        # Добавляем кнопку очистки чатов
        self.cleanup_chats_btn = QPushButton('🧹 Очистить неиспользуемые чаты')
        self.cleanup_chats_btn.setStyleSheet('background-color: #FF5722; color: white; font-weight: bold;')
        self.cleanup_chats_btn.clicked.connect(self.cleanup_unused_chats)
        self.cleanup_chats_btn.setToolTip('Выйдет из всех чатов, которые не добавлены в список рассылки')
        saved_buttons.addWidget(self.cleanup_chats_btn)

        saved_layout.addLayout(saved_buttons)

        # Информация о выбранных чатах
        self.selected_chats_info = QLabel('Выбрано чатов: 0')
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
        message_group = QGroupBox('Сообщение для рассылки')
        message_layout = QVBoxLayout()

        self.message_text = QTextEdit()
        self.message_text.setMinimumHeight(150)
        self.message_text.setPlaceholderText('Введите текст сообщения для рассылки...')
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
        message_group.setLayout(message_layout)
        right_layout.addWidget(message_group)

        # Статистика и управление
        stats_group = QGroupBox('Статистика и управление рассылкой')
        stats_layout = QVBoxLayout()

        stats_info_layout = QHBoxLayout()

        self.stats_label = QLabel('Всего чатов: 0 | Отправлено сегодня: 0/0')
        stats_info_layout.addWidget(self.stats_label)

        self.settings_btn = QPushButton('⚙️ Настройки')
        self.settings_btn.setStyleSheet('background-color: #607D8B; color: white;')
        self.settings_btn.clicked.connect(self.show_settings)
        stats_info_layout.addWidget(self.settings_btn)

        stats_layout.addLayout(stats_info_layout)

        # Прогресс бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        stats_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel('')
        self.progress_label.setVisible(False)
        stats_layout.addWidget(self.progress_label)

        # Кнопки отправки
        send_buttons_layout = QHBoxLayout()

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

    def check_authorization(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
            result = loop.run_until_complete(self.check_auth(client))
            self.is_authorized = result
            if result:
                self.auth_btn.setText('✅ Авторизован')
                self.auth_btn.setStyleSheet(
                    'background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;')
            else:
                self.auth_btn.setText('🔐 Авторизация')
                self.auth_btn.setStyleSheet(
                    'background-color: #FF9800; color: white; font-weight: bold; padding: 10px;')

        except Exception:
            self.is_authorized = False
            self.auth_btn.setText('🔐 Авторизация')
            self.auth_btn.setStyleSheet('background-color: #FF9800; color: white; font-weight: bold; padding: 10px;')
        finally:
            if loop and not loop.is_closed():
                loop.close()

    async def check_auth(self, client):
        try:
            await client.connect()
            if not client.is_connected():
                return False
            return await client.is_user_authorized()
        except:
            return False
        finally:
            await client.disconnect()

    def auth_button_clicked(self):
        if self.is_authorized:
            reply = QMessageBox.question(self, 'Выход', 'Вы уверены, что хотите выйти?',
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.logout()
        else:
            self.show_auth_dialog()

    def show_auth_dialog(self):
        auth_dialog = AuthDialog(self)
        auth_dialog.authorization_success.connect(self.on_auth_success)
        auth_dialog.exec_()

    def on_auth_success(self):
        self.is_authorized = True
        self.auth_btn.setText('✅ Авторизован')
        self.auth_btn.setStyleSheet('background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;')
        QMessageBox.information(self, 'Успех', 'Авторизация прошла успешно!')

    def logout(self):
        try:
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)
            self.is_authorized = False
            self.auth_btn.setText('🔐 Авторизация')
            self.auth_btn.setStyleSheet('background-color: #FF9800; color: white; font-weight: bold; padding: 10px;')
            QMessageBox.information(self, 'Выход', 'Вы успешно вышли из системы')
        except Exception as e:
            QMessageBox.warning(self, 'Ошибка', f'Ошибка при выходе: {str(e)}')

    def search_chats(self):
        if not self.is_authorized:
            QMessageBox.warning(self, 'Ошибка', 'Сначала авторизуйтесь!')
            return

        search_query = self.search_edit.text().strip()

        self.search_btn.setEnabled(False)
        self.search_btn.setText('Глобальный поиск...')

        self.global_search_thread = GlobalSearchThread(search_query, 30)
        self.global_search_thread.finished.connect(self.on_search_finished)
        self.global_search_thread.progress.connect(self.on_search_progress)
        self.global_search_thread.error.connect(self.on_search_error)
        self.global_search_thread.start()

    def on_search_progress(self, message):
        self.statusBar().showMessage(message)

    def on_search_finished(self, found_chats):
        self.search_btn.setEnabled(True)
        self.search_btn.setText('🔍 Найти')
        self.statusBar().showMessage(f'Найдено новых чатов: {len(found_chats)}')

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
            no_chats_label = QLabel('Новые чаты не найдены. Попробуйте другой запрос.')
            no_chats_label.setStyleSheet('color: gray; font-style: italic; padding: 20px;')
            no_chats_label.setAlignment(Qt.AlignCenter)
            self.found_chats_layout.addWidget(no_chats_label)

    def on_search_error(self, error_message):
        self.search_btn.setEnabled(True)
        self.search_btn.setText('🔍 Найти')
        QMessageBox.critical(self, 'Ошибка поиска', error_message)

    def save_selected_chats(self):
        if not hasattr(self, 'found_chats'):
            QMessageBox.warning(self, 'Ошибка', 'Сначала выполните поиск чатов')
            return

        selected_chats = {}
        for i in range(self.found_chats_layout.count()):
            widget = self.found_chats_layout.itemAt(i).widget()
            if isinstance(widget, ChatListWidget) and widget.checkbox.isChecked():
                selected_chats[widget.chat_id] = widget.chat_data

        if not selected_chats:
            QMessageBox.warning(self, 'Ошибка', 'Выберите хотя бы один чат')
            return

        if ChatsManager.add_chats(selected_chats):
            QMessageBox.information(self, 'Успех', f'Сохранено чатов: {len(selected_chats)}')
            self.update_stats()

            # Автоматически добавляем сохраненные чаты в выбранные для рассылки
            for chat_id in selected_chats.keys():
                self.selected_chats_for_sending.add(chat_id)
            self.selected_chats_info.setText(f'Выбрано чатов: {len(self.selected_chats_for_sending)}')

        else:
            QMessageBox.warning(self, 'Ошибка', 'Не удалось сохранить чаты')

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
            self.selected_chats_info.setText(f'Выбрано чатов: {len(self.selected_chats_for_sending)}')
            QMessageBox.information(self, 'Успех', f'Выбрано {len(self.selected_chats_for_sending)} чатов для рассылки')

    def delete_selected_chats(self):
        """Удаляет выбранные чаты и выходит из них"""
        chats_to_delete = []

        dialog = SelectChatsDialog(self)
        dialog.load_chats()
        dialog.setWindowTitle('Выберите чаты для удаления')
        if dialog.exec_() == QDialog.Accepted:
            chats_to_delete = dialog.get_selected_chats()

        if not chats_to_delete:
            return

        reply = QMessageBox.question(self, 'Подтверждение',
                                     f'Вы уверены, что хотите удалить {len(chats_to_delete)} чатов и выйти из них?',
                                     QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            # Сначала выходим из чатов
            self.leave_chats_after_deletion(chats_to_delete)

            # Затем удаляем из списка
            if ChatsManager.delete_chats(chats_to_delete):
                QMessageBox.information(self, 'Успех', f'Удалено {len(chats_to_delete)} чатов')
                self.update_stats()
                # Обновляем список выбранных чатов
                self.selected_chats_for_sending = self.selected_chats_for_sending - set(chats_to_delete)
                self.selected_chats_info.setText(f'Выбрано чатов: {len(self.selected_chats_for_sending)}')
            else:
                QMessageBox.warning(self, 'Ошибка', 'Не удалось удалить чаты')

    def cleanup_unused_chats(self):
        """Очищает неиспользуемые чаты - выходит из тех, что не в списке рассылки"""
        if not self.is_authorized:
            QMessageBox.warning(self, 'Ошибка', 'Сначала авторизуйтесь!')
            return

        reply = QMessageBox.question(self, 'Подтверждение',
                                     'Вы уверены, что хотите выйти из всех чатов, не добавленных в список рассылки?',
                                     QMessageBox.Yes | QMessageBox.No)

        if reply != QMessageBox.Yes:
            return

        # Получаем ID чатов, которые нужно сохранить (все сохраненные чаты)
        saved_chats = ChatsManager.load_chats()
        chat_ids_to_keep = set(saved_chats.keys())

        self.cleanup_chats_btn.setEnabled(False)
        self.statusBar().showMessage('Начинаем очистку неиспользуемых чатов...')

        self.leave_chats_thread = LeaveChatsThread(chat_ids_to_keep)
        self.leave_chats_thread.progress.connect(self.on_leave_progress)
        self.leave_chats_thread.finished.connect(self.on_leave_finished)
        self.leave_chats_thread.error.connect(self.on_leave_error)
        self.leave_chats_thread.start()

    def on_leave_progress(self, message):
        self.statusBar().showMessage(message)

    def on_leave_finished(self, left_count):
        self.cleanup_chats_btn.setEnabled(True)
        self.statusBar().showMessage(f'Очистка завершена. Выход из {left_count} чатов')
        QMessageBox.information(self, 'Очистка завершена', f'Выход из {left_count} неиспользуемых чатов')

    def on_leave_error(self, error_message):
        self.cleanup_chats_btn.setEnabled(True)
        QMessageBox.critical(self, 'Ошибка очистки', error_message)

    def leave_chats_after_deletion(self, chat_ids):
        """Выходит из указанных чатов после их удаления из списка"""
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
            loop.run_until_complete(self._leave_chats(client, chat_ids))

        except Exception as e:
            print(f"Ошибка при выходе из чатов: {e}")
        finally:
            if loop and not loop.is_closed():
                loop.close()

    async def _leave_chats(self, client, chat_ids):
        """Асинхронный метод для выхода из чатов"""
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return

        try:
            chats = ChatsManager.load_chats()
            for chat_id in chat_ids:
                if chat_id in chats:
                    chat_data = chats[chat_id]
                    try:
                        entity = await client.get_entity(int(chat_id))
                        await client(LeaveChannelRequest(entity))
                        print(f"✅ Вышли из чата: {chat_data['title']}")
                    except Exception as e:
                        print(f"❌ Не удалось выйти из {chat_data['title']}: {str(e)}")
                    await asyncio.sleep(1)  # Задержка между выходами

            await client.disconnect()
        except Exception as e:
            await client.disconnect()
            raise e

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

    def update_stats(self):
        chats = ChatsManager.load_chats()
        total_chats = len(chats)
        today_sent = ChatsManager.get_today_sent_count()
        daily_limit = self.settings['daily_limit']

        self.stats_label.setText(f'Всего чатов: {total_chats} | Отправлено сегодня: {today_sent}/{daily_limit}')

    def show_settings(self):
        settings_dialog = SettingsDialog(self)
        if settings_dialog.exec_() == QDialog.Accepted:
            self.settings = SettingsManager.load_settings()
            self.update_stats()

    def send_to_selected(self):
        if not self.is_authorized:
            QMessageBox.warning(self, 'Ошибка', 'Сначала авторизуйтесь!')
            return

        if not self.selected_chats_for_sending:
            QMessageBox.warning(self, 'Ошибка', 'Сначала выберите чаты для отправки')
            return

        message = self.message_text.toPlainText().strip()
        if not message and not self.video_path:
            QMessageBox.warning(self, 'Ошибка', 'Введите сообщение или загрузите видео')
            return

        # Фильтруем чаты по возможности отправки видео
        if self.video_path:
            filtered_chats = []
            chats = ChatsManager.load_chats()
            for chat_id in self.selected_chats_for_sending:
                if chat_id in chats and chats[chat_id].get('can_video', False):
                    filtered_chats.append(chat_id)

            if not filtered_chats:
                QMessageBox.warning(self, 'Ошибка', 'Нет выбранных чатов, в которые можно отправлять видео')
                return
            chat_ids = filtered_chats
        else:
            chat_ids = list(self.selected_chats_for_sending)

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
            QMessageBox.information(self, 'Завершено', 'Рассылка завершена!')
            return

        chat_id = chat_ids[current_index]
        chat_title = ChatsManager.load_chats()[chat_id]['title']

        self.progress_label.setText(f'Отправка в {chat_title} ({current_index + 1}/{len(chat_ids)})')
        self.progress_bar.setValue(current_index)

        self.send_thread = SendToChatThread(chat_id, message, self.video_path)
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
        if self.auto_send_thread and self.auto_send_thread.isRunning():
            self.stop_sending()
        else:
            self.start_auto_send()

    def start_auto_send(self):
        if not self.is_authorized:
            QMessageBox.warning(self, 'Ошибка', 'Сначала авторизуйтесь!')
            return

        if not self.selected_chats_for_sending:
            QMessageBox.warning(self, 'Ошибка', 'Сначала выберите чаты для отправки')
            return

        message = self.message_text.toPlainText().strip()
        if not message and not self.video_path:
            QMessageBox.warning(self, 'Ошибка', 'Введите сообщение или загрузите видео')
            return

        # Фильтруем чаты по возможности отправки видео
        if self.video_path:
            filtered_chats = []
            chats = ChatsManager.load_chats()
            for chat_id in self.selected_chats_for_sending:
                if chat_id in chats and chats[chat_id].get('can_video', False):
                    filtered_chats.append(chat_id)

            if not filtered_chats:
                QMessageBox.warning(self, 'Ошибка', 'Нет выбранных чатов, в которые можно отправлять видео')
                return
            selected_chats = filtered_chats
        else:
            selected_chats = list(self.selected_chats_for_sending)

        self.auto_send_btn.setVisible(False)
        self.stop_btn.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)

        self.auto_send_thread = AutoSendThread(
            message,
            self.video_path,
            selected_chats,
            self.settings['min_delay'],
            self.settings['max_delay'],
            self.settings['daily_limit']
        )
        self.auto_send_thread.progress.connect(self.on_auto_send_progress)
        self.auto_send_thread.finished.connect(self.on_auto_send_finished)
        self.auto_send_thread.error.connect(self.on_auto_send_error)
        self.auto_send_thread.start()

    def stop_sending(self):
        if self.auto_send_thread and self.auto_send_thread.isRunning():
            self.auto_send_thread.stop_sending()
            self.auto_send_thread.wait()

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
    app.setApplicationName('Telegram Chat Manager')

    window = TelegramBotApp()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()