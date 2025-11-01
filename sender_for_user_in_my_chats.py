import sys
import asyncio
import os
import random
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError, ChatWriteForbiddenError
from telethon.tl.types import UserStatusOnline, UserStatusRecently, UserStatusOffline
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout,
                             QHBoxLayout, QWidget, QComboBox, QTextEdit,
                             QPushButton, QLabel, QMessageBox, QLineEdit,
                             QDialog, QProgressBar, QListWidget, QListWidgetItem, QCheckBox, QSpinBox, QSystemTrayIcon,)
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QFont, QIcon
import tempfile

API_ID = '21339848'
API_HASH = '3bc2385cae1af7eb7bc29302e69233a6'

SESSION_FILE = os.path.join(tempfile.gettempdir(), 'telegram_session')
USERS_FILE = 'users_chat.txt'
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
                        if ',' in line:
                            parts = line.split(',')
                            username = parts[0]
                            status = parts[1]
                            # Если есть время отправки, берем его
                            send_time = parts[2] if len(parts) > 2 else ''
                            users[username] = {'status': status, 'send_time': send_time}
            except Exception as e:
                print(f"Ошибка загрузки файла: {e}")
        return users

    @staticmethod
    def save_users(users):
        """Сохраняет пользователей в файл"""
        try:
            with open(USERS_FILE, 'w', encoding='utf-8') as f:
                for username, data in users.items():
                    status = data['status']
                    send_time = data.get('send_time', '')
                    f.write(f"{username},{status},{send_time}\n")
            return True
        except Exception as e:
            print(f"Ошибка сохранения файла: {e}")
            return False

    @staticmethod
    def add_users_from_chat(new_users):
        """Добавляет новых пользователей в файл"""
        existing_users = UserManager.load_users()

        for username in new_users:
            if username not in existing_users:
                existing_users[username] = {'status': 'не отправлено', 'send_time': ''}

        return UserManager.save_users(existing_users)

    @staticmethod
    def update_user_status(username, status, send_time=''):
        """Обновляет статус пользователя"""
        users = UserManager.load_users()
        if username in users:
            users[username]['status'] = status
            if send_time:
                users[username]['send_time'] = send_time
            return UserManager.save_users(users)
        return False

    @staticmethod
    def get_unsent_users():
        """Возвращает список пользователей со статусом 'не отправлено'"""
        users = UserManager.load_users()
        unsent_users = [username for username, data in users.items()
                        if username.startswith('@') and data['status'] == 'не отправлено']
        return unsent_users

    @staticmethod
    def get_today_sent_count():
        """Возвращает количество сообщений, отправленных сегодня"""
        users = UserManager.load_users()
        today = datetime.now().strftime('%d.%m.%Y')
        today_sent = 0

        for username, data in users.items():
            if data['status'] == 'отправлено' and data['send_time'].startswith(today):
                today_sent += 1

        return today_sent

    @staticmethod
    def get_users_with_send_time():
        """Возвращает пользователей с временем отправки"""
        users = UserManager.load_users()
        return users


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
                break  # Успешно, выходим из цикла

            except Exception as e:
                attempt += 1
                if attempt == max_attempts:
                    self.error.emit(str(e))
                else:
                    # Ждем перед повторной попыткой
                    import time
                    time.sleep(2)
            finally:
                if loop and not loop.is_closed():
                    loop.close()

    async def send_code(self, client):
        # Пытаемся подключиться с повторными попытками
        for attempt in range(3):
            try:
                await client.connect()
                if client.is_connected():
                    break
            except Exception:
                if attempt == 2:  # Последняя попытка
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
    # Добавляем сигнал успешной авторизации
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
            self.accept()  # Просто закрываем с Accept
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


class LoadChatsThread(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()

    def run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
            result = loop.run_until_complete(self.load_chats(client))
            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                loop.close()

    async def load_chats(self, client):
        await client.connect()
        if not client.is_connected():
            await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            raise Exception("Пользователь не авторизован")

        try:
            dialogs = await client.get_dialogs(limit=100)
            chats_info = []

            for dialog in dialogs:
                try:
                    if hasattr(dialog, 'entity') and dialog.entity:
                        chat_title = getattr(dialog, 'name', 'Без названия') or 'Без названия'

                        # ИСКЛЮЧАЕМ ЛИЧНЫЕ ЧАТЫ С ПОЛЬЗОВАТЕЛЯМИ И БОТАМИ
                        if dialog.is_user:
                            # Проверяем, является ли собеседник ботом
                            entity = dialog.entity
                            if hasattr(entity, 'bot') and entity.bot:
                                continue  # Пропускаем ботов
                            else:
                                continue  # Пропускаем личные чаты с пользователями

                        # ИСКЛЮЧАЕМ ЧАТЫ БЕЗ НАЗВАНИЯ
                        if not chat_title or chat_title == 'Без названия' or chat_title.strip() == '':
                            continue

                        # ЗАГРУЖАЕМ ТОЛЬКО ГРУППЫ И КАНАЛЫ
                        if dialog.is_group or dialog.is_channel:
                            try:
                                entity = dialog.entity
                                chat_id = getattr(entity, 'id', None)

                                if chat_id:
                                    chats_info.append((chat_title, chat_id, entity))

                            except Exception as e:
                                print(f"Ошибка при обработке чата {chat_title}: {e}")
                                continue

                except Exception as e:
                    print(f"Ошибка в диалоге: {e}")
                    continue

            # Сортируем чаты по названию для удобства
            chats_info.sort(key=lambda x: x[0].lower())

            return chats_info

        except Exception as e:
            await client.disconnect()
            raise e
        finally:
            try:
                await client.disconnect()
            except:
                pass


class SaveUsersThread(QThread):
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(int, int)
    error = pyqtSignal(str)

    def __init__(self, chat_entity):
        super().__init__()
        self.chat_entity = chat_entity

    def run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
            result = loop.run_until_complete(self.save_users(client))
            self.finished.emit(True, result)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                loop.close()

    async def save_users(self, client):
        await client.connect()
        if not client.is_connected():
            await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            raise Exception("Пользователь не авторизован")

        try:
            users = set()
            total_count = 0

            participants_count = 0
            try:
                if hasattr(self.chat_entity, 'participants_count'):
                    participants_count = self.chat_entity.participants_count
            except:
                pass

            self.progress.emit(0, participants_count or 100)

            # Собираем только пользователей с username (никнеймами)
            async for user in client.iter_participants(self.chat_entity, aggressive=True):
                total_count += 1
                self.progress.emit(total_count, participants_count or total_count + 50)

                if user.bot or user.deleted or user.is_self:
                    continue

                # СОХРАНЯЕМ ТОЛЬКО ЕСЛИ ЕСТЬ USERNAME (НИКНЕЙМ)
                if user.username:
                    username = f"@{user.username}"
                    users.add(username)

                if total_count % 50 == 0:
                    await asyncio.sleep(0.5)

            # Сохраняем пользователей
            if users:
                success = UserManager.add_users_from_chat(users)
                if success:
                    return f"Сохранено {len(users)} пользователей с никами в файл {USERS_FILE}"
                else:
                    return "Ошибка сохранения в файл"
            else:
                return "Не найдено пользователей с никами для сохранения"

        except Exception as e:
            await client.disconnect()
            raise e
        finally:
            try:
                await client.disconnect()
            except:
                pass


class SendPersonalMessageThread(QThread):
    finished = pyqtSignal(bool, str)
    error = pyqtSignal(str)

    def __init__(self, username, message, delay=2):
        super().__init__()
        self.username = username
        self.message = message
        self.delay = delay

    def run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
            result = loop.run_until_complete(self.send_personal_message(client))
            self.finished.emit(True, result)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                loop.close()

    async def send_personal_message(self, client):
        await client.connect()
        if not client.is_connected():
            await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            raise Exception("Пользователь не авторизован")

        try:
            # Добавляем задержку перед отправкой
            await asyncio.sleep(self.delay)

            # ТЕПЕРЬ РАБОТАЕМ ТОЛЬКО С USERNAME (НИКАМИ)
            if not self.username.startswith('@'):
                raise Exception("Можно отправлять только пользователям с никами (@username)")

            # Ищем пользователя по username
            user = await client.get_entity(self.username)

            # Отправляем сообщение
            await client.send_message(user, self.message)

            # Короткая задержка после отправки
            await asyncio.sleep(1)

            await client.disconnect()

            # Обновляем статус с временем отправки
            send_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
            UserManager.update_user_status(self.username, 'отправлено', send_time)

            return f"✅ Сообщение отправлено пользователю {self.username}"

        except FloodWaitError as e:
            wait_time = e.seconds
            await client.disconnect()
            raise Exception(f"⏳ Лимит Telegram! Подождите {wait_time} секунд")

        except Exception as e:
            await client.disconnect()
            raise Exception(f"❌ Ошибка: {str(e)}")


class SendMessageThread(QThread):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, chat_entity, message, mention_all=False, mention_online=False):
        super().__init__()
        self.chat_entity = chat_entity
        self.message = message
        self.mention_all = mention_all
        self.mention_online = mention_online

    def run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
            result = loop.run_until_complete(self.send_message(client))
            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                loop.close()

    async def send_message(self, client):
        await client.connect()
        if not client.is_connected():
            await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            raise Exception("Пользователь не авторизован")

        try:
            if self.mention_all:
                return await self.send_message_with_all_mention(client)
            elif self.mention_online:
                return await self.send_message_with_online_mentions(client)
            else:
                await client.send_message(self.chat_entity, self.message)
                return "✅ Сообщение отправлено!"

        except FloodWaitError as e:
            await client.disconnect()
            raise Exception(f"Превышен лимит отправки. Попробуйте через {e.seconds} секунд")
        except ChatWriteForbiddenError:
            await client.disconnect()
            raise Exception("Нет прав на отправку сообщений в этот чат")
        except Exception as e:
            await client.disconnect()
            raise e
        finally:
            try:
                await client.disconnect()
            except:
                pass

    async def send_message_with_all_mention(self, client):
        """Упоминание через @all с проверкой результата"""
        try:
            full_message = f"{self.message}\n\n@all"
            sent_message = await client.send_message(self.chat_entity, full_message)

            # Проверяем, сработало ли упоминание
            await asyncio.sleep(1)

            if hasattr(sent_message, 'entities') and sent_message.entities:
                for entity in sent_message.entities:
                    if hasattr(entity, 'mention') and entity.mention:
                        return "✅ Сообщение отправлено с УСПЕШНЫМ упоминанием @all (упоминание активно)"

            return "✅ Сообщение отправлено, но @all НЕ СРАБОТАЛ (отображается серым)"

        except Exception as e:
            await client.send_message(self.chat_entity, self.message)
            return f"✅ Сообщение отправлено (ошибка @all: {str(e)})"

    async def send_message_with_online_mentions(self, client):
        """Упоминание 40 случайных онлайн-участников"""
        try:
            online_users = []
            recently_online_users = []
            total_processed = 0

            self.progress.emit(0, 100)

            # Собираем онлайн и недавно активных пользователей
            async for user in client.iter_participants(self.chat_entity, aggressive=False):
                total_processed += 1
                self.progress.emit(total_processed, total_processed + 50)

                if user.bot or user.deleted or user.is_self:
                    continue

                # Проверяем статус онлайн
                if hasattr(user, 'status'):
                    # Онлайн сейчас
                    if isinstance(user.status, UserStatusOnline):
                        online_users.append(user)
                    # Был онлайн недавно (в течение последних 15 минут)
                    elif isinstance(user.status, UserStatusRecently):
                        recently_online_users.append(user)
                    # Был онлайн сегодня
                    elif hasattr(user.status, 'was_online'):
                        time_diff = datetime.now().replace(
                            tzinfo=user.status.was_online.tzinfo) - user.status.was_online
                        if time_diff < timedelta(hours=24):
                            recently_online_users.append(user)

                # Ограничиваем сбор для больших чатов
                if total_processed >= 500:
                    break

                # Задержка для избежания ограничений
                if total_processed % 50 == 0:
                    await asyncio.sleep(0.5)

            # Объединяем списки: сначала онлайн, потом недавно активные
            all_active_users = online_users + recently_online_users

            # Выбираем случайных пользователей (максимум 40)
            max_mentions = 40
            if len(all_active_users) > max_mentions:
                selected_users = random.sample(all_active_users, max_mentions)
            else:
                selected_users = all_active_users

            # Формируем упоминания
            mentions = []
            for user in selected_users:
                if user.username:
                    mentions.append(f"@{user.username}")
                else:
                    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                    if name:
                        mentions.append(f"[{name}](tg://user?id={user.id})")

            if mentions:
                mention_text = " ".join(mentions)
                full_message = f"{self.message}\n\n{mention_text}"

            else:
                full_message = f"{self.message}\n"

            await client.send_message(self.chat_entity, full_message)

            # Формируем отчет
            report = f"✅ Сообщение отправлено!\n"
            report += f"• Найдено онлайн: {len(online_users)}\n"
            report += f"• Недавно активных: {len(recently_online_users)}\n"
            report += f"• Упомянуто: {len(mentions)} участников"

            return report

        except Exception as e:
            await client.send_message(self.chat_entity, self.message)
            return f"✅ Сообщение отправлено (ошибка упоминаний: {str(e)})"


class AutoSendThread(QThread):
    progress = pyqtSignal(str, int, int)  # status, current, total
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, message, min_delay=3600, max_delay=5400, daily_limit=10):
        super().__init__()
        self.message = message
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.daily_limit = daily_limit
        self.is_running = True
        self.current_user_index = 0

        # Загружаем приветствия
        self.greetings = self.load_greetings()
        self.used_greetings_today = set()  # Приветствия, использованные сегодня

    def stop_sending(self):
        """Останавливает автоматическую отправку"""
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
        """Проверяет, находится ли текущее время в разрешенном интервале (11:00-21:00)"""
        now = datetime.now()
        current_hour = now.hour
        return 11 <= current_hour < 21

    def get_today_sent_count(self):
        """Получает количество отправленных сегодня сообщений"""
        return UserManager.get_today_sent_count()

    def can_send_today(self):
        """Проверяет, можно ли отправить еще сообщений сегодня"""
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
                # Проверяем время работы (11:00-21:00)
                if not self.is_working_time():
                    wait_until = datetime.now().replace(hour=11, minute=0, second=0, microsecond=0)
                    if datetime.now().hour >= 21:
                        wait_until += timedelta(days=1)

                    wait_seconds = (wait_until - datetime.now()).total_seconds()
                    self.progress.emit(
                        f"⏳ Вне времени работы (11:00-21:00). Ждем до {wait_until.strftime('%H:%M')}",
                        0, 1
                    )

                    # Ждем до начала рабочего времени
                    for sec in range(int(wait_seconds)):
                        if not self.is_running:
                            await client.disconnect()
                            return "⏹️ Автоматическая отправка остановлена"
                        await asyncio.sleep(1)
                    continue

                # Получаем список неотправленных пользователей
                unsent_users = UserManager.get_unsent_users()
                total_users = len(unsent_users)

                if total_users == 0:
                    await client.disconnect()
                    return "❌ Нет пользователей для отправки (все уже отправлены)"

                # Определяем сколько сообщений можно отправить сегодня
                today_sent = self.get_today_sent_count()
                remaining_limit = self.daily_limit - today_sent


                if remaining_limit <= 0:
                    # Лимит на сегодня исчерпан - ждем до следующего дня
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
                            return "⏹️ Автоматическая отправка остановлена"
                        await asyncio.sleep(1)
                    self.used_greetings_today.clear()
                    continue

                # Ограничиваем количество пользователей для отправки сегодняшним лимитом
                users_to_send_today = min(remaining_limit, total_users - self.current_user_index)

                if users_to_send_today <= 0:
                    # Нет пользователей для отправки сегодня (все отправлены или лимит достигнут)
                    tomorrow = datetime.now() + timedelta(days=1)
                    wait_until = tomorrow.replace(hour=11, minute=0, second=0, microsecond=0)
                    wait_seconds = (wait_until - datetime.now()).total_seconds()

                    self.progress.emit(
                        f"✅ На сегодня отправка завершена. Ждем до завтра 11:00",
                        0, 1
                    )

                    for sec in range(int(wait_seconds)):
                        if not self.is_running:
                            await client.disconnect()
                            return "⏹️ Автоматическая отправка остановлена"
                        await asyncio.sleep(1)
                    continue

                # Отправляем сообщения сегодняшним лимитом
                sent_today_count = 0
                user_found = False

                for i in range(self.current_user_index, self.current_user_index + users_to_send_today):
                    if not self.is_running:
                        await client.disconnect()
                        return "⏹️ Автоматическая отправка остановлена"

                    if i >= total_users:
                        break

                    username = unsent_users[i]

                    try:
                        # Случайная задержка от min_delay до max_delay между сообщениями
                        if sent_today_count > 0:  # Задержка только после первого сообщения
                            delay_seconds = random.randint(self.min_delay, self.max_delay)
                            delay_minutes = delay_seconds // 60
                            delay_secs = delay_seconds % 60

                            self.progress.emit(
                                f"⏰ Ожидание {delay_minutes} мин {delay_secs} сек перед отправкой {username}",
                                i, total_users
                            )

                            # Ожидание с проверкой остановки и времени работы
                            for sec in range(delay_seconds):
                                if not self.is_running:
                                    await client.disconnect()
                                    return "⏹️ Автоматическая отправка остановлена"

                                # Проверяем время работы каждую секунду
                                if not self.is_working_time():
                                    break

                                await asyncio.sleep(1)

                            if not self.is_running:
                                await client.disconnect()
                                return "⏹️ Автоматическая отправка остановлена"

                            # Проверяем время работы после задержки
                            if not self.is_working_time():
                                self.progress.emit(
                                    f"⏳ Время работы истекло (11:00-21:00). Продолжим завтра",
                                    i, total_users
                                )
                                break

                        # Отправка сообщения
                        self.progress.emit(
                            f"📨 Отправка сообщения {username} ({sent_today_count + 1}/{users_to_send_today})", i,
                            total_users)

                        # ДОБАВЛЯЕМ ПРИВЕТСТВИЕ ПЕРЕД СООБЩЕНИЕМ
                        greeting = self.get_random_greeting(self.used_greetings_today)
                        full_message = f"{greeting}\n\n{self.message}"

                        user = await client.get_entity(username)
                        await client.send_message(user, full_message)

                        # Обновляем статус с временем отправки
                        send_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
                        UserManager.update_user_status(username, 'отправлено', send_time)

                        user_found = True
                        sent_today_count += 1
                        self.current_user_index = i + 1

                        # Короткая пауза после отправки (2 секунды)
                        await asyncio.sleep(2)

                    except FloodWaitError as e:
                        wait_time = e.seconds
                        self.progress.emit(
                            f"⏳ Лимит! Ждем {wait_time} сек. Пропускаем {username}",
                            i, total_users
                        )
                        await asyncio.sleep(wait_time)
                        # Пробуем этого же пользователя снова в следующей итерации
                        continue

                    except Exception as e:
                        self.progress.emit(
                            f"❌ Ошибка с {username}: {str(e)}",
                            i, total_users
                        )
                        # Пропускаем проблемного пользователя и переходим к следующему
                        self.current_user_index = i + 1
                        await asyncio.sleep(10)
                        continue

                # После отправки всех запланированных на сегодня сообщений ждем до следующего дня
                if sent_today_count > 0:
                    tomorrow = datetime.now() + timedelta(days=1)
                    wait_until = tomorrow.replace(hour=11, minute=0, second=0, microsecond=0)
                    wait_seconds = (wait_until - datetime.now()).total_seconds()

                    self.progress.emit(
                        f"✅ Отправлено {sent_today_count} сообщений сегодня. Ждем до завтра 11:00",
                        0, 1
                    )

                    for sec in range(int(wait_seconds)):
                        if not self.is_running:
                            await client.disconnect()
                            return "⏹️ Автоматическая отправка остановлена"
                        await asyncio.sleep(1)

                # Если ни одного пользователя не удалось отправить, ждем 10 секунд и пробуем снова
                elif not user_found:
                    self.progress.emit(
                        "🔄 Не удалось отправить ни одному пользователю. Повтор через 10 сек",
                        0, 1
                    )
                    for sec in range(10):
                        if not self.is_running:
                            await client.disconnect()
                            return "⏹️ Автоматическая отправка остановлена"
                        await asyncio.sleep(1)

            await client.disconnect()
            return "⏹️ Автоматическая отправка остановлена"

        except Exception as e:
            await client.disconnect()
            raise e

    def load_greetings(self):
        """Загружает приветствия из файла"""
        greetings = []
        try:
            with open('welcome_preset.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):  # Пропускаем пустые строки и комментарии
                        greetings.append(line)
        except Exception as e:
            print(f"Ошибка загрузки приветствий: {e}")
            # Запасные приветствия на случай ошибки
            greetings = [
                "Приветствую Вас, уважаемый друг!😊",
                "Доброго времени суток!😊",
                "Здравствуйте!😊"
            ]
        return greetings

    def get_random_greeting(self, used_greetings):
        """Возвращает случайное приветствие, которое еще не использовалось сегодня"""
        available_greetings = [g for g in self.greetings if g not in used_greetings]

        if not available_greetings:
            # Если все приветствия использованы, сбрасываем список
            used_greetings.clear()
            available_greetings = self.greetings.copy()

        if available_greetings:
            greeting = random.choice(available_greetings)
            used_greetings.add(greeting)
            return greeting
        else:
            return "Здравствуйте!😊"  # Запасное приветствие


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = SettingsManager.load_settings()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Настройки')
        self.setFixedSize(400, 300)
        layout = QVBoxLayout()

        # Лимит сообщений в день
        layout.addWidget(QLabel('Лимит сообщений в день:'))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 100)
        self.limit_spin.setValue(self.settings['daily_limit'])
        layout.addWidget(self.limit_spin)

        # Интервалы времени
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
        self.settings['daily_limit'] = self.limit_spin.value()
        self.settings['min_delay'] = self.min_delay_spin.value()
        self.settings['max_delay'] = self.max_delay_spin.value()

        if SettingsManager.save_settings(self.settings):
            QMessageBox.information(self, 'Успех', 'Настройки сохранены!')
            self.accept()
        else:
            QMessageBox.warning(self, 'Ошибка', 'Не удалось сохранить настройки')


class TelegramBotApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = SettingsManager.load_settings()
        self.auto_send_thread = None
        self.is_authorized = False  # Добавляем флаг авторизации
        self.init_ui()

        # Настройка трей-иконки
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon('icon.ico'))

        self.check_authorization()  # Проверяем авторизацию при запуске

    def init_ui(self):
        self.setWindowTitle('Менеджер рассылки в Telegram ')
        self.setFixedSize(800, 800)

        central_widget = QWidget()
        layout = QVBoxLayout()

        # Кнопка авторизации
        self.auth_btn = QPushButton('🔐 Авторизация')
        self.auth_btn.setStyleSheet('background-color: #FF9800; color: white; font-weight: bold; padding: 10px;')
        self.auth_btn.clicked.connect(self.auth_button_clicked)
        layout.addWidget(self.auth_btn)

        # Выбор чата
        layout.addWidget(QLabel('Выберите чат:'))
        self.chat_combo = QComboBox()
        layout.addWidget(self.chat_combo)

        # Кнопка загрузки чатов
        self.load_chats_btn = QPushButton('🔄 Загрузить чаты')
        self.load_chats_btn.setStyleSheet('background-color: #2196F3; color: white; font-weight: bold; padding: 8px;')
        self.load_chats_btn.clicked.connect(self.load_chats)
        layout.addWidget(self.load_chats_btn)

        # Кнопка сохранения пользователей
        self.save_users_btn = QPushButton('💾 Сохранить пользователей чата')
        self.save_users_btn.setStyleSheet('background-color: #9C27B0; color: white; font-weight: bold; padding: 8px;')
        self.save_users_btn.clicked.connect(self.save_users)
        layout.addWidget(self.save_users_btn)

        # Поле сообщения
        layout.addWidget(QLabel('Сообщение:'))
        self.message_text = QTextEdit()
        self.message_text.setMinimumHeight(150)
        self.message_text.setPlaceholderText('Введите текст сообщения...')
        layout.addWidget(self.message_text)

        # Чекбоксы упоминаний
        mention_layout = QHBoxLayout()
        self.mention_all_check = QCheckBox('Выделить всех')
        self.mention_online_check = QCheckBox('Выделить 40 случайных в сети')
        mention_layout.addWidget(self.mention_all_check)
        mention_layout.addWidget(self.mention_online_check)
        layout.addLayout(mention_layout)

        # Кнопка отправки сообщения
        self.send_btn = QPushButton('📤 Отправить сообщение в чат')
        self.send_btn.setStyleSheet('background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;')
        self.send_btn.clicked.connect(self.send_message)
        layout.addWidget(self.send_btn)

        # Кнопка отправки личного сообщения
        self.send_personal_btn = QPushButton('👤 Отправить личное сообщение')
        self.send_personal_btn.setStyleSheet(
            'background-color: #607D8B; color: white; font-weight: bold; padding: 8px;')
        self.send_personal_btn.clicked.connect(self.send_personal_message_dialog)
        layout.addWidget(self.send_personal_btn)

        # Кнопка автоматической рассылки
        auto_send_layout = QHBoxLayout()

        self.start_auto_send_btn = QPushButton('🚀 Начать авто-рассылку')
        self.start_auto_send_btn.setStyleSheet(
            'background-color: #E91E63; color: white; font-weight: bold; padding: 8px;')
        self.start_auto_send_btn.clicked.connect(self.start_auto_send)
        auto_send_layout.addWidget(self.start_auto_send_btn)

        self.stop_auto_send_btn = QPushButton('⏹️ Остановить авто-рассылку')
        self.stop_auto_send_btn.setStyleSheet(
            'background-color: #FF5722; color: white; font-weight: bold; padding: 8px;')
        self.stop_auto_send_btn.clicked.connect(self.stop_auto_send)
        self.stop_auto_send_btn.setEnabled(False)
        auto_send_layout.addWidget(self.stop_auto_send_btn)

        layout.addLayout(auto_send_layout)

        # Кнопка настроек
        self.settings_btn = QPushButton('⚙️ Настройки')
        self.settings_btn.setStyleSheet('background-color: #795548; color: white; font-weight: bold; padding: 8px;')
        self.settings_btn.clicked.connect(self.show_settings)
        layout.addWidget(self.settings_btn)

        # Прогресс бар
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        # Статус
        self.status_label = QLabel('Готов к работе')
        self.status_label.setStyleSheet('color: green;')
        layout.addWidget(self.status_label)

        # Список пользователей
        layout.addWidget(QLabel('Список пользователей:'))
        self.users_list = QListWidget()
        layout.addWidget(self.users_list)

        # Кнопка обновления списка пользователей
        self.refresh_users_btn = QPushButton('🔄 Обновить список')
        self.refresh_users_btn.setStyleSheet(
            'background-color: #009688; color: white; font-weight: bold; padding: 6px;')
        self.refresh_users_btn.clicked.connect(self.refresh_users_list)
        layout.addWidget(self.refresh_users_btn)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Таймер для обновления статуса
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(5000)

        self.update_status()

    def check_authorization(self):
        """Проверяет авторизацию при запуске приложения"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

            # Быстрая проверка подключения
            result = loop.run_until_complete(self.check_auth_status(client))
            self.is_authorized = result
            self.update_auth_button()

        except Exception:
            self.is_authorized = False
            self.update_auth_button()
        finally:
            if loop and not loop.is_closed():
                loop.close()

    def update_auth_button(self):
        """Обновляет текст и стиль кнопки авторизации"""
        if self.is_authorized:
            self.auth_btn.setText('🚪 Выйти из учётной записи')
            self.auth_btn.setStyleSheet('background-color: #f44336; color: white; font-weight: bold; padding: 10px;')
        else:
            self.auth_btn.setText('🔐 Авторизация')
            self.auth_btn.setStyleSheet('background-color: #FF9800; color: white; font-weight: bold; padding: 10px;')

    def logout(self):
        """Выход из учётной записи"""
        reply = QMessageBox.question(self, 'Подтверждение',
                                     'Вы уверены, что хотите выйти из учётной записи?',
                                     QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                # Удаляем файл сессии
                if os.path.exists(SESSION_FILE):
                    os.remove(SESSION_FILE)
                if os.path.exists(SESSION_FILE + '.session'):
                    os.remove(SESSION_FILE + '.session')

                self.is_authorized = False
                self.update_auth_button()
                self.status_label.setText('Вы вышли из учётной записи')
                self.status_label.setStyleSheet('color: blue;')

                QMessageBox.information(self, 'Успех', 'Вы успешно вышли из учётной записи')

            except Exception as e:
                QMessageBox.warning(self, 'Ошибка', f'Ошибка при выходе: {str(e)}')

    def show_auth_dialog(self):
        """Показывает диалог авторизации"""
        dialog = AuthDialog(self)
        # Используем прямой вызов вместо сигнала
        if dialog.exec_() == QDialog.Accepted:
            self.is_authorized = True
            self.update_auth_button()
            self.status_label.setText('Авторизация успешна!')
            self.status_label.setStyleSheet('color: green;')
            QMessageBox.information(self, 'Успех', 'Авторизация прошла успешно!')

    async def check_auth_status(self, client):
        """Проверяет статус авторизации"""
        try:
            await client.connect()
            if not client.is_connected():
                return False

            authorized = await client.is_user_authorized()
            await client.disconnect()
            return authorized
        except:
            return False

    def auth_button_clicked(self):
        """Обработчик клика по кнопке авторизации/выхода"""
        if self.is_authorized:
            self.logout()
        else:
            self.show_auth_dialog()

    # Остальные методы остаются без изменений...
    def load_chats(self):
        self.status_label.setText('Загрузка чатов...')
        self.load_chats_btn.setEnabled(False)

        self.load_chats_thread = LoadChatsThread()
        self.load_chats_thread.finished.connect(self.on_chats_loaded)
        self.load_chats_thread.error.connect(self.on_load_chats_error)
        self.load_chats_thread.start()

    def on_chats_loaded(self, chats):
        self.chat_combo.clear()
        for chat_title, chat_id, entity in chats:
            self.chat_combo.addItem(chat_title, (chat_id, entity))

        self.load_chats_btn.setEnabled(True)
        self.status_label.setText(f'Загружено {len(chats)} чатов')
        self.status_label.setStyleSheet('color: green;')

    def on_load_chats_error(self, error_message):
        self.load_chats_btn.setEnabled(True)
        self.status_label.setText(f'Ошибка загрузки чатов: {error_message}')
        self.status_label.setStyleSheet('color: red;')
        QMessageBox.critical(self, 'Ошибка', f'Не удалось загрузить чаты: {error_message}')

    def save_users(self):
        if self.chat_combo.currentIndex() == -1:
            QMessageBox.warning(self, 'Ошибка', 'Выберите чат сначала')
            return

        chat_data = self.chat_combo.currentData()
        if not chat_data:
            QMessageBox.warning(self, 'Ошибка', 'Неверные данные чата')
            return

        chat_id, chat_entity = chat_data

        self.status_label.setText('Сохранение пользователей...')
        self.save_users_btn.setEnabled(False)

        self.save_users_thread = SaveUsersThread(chat_entity)
        self.save_users_thread.finished.connect(self.on_users_saved)
        self.save_users_thread.progress.connect(self.on_save_users_progress)
        self.save_users_thread.error.connect(self.on_save_users_error)
        self.save_users_thread.start()

    def on_save_users_progress(self, current, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(f'Обработано {current} из {total} пользователей')

    def on_users_saved(self, success, message):
        self.save_users_btn.setEnabled(True)
        self.status_label.setText(message)
        self.status_label.setStyleSheet('color: green;')
        self.refresh_users_list()
        QMessageBox.information(self, 'Успех', message)

    def on_save_users_error(self, error_message):
        self.save_users_btn.setEnabled(True)
        self.status_label.setText(f'Ошибка сохранения: {error_message}')
        self.status_label.setStyleSheet('color: red;')
        QMessageBox.critical(self, 'Ошибка', f'Не удалось сохранить пользователей: {error_message}')

    def send_message(self):
        if self.chat_combo.currentIndex() == -1:
            QMessageBox.warning(self, 'Ошибка', 'Выберите чат сначала')
            return

        message = self.message_text.toPlainText().strip()
        if not message:
            QMessageBox.warning(self, 'Ошибка', 'Введите текст сообщения')
            return

        chat_data = self.chat_combo.currentData()
        if not chat_data:
            QMessageBox.warning(self, 'Ошибка', 'Неверные данные чата')
            return

        chat_id, chat_entity = chat_data

        self.status_label.setText('Отправка сообщения...')
        self.send_btn.setEnabled(False)

        self.send_message_thread = SendMessageThread(
            chat_entity,
            message,
            self.mention_all_check.isChecked(),
            self.mention_online_check.isChecked()
        )
        self.send_message_thread.finished.connect(self.on_message_sent)
        self.send_message_thread.progress.connect(self.on_send_message_progress)
        self.send_message_thread.error.connect(self.on_send_message_error)
        self.send_message_thread.start()

    def on_send_message_progress(self, current, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def on_message_sent(self, message):
        self.send_btn.setEnabled(True)
        self.status_label.setText(message)
        self.status_label.setStyleSheet('color: green;')
        QMessageBox.information(self, 'Успех', message)

    def on_send_message_error(self, error_message):
        self.send_btn.setEnabled(True)
        self.status_label.setText(f'Ошибка отправки: {error_message}')
        self.status_label.setStyleSheet('color: red;')
        QMessageBox.critical(self, 'Ошибка', f'Не удалось отправить сообщение: {error_message}')

    def send_personal_message_dialog(self):
        users = UserManager.get_unsent_users()
        if not users:
            QMessageBox.information(self, 'Информация', 'Нет пользователей для отправки')
            return

        message = self.message_text.toPlainText().strip()
        if not message:
            QMessageBox.warning(self, 'Ошибка', 'Введите текст сообщения')
            return

        # Диалог выбора пользователя
        dialog = QDialog(self)
        dialog.setWindowTitle('Выбор пользователя')
        dialog.setFixedSize(300, 200)
        layout = QVBoxLayout()

        layout.addWidget(QLabel('Выберите пользователя:'))
        user_combo = QComboBox()
        user_combo.addItems(users)
        layout.addWidget(user_combo)

        button_layout = QHBoxLayout()
        send_btn = QPushButton('Отправить')
        send_btn.setStyleSheet('background-color: #4CAF50; color: white;')
        send_btn.clicked.connect(lambda: self.send_personal_message(user_combo.currentText(), message, dialog))
        button_layout.addWidget(send_btn)

        cancel_btn = QPushButton('Отмена')
        cancel_btn.setStyleSheet('background-color: #f44336; color: white;')
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec_()

    def send_personal_message(self, username, message, dialog):
        dialog.accept()

        self.status_label.setText(f'Отправка сообщения {username}...')
        self.send_personal_btn.setEnabled(False)

        self.send_personal_thread = SendPersonalMessageThread(username, message)
        self.send_personal_thread.finished.connect(self.on_personal_message_sent)
        self.send_personal_thread.error.connect(self.on_personal_message_error)
        self.send_personal_thread.start()

    def on_personal_message_sent(self, success, message):
        self.send_personal_btn.setEnabled(True)
        self.status_label.setText(message)
        self.status_label.setStyleSheet('color: green;')
        self.refresh_users_list()
        QMessageBox.information(self, 'Успех', message)

    def on_personal_message_error(self, error_message):
        self.send_personal_btn.setEnabled(True)
        self.status_label.setText(f'Ошибка отправки: {error_message}')
        self.status_label.setStyleSheet('color: red;')
        QMessageBox.critical(self, 'Ошибка', f'Не удалось отправить сообщение: {error_message}')

    def start_auto_send(self):
        message = self.message_text.toPlainText().strip()
        if not message:
            QMessageBox.warning(self, 'Ошибка', 'Введите текст сообщения для авто-рассылки')
            return

        self.status_label.setText('Запуск авто-рассылки...')
        self.start_auto_send_btn.setEnabled(False)
        self.stop_auto_send_btn.setEnabled(True)

        self.auto_send_thread = AutoSendThread(
            message,
            self.settings['min_delay'],
            self.settings['max_delay'],
            self.settings['daily_limit']
        )
        self.auto_send_thread.progress.connect(self.on_auto_send_progress)
        self.auto_send_thread.finished.connect(self.on_auto_send_finished)
        self.auto_send_thread.error.connect(self.on_auto_send_error)
        self.auto_send_thread.start()

    def stop_auto_send(self):
        if self.auto_send_thread and self.auto_send_thread.isRunning():
            self.auto_send_thread.stop_sending()
            self.status_label.setText('Остановка авто-рассылки...')
            self.stop_auto_send_btn.setEnabled(False)

    def on_auto_send_progress(self, status, current, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(status)

    def on_auto_send_finished(self, message):
        self.start_auto_send_btn.setEnabled(True)
        self.stop_auto_send_btn.setEnabled(False)
        self.status_label.setText(message)
        self.status_label.setStyleSheet('color: blue;')
        QMessageBox.information(self, 'Авто-рассылка', message)

    def on_auto_send_error(self, error_message):
        self.start_auto_send_btn.setEnabled(True)
        self.stop_auto_send_btn.setEnabled(False)
        self.status_label.setText(f'Ошибка авто-рассылки: {error_message}')
        self.status_label.setStyleSheet('color: red;')
        QMessageBox.critical(self, 'Ошибка', f'Ошибка авто-рассылки: {error_message}')

    def show_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.settings = SettingsManager.load_settings()
            self.update_status()

    def refresh_users_list(self):
        self.users_list.clear()
        users = UserManager.load_users()

        for username, data in users.items():
            status = data['status']
            send_time = data.get('send_time', '')
            item_text = f"{username} - {status}"
            if send_time:
                item_text += f" ({send_time})"

            item = QListWidgetItem(item_text)

            # Разные цвета для статусов
            if status == 'отправлено':
                item.setForeground(Qt.darkGreen)
            elif status == 'не отправлено':
                item.setForeground(Qt.darkBlue)
            else:
                item.setForeground(Qt.darkRed)

            self.users_list.addItem(item)

    def update_status(self):
        total_users = len(UserManager.load_users())
        unsent_users = len(UserManager.get_unsent_users())
        today_sent = UserManager.get_today_sent_count()
        daily_limit = self.settings['daily_limit']

        status_text = (f"Всего пользователей: {total_users} | "
                       f"Не отправлено: {unsent_users} | "
                       f"Отправлено сегодня: {today_sent}/{daily_limit}")

        self.status_label.setText(status_text)

        if today_sent >= daily_limit:
            self.status_label.setStyleSheet('color: orange; font-weight: bold;')
        else:
            self.status_label.setStyleSheet('color: green;')

    def closeEvent(self, event):
        """Останавливаем все потоки при закрытии приложения"""
        if self.auto_send_thread and self.auto_send_thread.isRunning():
            self.auto_send_thread.stop_sending()
            self.auto_send_thread.wait(2000)

        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Устанавливаем стиль приложения
    app.setStyle('Fusion')

    window = TelegramBotApp()
    window.show()

    sys.exit(app.exec_())