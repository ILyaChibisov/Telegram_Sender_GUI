import sys
import asyncio
import os
import random
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError, ChatWriteForbiddenError, ChannelPrivateError, \
    InviteRequestSentError, UserAlreadyParticipantError
from telethon.tl.functions.messages import GetDialogsRequest, ImportChatInviteRequest, GetDiscussionMessageRequest, \
    SearchRequest, GetDialogFiltersRequest
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest, GetFullChannelRequest, \
    GetChannelsRequest
from telethon.tl.types import InputPeerEmpty, Channel, ChatForbidden, Message, Chat, User, InputMessagesFilterEmpty, \
    DialogFolder
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout,
                             QHBoxLayout, QWidget, QComboBox, QTextEdit,
                             QPushButton, QLabel, QMessageBox, QLineEdit,
                             QDialog, QProgressBar, QListWidget, QListWidgetItem, QCheckBox, QSpinBox,
                             QSystemTrayIcon, QGroupBox, QScrollArea, QFileDialog, QSplitter)
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QFont, QIcon
import tempfile
import re
import json

API_ID = '21339848'
API_HASH = '3bc2385cae1af7eb7bc29302e69233a6'

SESSION_FILE = os.path.join(tempfile.gettempdir(), 'telegram_session')
COMMENTS_FILE = 'comments_chats_list.txt'
SETTINGS_FILE = 'comments_settings.txt'
FOLDERS_FILE = 'telegram_folders.json'


def clean_text(text):
    """Очищает текст от проблемных символов, но сохраняет смайлы/эмодзи"""
    if not text:
        return text

    # Убираем нулевые символы и другие непечатаемые символы, кроме эмодзи
    # Сохраняем эмодзи (символы из диапазонов эмодзи)
    cleaned = []
    for char in text:
        code = ord(char)
        # Сохраняем:
        # - обычные печатные символы (32-126)
        # - кириллицу (1040-1103 и 1025, 1105)
        # - эмодзи (диапазоны 0x1F600-0x1F64F, 0x1F300-0x1F5FF, 0x1F680-0x1F6FF, 0x1F700-0x1F77F,
        #           0x1F780-0x1F7FF, 0x1F800-0x1F8FF, 0x1F900-0x1F9FF, 0x1FA00-0x1FA6F,
        #           0x1FA70-0x1FAFF, 0x02700-0x027BF, 0x1F1E6-0x1F1FF и т.д.)
        if (32 <= code <= 126 or  # ASCII печатные символы
                1040 <= code <= 1103 or  # Кириллица
                code in [1025, 1105] or  # Ё/ё
                0x1F600 <= code <= 0x1F64F or  # Эмодзи лица
                0x1F300 <= code <= 0x1F5FF or  # Символы и пиктограммы
                0x1F680 <= code <= 0x1F6FF or  # Транспорт и карты
                0x1F700 <= code <= 0x1F77F or  # Астрономические
                0x1F780 <= code <= 0x1F7FF or  # Геометрические
                0x1F800 <= code <= 0x1F8FF or  # Дополнительные стрелки
                0x1F900 <= code <= 0x1F9FF or  # Дополнительные символы
                0x1FA00 <= code <= 0x1FA6F or  # Шахматы
                0x1FA70 <= code <= 0x1FAFF or  # Дополнительные символы
                0x02700 <= code <= 0x027BF or  # Символы Dingbat
                0x1F1E6 <= code <= 0x1F1FF):  # Флаги
            cleaned.append(char)
        elif char == '\n' or char == '\r' or char == '\t':  # Сохраняем переносы строк и табуляцию
            cleaned.append(char)
        elif code < 32:  # Удаляем непечатаемые управляющие символы
            continue
        else:
            # Для остальных символов пробуем заменить на похожие или оставить
            # Многие смайлы из Windows (Wingdings и т.д.) могут быть здесь
            cleaned.append(char)

    result = ''.join(cleaned)

    # Убираем множественные пробелы
    result = re.sub(r'\s+', ' ', result).strip()

    return result


def encode_text_for_saving(text):
    """Кодирует текст для сохранения в файл"""
    if not text:
        return ""
    # Заменяем запятые на специальный символ, чтобы не путать с разделителями CSV
    text = text.replace(',', '‚')  # Используем одинарную нижнюю кавычку
    text = text.replace('\n', '↵')  # Заменяем переносы строк
    return text


def decode_text_from_saved(text):
    """Декодирует текст из сохраненного формата"""
    if not text:
        return ""
    text = text.replace('‚', ',')  # Возвращаем запятые
    text = text.replace('↵', '\n')  # Возвращаем переносы строк
    return text


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


class FoldersManager:
    @staticmethod
    def load_folders():
        """Загружает папки из файла"""
        folders = {}
        if os.path.exists(FOLDERS_FILE):
            try:
                with open(FOLDERS_FILE, 'r', encoding='utf-8') as f:
                    folders = json.load(f)
            except Exception as e:
                print(f"Ошибка загрузки папок: {e}")
        return folders

    @staticmethod
    def save_folders(folders):
        """Сохраняет папки в файл"""
        try:
            with open(FOLDERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(folders, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Ошибка сохранения папок: {e}")
            return False

    @staticmethod
    def get_folder_names():
        """Возвращает список названий папок"""
        folders = FoldersManager.load_folders()
        return list(folders.keys())


class LoadFoldersThread(QThread):
    finished = pyqtSignal(dict)
    progress = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, phone=None):
        super().__init__()
        self.client = None
        self.phone = phone
        self.session_file = f"{SESSION_FILE}_{phone.replace('+', '')}" if phone else SESSION_FILE

    def run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            self.client = TelegramClient(self.session_file, API_ID, API_HASH)
            result = loop.run_until_complete(self.load_telegram_folders())
            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                loop.close()

    async def load_telegram_folders(self):
        """Загружает реальные папки из Telegram"""
        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                await self.client.disconnect()
                raise Exception("Пользователь не авторизован")

            self.progress.emit("📁 Загружаем папки из Telegram...")

            # Получаем все фильтры (папки)
            folders = {}

            try:
                # Получаем фильтры (папки)
                filters = await self.client(GetDialogFiltersRequest())

                for i, filter_obj in enumerate(filters):
                    try:
                        if hasattr(filter_obj, 'title') and filter_obj.title:
                            folder_title = clean_text(filter_obj.title)  # Очищаем название папки

                            # Собираем ID чатов из фильтра
                            chat_ids = []

                            # Получаем включенные чаты
                            if hasattr(filter_obj, 'include_peers'):
                                for peer in filter_obj.include_peers:
                                    if hasattr(peer, 'channel_id'):
                                        chat_ids.append(str(peer.channel_id))
                                    elif hasattr(peer, 'chat_id'):
                                        chat_ids.append(str(peer.chat_id))
                                    elif hasattr(peer, 'user_id'):
                                        # Пропускаем пользователей
                                        continue

                            # Также проверяем pinned_peers
                            if hasattr(filter_obj, 'pinned_peers'):
                                for peer in filter_obj.pinned_peers:
                                    if hasattr(peer, 'channel_id'):
                                        chat_id = str(peer.channel_id)
                                        if chat_id not in chat_ids:
                                            chat_ids.append(chat_id)
                                    elif hasattr(peer, 'chat_id'):
                                        chat_id = str(peer.chat_id)
                                        if chat_id not in chat_ids:
                                            chat_ids.append(chat_id)

                            if chat_ids:
                                folders[folder_title] = chat_ids
                                self.progress.emit(f"📂 Найдена папка: '{folder_title}' с {len(chat_ids)} чатами")
                            else:
                                folders[folder_title] = []
                                self.progress.emit(f"📂 Найдена пустая папка: '{folder_title}'")
                    except Exception as e:
                        self.progress.emit(f"⚠️ Ошибка обработки папки: {str(e)}")
                        continue

            except Exception as e:
                self.progress.emit(f"⚠️ Ошибка получения папок: {str(e)}")

            # Если папок нет, создаем "Все диалоги"
            if not folders:
                self.progress.emit("ℹ️ Папки не найдены. Создайте папки в Telegram и добавьте в них чаты.")

                # Получаем все группы и каналы для папки "Все диалоги"
                dialogs = await self.client.get_dialogs(limit=100)
                all_chats = []

                for dialog in dialogs:
                    if hasattr(dialog, 'entity') and hasattr(dialog.entity, 'id'):
                        if isinstance(dialog.entity, Channel) or isinstance(dialog.entity, Chat):
                            chat_id = str(dialog.entity.id)
                            all_chats.append(chat_id)

                if all_chats:
                    folders["Все диалоги"] = all_chats
                    self.progress.emit(f"✅ Создана папка 'Все диалоги' с {len(all_chats)} чатами")
            else:
                # Добавляем "Все диалоги" как отдельную папку
                dialogs = await self.client.get_dialogs(limit=100)
                all_chats = []

                for dialog in dialogs:
                    if hasattr(dialog, 'entity') and hasattr(dialog.entity, 'id'):
                        if isinstance(dialog.entity, Channel) or isinstance(dialog.entity, Chat):
                            chat_id = str(dialog.entity.id)
                            all_chats.append(chat_id)

                if all_chats:
                    folders["Все диалоги"] = all_chats
                    self.progress.emit(f"✅ Добавлена папка 'Все диалоги' с {len(all_chats)} чатами")

            # Сохраняем найденные папки
            FoldersManager.save_folders(folders)

            await self.client.disconnect()
            self.progress.emit(f"✅ Загружено папок: {len(folders)}")
            return folders

        except Exception as e:
            try:
                await self.client.disconnect()
            except:
                pass
            raise e


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
                                chat_title = decode_text_from_saved(parts[1]) if len(parts) > 1 else ''
                                chat_type = parts[2] if len(parts) > 2 else ''
                                access_type = parts[3] if len(parts) > 3 else ''
                                can_comment = parts[4] == 'True' if len(parts) > 4 else False
                                can_video = parts[5] == 'True' if len(parts) > 5 else False
                                last_post_id = parts[6] if len(parts) > 6 else '0'
                                last_post_date = parts[7] if len(parts) > 7 else ''
                                status = parts[8] if len(parts) > 8 else 'не отправлено'
                                send_time = parts[9] if len(parts) > 9 else ''
                                username = parts[10] if len(parts) > 10 else ''

                                chats[chat_id] = {
                                    'title': clean_text(chat_title),
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
                    title = encode_text_for_saving(clean_text(data['title']))
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
        self.session_file = f"{SESSION_FILE}_{phone.replace('+', '')}"

    def run(self):
        loop = None
        max_attempts = 3
        attempt = 0

        while attempt < max_attempts:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                client = TelegramClient(self.session_file, API_ID, API_HASH)
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
        self.session_file = f"{SESSION_FILE}_{phone.replace('+', '')}"

    def run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            client = TelegramClient(self.session_file, API_ID, API_HASH)
            result = loop.run_until_complete(self.sign_in(client))
            self.finished.emit(True, result)

        except SessionPasswordNeededError:
            # Обработка необходимости пароля
            self.need_password.emit()
        except Exception as e:
            error_msg = str(e)
            if 'two-step verification' in error_msg.lower() or 'two factor' in error_msg.lower():
                self.need_password.emit()
            else:
                self.error.emit(error_msg)
        finally:
            if loop and not loop.is_closed():
                loop.close()

    async def sign_in(self, client):
        await client.connect()
        if not client.is_connected():
            await client.connect()

        try:
            if self.password is None:
                # Без пароля
                await client.sign_in(
                    phone=self.phone,
                    code=self.code,
                    phone_code_hash=self.phone_code_hash
                )
            else:
                # С паролем - сначала код, потом пароль
                await client.sign_in(
                    phone=self.phone,
                    code=self.code,
                    phone_code_hash=self.phone_code_hash
                )

                # Если требуется пароль, Telethon сам выбросит SessionPasswordNeededError
                # и мы попадем в нужный обработчик

            if await client.is_user_authorized():
                await client.disconnect()
                return "Авторизация успешна!"
            else:
                await client.disconnect()
                return "Ошибка авторизации"

        except SessionPasswordNeededError:
            # Если требуется пароль, вводим его
            if self.password:
                await client.sign_in(password=self.password)
                if await client.is_user_authorized():
                    await client.disconnect()
                    return "Авторизация успешна (с паролем 2FA)!"
                else:
                    await client.disconnect()
                    raise Exception("Неверный пароль 2FA")
            else:
                # Если пароль не был передан, пробрасываем исключение выше
                raise
        except Exception as e:
            await client.disconnect()
            raise e


class AuthDialog(QDialog):
    authorization_success = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.phone_code_hash = None
        self.phone = None
        self.password_entered = False
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Авторизация в Telegram')
        self.setFixedSize(400, 450)
        layout = QVBoxLayout()

        self.stacked_widget = QWidget()
        self.stacked_layout = QVBoxLayout()

        # Шаг 1: Ввод телефона
        self.phone_widget = QWidget()
        phone_layout = QVBoxLayout()
        phone_layout.addWidget(QLabel('Введите номер телефона (с кодом страны):'))

        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText('+79991234567')
        phone_layout.addWidget(self.phone_edit)

        self.send_code_btn = QPushButton('Отправить код')
        self.send_code_btn.setStyleSheet('background-color: #2196F3; color: white; font-weight: bold; padding: 10px;')
        self.send_code_btn.clicked.connect(self.send_code)
        phone_layout.addWidget(self.send_code_btn)

        phone_layout.addStretch()
        self.phone_widget.setLayout(phone_layout)

        # Шаг 2: Ввод кода
        self.code_widget = QWidget()
        code_layout = QVBoxLayout()
        code_layout.addWidget(QLabel('Введите код из Telegram:'))

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText('12345')
        code_layout.addWidget(self.code_edit)

        self.verify_code_btn = QPushButton('Подтвердить')
        self.verify_code_btn.setStyleSheet('background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;')
        self.verify_code_btn.clicked.connect(self.verify_code)
        code_layout.addWidget(self.verify_code_btn)

        code_layout.addStretch()
        self.code_widget.setLayout(code_layout)

        # Шаг 3: Ввод пароля 2FA
        self.password_widget = QWidget()
        password_layout = QVBoxLayout()
        password_layout.addWidget(QLabel('Введите пароль двухэтапной аутентификации:'))

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText('Пароль 2FA')
        self.password_edit.setEchoMode(QLineEdit.Password)
        password_layout.addWidget(self.password_edit)

        self.verify_password_btn = QPushButton('Подтвердить пароль')
        self.verify_password_btn.setStyleSheet(
            'background-color: #FF9800; color: white; font-weight: bold; padding: 10px;')
        self.verify_password_btn.clicked.connect(self.verify_password)
        password_layout.addWidget(self.verify_password_btn)

        password_layout.addStretch()
        self.password_widget.setLayout(password_layout)

        # Добавляем все виджеты
        self.stacked_layout.addWidget(self.phone_widget)
        self.stacked_layout.addWidget(self.code_widget)
        self.stacked_layout.addWidget(self.password_widget)
        self.stacked_widget.setLayout(self.stacked_layout)
        layout.addWidget(self.stacked_widget)

        # Статус
        self.status_label = QLabel('')
        self.status_label.setStyleSheet('color: gray; font-size: 11px;')
        layout.addWidget(self.status_label)

        self.setLayout(layout)
        self.show_phone_step()

    def show_phone_step(self):
        self.code_widget.setVisible(False)
        self.password_widget.setVisible(False)
        self.phone_widget.setVisible(True)
        self.status_label.setText('Введите номер телефона')
        self.password_entered = False

    def show_code_step(self, phone):
        self.phone_widget.setVisible(False)
        self.password_widget.setVisible(False)
        self.code_widget.setVisible(True)
        self.phone = phone
        self.status_label.setText(f'Код отправлен на {phone}. Введите код из Telegram.')
        self.password_entered = False

    def show_password_step(self):
        self.phone_widget.setVisible(False)
        self.code_widget.setVisible(False)
        self.password_widget.setVisible(True)
        self.status_label.setText('Требуется двухэтапная аутентификация. Введите пароль:')
        self.password_edit.setFocus()
        self.password_entered = False

    def send_code(self):
        phone = self.phone_edit.text().strip()
        if not phone:
            QMessageBox.warning(self, 'Ошибка', 'Введите номер телефона')
            return

        self.send_code_btn.setEnabled(False)
        self.send_code_btn.setText('Отправка...')

        self.send_code_thread = SendCodeThread(phone)
        self.send_code_thread.finished.connect(self.on_code_sent)
        self.send_code_thread.error.connect(self.on_send_code_error)
        self.send_code_thread.start()

    def on_code_sent(self, success, message, phone_code_hash):
        self.send_code_btn.setEnabled(True)
        self.send_code_btn.setText('Отправить код')

        if success:
            self.phone_code_hash = phone_code_hash
            self.show_code_step(self.phone_edit.text().strip())
            self.status_label.setText(message)
        else:
            QMessageBox.warning(self, 'Ошибка', message)

    def on_send_code_error(self, error_message):
        self.send_code_btn.setEnabled(True)
        self.send_code_btn.setText('Отправить код')
        QMessageBox.critical(self, 'Ошибка', f'Ошибка отправки кода: {error_message}')

    def verify_code(self):
        code = self.code_edit.text().strip()
        if not code:
            QMessageBox.warning(self, 'Ошибка', 'Введите код')
            return

        self.verify_code_btn.setEnabled(False)
        self.verify_code_btn.setText('Проверка...')

        self.sign_in_thread = SignInThread(
            self.phone,
            code,
            self.phone_code_hash
        )
        self.sign_in_thread.finished.connect(self.on_sign_in_finished)
        self.sign_in_thread.need_password.connect(self.on_need_password)
        self.sign_in_thread.error.connect(self.on_sign_in_error)
        self.sign_in_thread.start()

    def verify_password(self):
        password = self.password_edit.text().strip()
        if not password:
            QMessageBox.warning(self, 'Ошибка', 'Введите пароль 2FA')
            return

        self.verify_password_btn.setEnabled(False)
        self.verify_password_btn.setText('Проверка...')

        # Повторная попытка авторизации с паролем
        self.sign_in_thread = SignInThread(
            self.phone,
            self.code_edit.text().strip(),
            self.phone_code_hash,
            password
        )
        self.sign_in_thread.finished.connect(self.on_sign_in_finished)
        self.sign_in_thread.error.connect(self.on_sign_in_error)
        self.sign_in_thread.start()
        self.password_entered = True

    def on_sign_in_finished(self, success, message):
        if success:
            self.authorization_success.emit()
            self.accept()
            QMessageBox.information(self, 'Успех', message)
        else:
            if not self.password_entered:
                self.verify_code_btn.setEnabled(True)
                self.verify_code_btn.setText('Подтвердить')
            self.verify_password_btn.setEnabled(True)
            self.verify_password_btn.setText('Подтвердить пароль')
            QMessageBox.warning(self, 'Ошибка', message)

    def on_need_password(self):
        self.verify_code_btn.setEnabled(True)
        self.verify_code_btn.setText('Подтвердить')
        self.show_password_step()

    def on_sign_in_error(self, error_message):
        if not self.password_entered:
            self.verify_code_btn.setEnabled(True)
            self.verify_code_btn.setText('Подтвердить')
        self.verify_password_btn.setEnabled(True)
        self.verify_password_btn.setText('Подтвердить пароль')

        if 'PASSWORD_HASH_INVALID' in error_message:
            QMessageBox.warning(self, 'Ошибка', 'Неверный пароль 2FA. Попробуйте снова.')
            self.password_edit.clear()
            self.password_edit.setFocus()
        else:
            QMessageBox.critical(self, 'Ошибка авторизации', error_message)


class CompactChatWidget(QWidget):
    def __init__(self, chat_id, chat_data, parent=None):
        super().__init__(parent)
        self.chat_id = chat_id
        self.chat_data = chat_data
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(5)

        self.checkbox = QCheckBox()
        layout.addWidget(self.checkbox)

        # Компактная информационная строка
        chat_type_icon = "📢" if self.chat_data['type'] == "Канал" else "👥"
        access_icon = "🔓" if self.chat_data['access_type'] in ["Открытый", "Уже участник"] else "🔒"

        info_text = f"{chat_type_icon} {self.chat_data['title']} {access_icon}"

        chat_info = QLabel(info_text)
        chat_info.setStyleSheet("font-size: 11px; margin: 0; padding: 0;")
        chat_info.setToolTip(f"ID: {self.chat_id}\n"
                             f"Название: {self.chat_data['title']}\n"
                             f"Тип: {self.chat_data['type']}\n"
                             f"Доступ: {self.chat_data['access_type']}\n"
                             f"Статус: {self.chat_data['status']}")
        layout.addWidget(chat_info)

        layout.addStretch()
        self.setLayout(layout)


class SelectChatsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_chats = set()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Выбор групп/каналов для рассылки')
        self.setFixedSize(700, 500)
        layout = QVBoxLayout()

        # Заголовок
        title_label = QLabel('Выберите группы/каналы для рассылки комментариев:')
        title_label.setStyleSheet('font-size: 14px; font-weight: bold; margin-bottom: 10px;')
        layout.addWidget(title_label)

        # Кнопки управления
        buttons_top_layout = QHBoxLayout()

        self.select_all_btn = QPushButton('✅ Выбрать все')
        self.select_all_btn.setStyleSheet('background-color: #4CAF50; color: white; font-size: 11px; padding: 5px;')
        self.select_all_btn.clicked.connect(self.select_all)
        buttons_top_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton('❌ Снять все')
        self.deselect_all_btn.setStyleSheet('background-color: #f44336; color: white; font-size: 11px; padding: 5px;')
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        buttons_top_layout.addWidget(self.deselect_all_btn)

        buttons_top_layout.addStretch()

        layout.addLayout(buttons_top_layout)

        # Область с чатами
        self.chats_scroll = QScrollArea()
        self.chats_widget = QWidget()
        self.chats_layout = QVBoxLayout(self.chats_widget)
        self.chats_layout.setSpacing(1)
        self.chats_layout.setContentsMargins(5, 5, 5, 5)
        self.chats_scroll.setWidget(self.chats_widget)
        self.chats_scroll.setWidgetResizable(True)
        layout.addWidget(self.chats_scroll)

        # Кнопки подтверждения
        buttons_layout = QHBoxLayout()

        self.ok_btn = QPushButton('Сохранить выбор')
        self.ok_btn.setStyleSheet('background-color: #2196F3; color: white; font-weight: bold; padding: 8px;')
        self.ok_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton('Отмена')
        self.cancel_btn.setStyleSheet('background-color: #607D8B; color: white; padding: 8px;')
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
            chat_widget = CompactChatWidget(chat_id, chat_data)
            self.chats_layout.addWidget(chat_widget)

        if not chats:
            no_chats_label = QLabel('Нет сохраненных групп/каналов. Сначала выполните поиск и сохраните группы.')
            no_chats_label.setStyleSheet('color: gray; font-style: italic; padding: 20px; font-size: 12px;')
            no_chats_label.setAlignment(Qt.AlignCenter)
            self.chats_layout.addWidget(no_chats_label)

    def select_all(self):
        """Выбирает все чаты"""
        for i in range(self.chats_layout.count()):
            widget = self.chats_layout.itemAt(i).widget()
            if isinstance(widget, CompactChatWidget):
                widget.checkbox.setChecked(True)

    def deselect_all(self):
        """Снимает выбор со всех чатов"""
        for i in range(self.chats_layout.count()):
            widget = self.chats_layout.itemAt(i).widget()
            if isinstance(widget, CompactChatWidget):
                widget.checkbox.setChecked(False)

    def get_selected_chats(self):
        """Возвращает список выбранных чатов"""
        selected = []
        for i in range(self.chats_layout.count()):
            widget = self.chats_layout.itemAt(i).widget()
            if isinstance(widget, CompactChatWidget) and widget.checkbox.isChecked():
                selected.append(widget.chat_id)
        return selected


class LoadFolderThread(QThread):
    finished = pyqtSignal(dict)
    progress = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, folder_name, phone=None):
        super().__init__()
        self.folder_name = folder_name
        self.client = None
        self.phone = phone
        self.session_file = f"{SESSION_FILE}_{phone.replace('+', '')}" if phone else SESSION_FILE

    def run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            self.client = TelegramClient(self.session_file, API_ID, API_HASH)
            result = loop.run_until_complete(self.load_folder_chats())
            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                loop.close()

    async def load_folder_chats(self):
        """Загружает чаты из указанной папки"""
        found_chats = {}

        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                await self.client.disconnect()
                raise Exception("Пользователь не авторизован")

            self.progress.emit(f"📁 Загружаем чаты из папки: {self.folder_name}")

            # Загружаем структуру папок
            folders = FoldersManager.load_folders()
            if self.folder_name not in folders:
                await self.client.disconnect()
                raise Exception(f"Папка '{self.folder_name}' не найдена")

            folder_chat_ids = folders[self.folder_name]

            if not folder_chat_ids:
                await self.client.disconnect()
                self.progress.emit(f"⚠️ Папка '{self.folder_name}' пустая")
                return found_chats

            # Получаем все диалоги для быстрого поиска
            dialogs = await self.client.get_dialogs(limit=200)

            # Создаем словарь для быстрого поиска диалогов по ID
            dialogs_by_id = {}
            for dialog in dialogs:
                if hasattr(dialog, 'entity') and hasattr(dialog.entity, 'id'):
                    chat_id = str(dialog.entity.id)
                    dialogs_by_id[chat_id] = dialog

            # Обрабатываем каждый чат из папки
            processed = 0
            for chat_id in folder_chat_ids:
                try:
                    # Пробуем найти в уже загруженных диалогах
                    if chat_id in dialogs_by_id:
                        dialog = dialogs_by_id[chat_id]
                        entity = dialog.entity
                        dialog_name = dialog.name
                    else:
                        # Пробуем получить чат напрямую по ID
                        try:
                            entity = await self.client.get_entity(int(chat_id))
                            dialog_name = getattr(entity, 'title', '')
                        except Exception as e:
                            self.progress.emit(f"⚠️ Не удалось получить чат ID {chat_id}: {str(e)}")
                            continue

                    # Обрабатываем чат
                    if await self.process_folder_entity(entity, found_chats, dialog_name):
                        processed += 1
                        chat_title = getattr(entity, 'title', f'Чат {chat_id}')
                        self.progress.emit(f"✅ Загружен: {chat_title} ({processed}/{len(folder_chat_ids)})")
                    else:
                        self.progress.emit(f"⚠️ Пропущен чат ID {chat_id}")

                except Exception as e:
                    self.progress.emit(f"⚠️ Ошибка обработки чата ID {chat_id}: {str(e)}")
                    continue

            await self.client.disconnect()

            if not found_chats:
                self.progress.emit("❌ В папке не найдено доступных чатов")
            else:
                self.progress.emit(f"🎯 Загрузка завершена. Найдено: {len(found_chats)} из {len(folder_chat_ids)}")

            return found_chats

        except Exception as e:
            try:
                await self.client.disconnect()
            except:
                pass
            raise e

    async def process_folder_entity(self, entity, found_chats, dialog_name=None):
        """Обрабатывает сущность из папки БЕЗ тестовых сообщений"""
        try:
            # Пропускаем личные чаты
            if isinstance(entity, User):
                return False

            chat_id = str(entity.id)

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
                chat_title = f"Чат {chat_id}"

            # Очищаем название чата
            chat_title = clean_text(chat_title)

            username = getattr(entity, 'username', '')
            access_type = "Открытый" if username else "Закрытый"

            # Проверяем, можем ли мы писать в чат
            can_comment = True  # Предполагаем что можно
            can_video = True  # Предполагаем что можно

            # Для каналов проверяем, есть ли комментарии
            if isinstance(entity, Channel) and entity.broadcast:
                try:
                    # Пробуем получить информацию о канале
                    full_channel = await self.client(GetFullChannelRequest(entity))
                    if hasattr(full_channel, 'linked_chat_id'):
                        # Есть чат для комментариев
                        can_comment = True
                except:
                    can_comment = False

            # Сохраняем чат
            found_chats[chat_id] = {
                'title': chat_title,
                'type': chat_type,
                'access_type': access_type,
                'can_comment': can_comment,
                'can_video': can_video,
                'last_post_id': '0',
                'last_post_date': '',
                'status': 'не отправлено',
                'send_time': '',
                'username': username
            }
            return True

        except Exception as e:
            self.progress.emit(f"⚠️ Ошибка обработки {getattr(entity, 'title', 'чата')}: {str(e)}")
            return False


class CommentsSearchThread(QThread):
    finished = pyqtSignal(dict)
    progress = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, search_query, limit=50, phone=None):
        super().__init__()
        self.search_query = search_query
        self.limit = limit
        self.client = None
        self.phone = phone
        self.session_file = f"{SESSION_FILE}_{phone.replace('+', '')}" if phone else SESSION_FILE

    def run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            self.client = TelegramClient(self.session_file, API_ID, API_HASH)
            result = loop.run_until_complete(self.search_groups_channels())
            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                loop.close()

    async def search_groups_channels(self):
        """Упрощенный поиск групп и каналов БЕЗ тестовых сообщений"""
        found_chats = {}
        count = 0

        existing_chats = CommentsManager.load_chats()

        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                await self.client.disconnect()
                raise Exception("Пользователь не авторизован")

            self.progress.emit("🔍 Начинаем поиск групп и каналов...")

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

            await self.client.disconnect()

            if not found_chats:
                self.progress.emit("❌ Группы/каналы не найдены. Попробуйте другой запрос.")
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

    async def process_entity(self, entity, found_chats, existing_chats, dialog_name=None):
        """Обрабатывает сущность БЕЗ тестовых сообщений"""
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

            # Очищаем название чата
            chat_title = clean_text(chat_title)

            # Фильтрация по поисковому запросу (если есть)
            if self.search_query and self.search_query.lower() not in chat_title.lower():
                return False

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

            # Сохраняем чат без проверки комментирования
            found_chats[chat_id] = {
                'title': chat_title,
                'type': chat_type,
                'access_type': access_type,
                'can_comment': True,  # Предполагаем что можно комментировать
                'can_video': True,  # Предполагаем что можно видео
                'last_post_id': '0',
                'last_post_date': '',
                'status': 'не отправлено',
                'send_time': '',
                'username': username
            }
            self.progress.emit(f"💬 Найден: {len(found_chats)} - {chat_title} ({chat_type})")
            return True

        except Exception as e:
            self.progress.emit(f"⚠️ Ошибка обработки {getattr(entity, 'title', 'чата')}: {str(e)}")
            return False


class SendCommentThread(QThread):
    finished = pyqtSignal(bool, str)
    error = pyqtSignal(str)

    def __init__(self, chat_id, message, video_path=None, delay=2, delete_after_send=True, force_text_only=False,
                 phone=None):
        super().__init__()
        self.chat_id = chat_id
        self.message = message
        self.video_path = video_path
        self.delay = delay
        self.delete_after_send = delete_after_send
        self.force_text_only = force_text_only
        self.phone = phone
        self.session_file = f"{SESSION_FILE}_{phone.replace('+', '')}" if phone else SESSION_FILE

    def run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            client = TelegramClient(self.session_file, API_ID, API_HASH)
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

            # Ищем последнее сообщение в чате для ответа
            messages = await client.get_messages(entity, limit=10)
            last_message = None

            for msg in messages:
                if msg and hasattr(msg, 'sender_id') and msg.sender_id != (await client.get_me()).id:
                    last_message = msg
                    break

            if not last_message:
                await client.disconnect()
                raise Exception("Не найдено сообщений для ответа")

            sent_message = None

            # Очищаем сообщение перед отправкой
            clean_message = clean_text(self.message) if self.message else ""

            # Пробуем отправить видео, если есть
            if self.video_path and os.path.exists(self.video_path) and not self.force_text_only:
                try:
                    if clean_message.strip():
                        sent_message = await client.send_file(entity, self.video_path,
                                                              caption=clean_message,
                                                              reply_to=last_message.id)
                    else:
                        sent_message = await client.send_file(entity, self.video_path,
                                                              reply_to=last_message.id)
                except Exception:
                    # Если не получилось отправить видео, отправляем текст
                    if clean_message.strip():
                        sent_message = await client.send_message(entity, clean_message,
                                                                 reply_to=last_message.id)
                    else:
                        await client.disconnect()
                        raise Exception("Сообщение пустое")
            else:
                if clean_message.strip():
                    sent_message = await client.send_message(entity, clean_message,
                                                             reply_to=last_message.id)
                else:
                    await client.disconnect()
                    raise Exception("Сообщение пустое")

            # Удаление тестовых сообщений
            if self.delete_after_send and sent_message:
                await asyncio.sleep(3)
                try:
                    await client.delete_messages(entity, [sent_message.id])
                except Exception as e:
                    pass  # Игнорируем ошибки удаления

            await asyncio.sleep(1)
            await client.disconnect()

            # Обновляем статус только если это НЕ тестовое сообщение
            if not self.delete_after_send:
                send_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
                CommentsManager.update_chat_status(self.chat_id, 'отправлено', send_time)

            chat_title = chat_info.get('title', 'чат')
            media_type = "видео" if (self.video_path and not self.force_text_only) else "текст"

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

    def __init__(self, message, video_path, selected_chats, min_delay=3600, max_delay=5400, daily_limit=10, phone=None):
        super().__init__()
        self.message = message
        self.video_path = video_path
        self.selected_chats = selected_chats
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.daily_limit = daily_limit
        self.phone = phone
        self.session_file = f"{SESSION_FILE}_{phone.replace('+', '')}" if phone else SESSION_FILE
        self.is_running = True

    def stop_sending(self):
        self.is_running = False

    def run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            client = TelegramClient(self.session_file, API_ID, API_HASH)
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
                    entity = await client.get_entity(int(chat_id))

                    # Ищем последнее сообщение от другого пользователя для ответа
                    messages = await client.get_messages(entity, limit=10)
                    last_message = None

                    for msg in messages:
                        if msg and hasattr(msg, 'sender_id') and msg.sender_id != (await client.get_me()).id:
                            last_message = msg
                            break

                    if not last_message:
                        self.progress.emit(f"⚠️ Пропускаем {chat_title}: нет сообщений для ответа",
                                           sent_count, failed_count)
                        failed_count += 1
                        continue

                    sent_message = None

                    # Очищаем сообщение
                    clean_message = clean_text(self.message) if self.message else ""

                    # Пробуем отправить видео, если есть
                    if self.video_path and os.path.exists(self.video_path):
                        try:
                            if clean_message.strip():
                                sent_message = await client.send_file(entity, self.video_path,
                                                                      caption=clean_message,
                                                                      reply_to=last_message.id)
                                media_type = "видео+текст"
                            else:
                                sent_message = await client.send_file(entity, self.video_path,
                                                                      reply_to=last_message.id)
                                media_type = "видео"
                        except Exception:
                            # Если не получилось отправить видео, отправляем текст
                            if clean_message.strip():
                                sent_message = await client.send_message(entity, clean_message,
                                                                         reply_to=last_message.id)
                                media_type = "текст"
                            else:
                                self.progress.emit(f"⚠️ Пропускаем {chat_title}: сообщение пустое",
                                                   sent_count, failed_count)
                                failed_count += 1
                                continue
                    else:
                        if clean_message.strip():
                            sent_message = await client.send_message(entity, clean_message,
                                                                     reply_to=last_message.id)
                            media_type = "текст"
                        else:
                            self.progress.emit(f"⚠️ Пропускаем {chat_title}: сообщение пустое",
                                               sent_count, failed_count)
                            failed_count += 1
                            continue

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
        self.current_phone = None
        self.init_ui()
        self.load_chats()
        self.check_auth()
        self.load_folders_combo()

    def init_ui(self):
        self.setWindowTitle('Telegram - Автоматические комментарии в группах и каналах')
        self.setFixedSize(1100, 800)

        central_widget = QWidget()
        main_layout = QHBoxLayout()

        # Левая панель - поиск и управление чатами
        left_panel = QWidget()
        left_panel.setMaximumWidth(450)
        left_layout = QVBoxLayout()

        # Авторизация
        self.auth_btn = QPushButton('🔐 Авторизация')
        self.auth_btn.setStyleSheet('background-color: #FF9800; color: white; font-weight: bold; padding: 8px;')
        self.auth_btn.clicked.connect(self.auth_button_clicked)
        left_layout.addWidget(self.auth_btn)

        # Поиск чатов
        search_group = QGroupBox('Поиск и загрузка чатов')
        search_layout = QVBoxLayout()

        search_input_layout = QHBoxLayout()
        search_input_layout.addWidget(QLabel('Ключевое слово:'))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('новости, музыка, спорт...')
        self.search_edit.returnPressed.connect(self.search_chats)
        search_input_layout.addWidget(self.search_edit)

        self.search_btn = QPushButton('🔍 Найти')
        self.search_btn.setStyleSheet('background-color: #2196F3; color: white; font-weight: bold; padding: 6px;')
        self.search_btn.clicked.connect(self.search_chats)
        search_input_layout.addWidget(self.search_btn)

        search_layout.addLayout(search_input_layout)

        # Загрузка из папок
        folder_layout = QHBoxLayout()
        folder_layout.addWidget(QLabel('Папка:'))

        self.folders_combo = QComboBox()
        self.folders_combo.setMinimumWidth(120)
        folder_layout.addWidget(self.folders_combo)

        self.load_folder_btn = QPushButton('📁 Загрузить')
        self.load_folder_btn.setStyleSheet('background-color: #9C27B0; color: white; font-weight: bold; padding: 6px;')
        self.load_folder_btn.clicked.connect(self.load_folder_chats)
        folder_layout.addWidget(self.load_folder_btn)

        self.refresh_folders_btn = QPushButton('🔄')
        self.refresh_folders_btn.setStyleSheet('background-color: #FF9800; color: white; padding: 6px;')
        self.refresh_folders_btn.clicked.connect(self.refresh_folders)
        self.refresh_folders_btn.setToolTip('Обновить список папок')
        folder_layout.addWidget(self.refresh_folders_btn)

        search_layout.addLayout(folder_layout)

        search_group.setLayout(search_layout)
        left_layout.addWidget(search_group)

        # Список найденных чатов
        left_layout.addWidget(QLabel('Найденные чаты:'))

        self.found_chats_scroll = QScrollArea()
        self.found_chats_widget = QWidget()
        self.found_chats_layout = QVBoxLayout(self.found_chats_widget)
        self.found_chats_layout.setSpacing(1)
        self.found_chats_layout.setContentsMargins(3, 3, 3, 3)
        self.found_chats_scroll.setWidget(self.found_chats_widget)
        self.found_chats_scroll.setWidgetResizable(True)
        self.found_chats_scroll.setMinimumHeight(200)
        left_layout.addWidget(self.found_chats_scroll)

        # Кнопки управления найденными чатами
        found_chats_buttons = QHBoxLayout()

        self.save_selected_btn = QPushButton('💾 Добавить выбранные')
        self.save_selected_btn.setStyleSheet(
            'background-color: #4CAF50; color: white; font-weight: bold; padding: 6px;')
        self.save_selected_btn.clicked.connect(self.save_selected_chats)
        found_chats_buttons.addWidget(self.save_selected_btn)

        self.clear_search_btn = QPushButton('🗑️ Очистить')
        self.clear_search_btn.setStyleSheet('background-color: #f44336; color: white; padding: 6px;')
        self.clear_search_btn.clicked.connect(self.clear_search_results)
        found_chats_buttons.addWidget(self.clear_search_btn)

        left_layout.addLayout(found_chats_buttons)

        # Управление сохраненными чатами
        saved_chats_group = QGroupBox('Сохраненные чаты')
        saved_layout = QVBoxLayout()

        saved_buttons = QHBoxLayout()

        self.select_chats_btn = QPushButton('📋 Выбрать для рассылки')
        self.select_chats_btn.setStyleSheet('background-color: #FF9800; color: white; font-weight: bold; padding: 6px;')
        self.select_chats_btn.clicked.connect(self.select_chats_for_sending)
        saved_buttons.addWidget(self.select_chats_btn)

        self.delete_chats_btn = QPushButton('🗑️ Удалить')
        self.delete_chats_btn.setStyleSheet('background-color: #f44336; color: white; padding: 6px;')
        self.delete_chats_btn.clicked.connect(self.delete_selected_chats)
        saved_buttons.addWidget(self.delete_chats_btn)

        saved_layout.addLayout(saved_buttons)

        # Информация о выбранных чатах
        self.selected_chats_info = QLabel('Выбрано для рассылки: 0')
        self.selected_chats_info.setStyleSheet('color: #2196F3; font-weight: bold; padding: 3px; font-size: 12px;')
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
        self.message_text.setMinimumHeight(120)
        self.message_text.setPlaceholderText('Введите текст комментария...\nМожно использовать смайлы/эмодзи: 😊 👍 🚀')

        # Добавляем кнопки быстрой вставки смайлов
        emoji_layout = QHBoxLayout()
        emoji_layout.addWidget(QLabel('Быстрые смайлы:'))

        popular_emojis = ['😊', '👍', '❤️', '🔥', '🚀', '💯', '⭐', '🎯', '🤝', '🙏']

        for emoji in popular_emojis:
            emoji_btn = QPushButton(emoji)
            emoji_btn.setStyleSheet('font-size: 16px; padding: 2px 5px;')
            emoji_btn.clicked.connect(lambda checked, e=emoji: self.insert_emoji(e))
            emoji_layout.addWidget(emoji_btn)

        emoji_layout.addStretch()
        message_layout.addLayout(emoji_layout)

        message_layout.addWidget(self.message_text)

        video_layout = QHBoxLayout()
        self.video_btn = QPushButton('🎥 Загрузить видео')
        self.video_btn.setStyleSheet('background-color: #9C27B0; color: white; font-weight: bold; padding: 6px;')
        self.video_btn.clicked.connect(self.load_video)
        video_layout.addWidget(self.video_btn)

        self.video_label = QLabel('Видео не выбрано')
        self.video_label.setStyleSheet('font-size: 11px; color: #666;')
        video_layout.addWidget(self.video_label)

        self.clear_video_btn = QPushButton('❌')
        self.clear_video_btn.setStyleSheet('background-color: #795548; color: white; padding: 6px;')
        self.clear_video_btn.clicked.connect(self.clear_video)
        self.clear_video_btn.setToolTip('Очистить видео')
        video_layout.addWidget(self.clear_video_btn)

        message_layout.addLayout(video_layout)

        message_group.setLayout(message_layout)
        right_layout.addWidget(message_group)

        # Статистика и управление
        stats_group = QGroupBox('Управление рассылкой')
        stats_layout = QVBoxLayout()

        stats_info_layout = QHBoxLayout()

        self.stats_label = QLabel('Всего: 0 | Сегодня: 0/0')
        self.stats_label.setStyleSheet('font-size: 12px; font-weight: bold;')
        stats_info_layout.addWidget(self.stats_label)

        self.settings_btn = QPushButton('⚙️')
        self.settings_btn.setStyleSheet('background-color: #607D8B; color: white; padding: 6px;')
        self.settings_btn.clicked.connect(self.show_settings)
        self.settings_btn.setToolTip('Настройки')
        stats_info_layout.addWidget(self.settings_btn)

        stats_layout.addLayout(stats_info_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        stats_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel('')
        self.progress_label.setVisible(False)
        self.progress_label.setStyleSheet('font-size: 11px;')
        stats_layout.addWidget(self.progress_label)

        send_buttons_layout = QHBoxLayout()

        self.send_test_button = QPushButton('🧪 Тест')
        self.send_test_button.setStyleSheet('background-color: #FF5722; color: white; font-weight: bold; padding: 6px;')
        self.send_test_button.clicked.connect(self.send_test_comment)
        self.send_test_button.setToolTip('Тестовый комментарий')
        send_buttons_layout.addWidget(self.send_test_button)

        self.send_selected_btn = QPushButton('📤 Отправить')
        self.send_selected_btn.setStyleSheet(
            'background-color: #FF9800; color: white; font-weight: bold; padding: 6px;')
        self.send_selected_btn.clicked.connect(self.send_to_selected)
        send_buttons_layout.addWidget(self.send_selected_btn)

        self.auto_send_btn = QPushButton('🤖 Авто')
        self.auto_send_btn.setStyleSheet('background-color: #4CAF50; color: white; font-weight: bold; padding: 6px;')
        self.auto_send_btn.clicked.connect(self.toggle_auto_send)
        self.auto_send_btn.setToolTip('Автоматическая рассылка')
        send_buttons_layout.addWidget(self.auto_send_btn)

        self.stop_btn = QPushButton('⏹️')
        self.stop_btn.setStyleSheet('background-color: #f44336; color: white; padding: 6px;')
        self.stop_btn.clicked.connect(self.stop_sending)
        self.stop_btn.setVisible(False)
        self.stop_btn.setToolTip('Остановить')
        send_buttons_layout.addWidget(self.stop_btn)

        stats_layout.addLayout(send_buttons_layout)
        stats_group.setLayout(stats_layout)
        right_layout.addWidget(stats_group)

        right_panel.setLayout(right_layout)
        main_layout.addWidget(right_panel)

        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        self.update_stats()

    def insert_emoji(self, emoji):
        """Вставляет смайл в текстовое поле"""
        cursor = self.message_text.textCursor()
        cursor.insertText(emoji)
        self.message_text.setFocus()

    def refresh_folders(self):
        """Обновляет список папок из Telegram"""
        if not self.check_auth():
            QMessageBox.warning(self, 'Ошибка', 'Сначала авторизуйтесь!')
            return

        self.refresh_folders_btn.setEnabled(False)
        self.refresh_folders_btn.setText('...')

        self.load_folders_thread = LoadFoldersThread(self.current_phone)
        self.load_folders_thread.finished.connect(self.on_folders_loaded)
        self.load_folders_thread.progress.connect(self.on_folders_progress)
        self.load_folders_thread.error.connect(self.on_folders_error)
        self.load_folders_thread.start()

    def on_folders_progress(self, message):
        self.statusBar().showMessage(message)

    def on_folders_loaded(self, folders):
        self.refresh_folders_btn.setEnabled(True)
        self.refresh_folders_btn.setText('🔄')
        self.statusBar().showMessage(f'Загружено папок: {len(folders)}')
        self.load_folders_combo()

    def on_folders_error(self, error_message):
        self.refresh_folders_btn.setEnabled(True)
        self.refresh_folders_btn.setText('🔄')
        QMessageBox.warning(self, 'Ошибка загрузки папок', error_message)
        self.load_folders_combo()

    def load_folders_combo(self):
        """Загружает список папок в комбобокс"""
        folder_names = FoldersManager.get_folder_names()
        self.folders_combo.clear()

        if folder_names:
            self.folders_combo.addItems(folder_names)
            self.folders_combo.setCurrentIndex(0)
        else:
            self.folders_combo.addItem("Папки не найдены")

    def load_folder_chats(self):
        """Загружает чаты из выбранной папки"""
        if not self.check_auth():
            QMessageBox.warning(self, 'Ошибка', 'Сначала авторизуйтесь!')
            return

        folder_name = self.folders_combo.currentText()

        if not folder_name or "Папки не найдены" in folder_name:
            QMessageBox.warning(self, 'Ошибка', 'Сначала загрузите папки из Telegram')
            return

        self.load_folder_btn.setEnabled(False)
        self.load_folder_btn.setText('...')

        self.load_folder_thread = LoadFolderThread(folder_name, self.current_phone)
        self.load_folder_thread.finished.connect(self.on_folder_load_finished)
        self.load_folder_thread.progress.connect(self.on_folder_load_progress)
        self.load_folder_thread.error.connect(self.on_folder_load_error)
        self.load_folder_thread.start()

    def on_folder_load_progress(self, message):
        self.statusBar().showMessage(message)

    def on_folder_load_finished(self, found_chats):
        self.load_folder_btn.setEnabled(True)
        self.load_folder_btn.setText('📁 Загрузить')
        self.statusBar().showMessage(f'Загружено из папки: {len(found_chats)} чатов')

        # Очищаем предыдущие результаты
        for i in reversed(range(self.found_chats_layout.count())):
            widget = self.found_chats_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Добавляем новые чаты
        self.found_chats = found_chats
        for chat_id, chat_data in found_chats.items():
            chat_widget = CompactChatWidget(chat_id, chat_data)
            self.found_chats_layout.addWidget(chat_widget)

        if not found_chats:
            no_chats_label = QLabel('В папке не найдено чатов')
            no_chats_label.setStyleSheet('color: gray; font-style: italic; padding: 10px; font-size: 11px;')
            no_chats_label.setAlignment(Qt.AlignCenter)
            self.found_chats_layout.addWidget(no_chats_label)

    def on_folder_load_error(self, error_message):
        self.load_folder_btn.setEnabled(True)
        self.load_folder_btn.setText('📁 Загрузить')
        QMessageBox.critical(self, 'Ошибка загрузки папки', error_message)

    def check_auth(self):
        """Проверяет авторизацию для всех возможных сессий"""
        import glob
        session_files = glob.glob(f"{SESSION_FILE}_*")

        is_authorized = False

        for session_file in session_files:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                client = TelegramClient(session_file, API_ID, API_HASH)

                async def check_auth_internal():
                    try:
                        await client.connect()
                        if not client.is_connected():
                            return False
                        auth_status = await client.is_user_authorized()
                        if auth_status:
                            # Извлекаем номер из имени файла
                            phone_part = session_file.split('_')[-1]
                            self.current_phone = f"+{phone_part}"
                        return auth_status
                    except Exception:
                        return False
                    finally:
                        try:
                            await client.disconnect()
                        except:
                            pass

                is_authorized = loop.run_until_complete(check_auth_internal())
                if is_authorized:
                    break

            except Exception:
                continue
            finally:
                if loop and not loop.is_closed():
                    loop.close()

        if is_authorized:
            self.auth_btn.setText(f'✅ Авторизован ({self.current_phone})')
            self.auth_btn.setStyleSheet('background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;')
        else:
            self.auth_btn.setText('🔐 Авторизация')
            self.auth_btn.setStyleSheet('background-color: #FF9800; color: white; font-weight: bold; padding: 8px;')
            self.current_phone = None

        return is_authorized

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
            # Удаляем все сессионные файлы
            import glob
            session_files = glob.glob(f"{SESSION_FILE}_*")
            for session_file in session_files:
                try:
                    os.remove(session_file)
                except:
                    pass

            self.current_phone = None
            self.auth_btn.setText('🔐 Авторизация')
            self.auth_btn.setStyleSheet('background-color: #FF9800; color: white; font-weight: bold; padding: 8px;')
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

        self.stats_label.setText(f'Всего: {total_chats} | Сегодня: {today_sent}/{daily_limit}')
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
        self.search_btn.setText('...')

        self.search_thread = CommentsSearchThread(search_query, 30, self.current_phone)
        self.search_thread.finished.connect(self.on_search_finished)
        self.search_thread.progress.connect(self.on_search_progress)
        self.search_thread.error.connect(self.on_search_error)
        self.search_thread.start()

    def on_search_progress(self, message):
        self.statusBar().showMessage(message)

    def on_search_finished(self, found_chats):
        self.search_btn.setEnabled(True)
        self.search_btn.setText('🔍 Найти')
        self.statusBar().showMessage(f'Найдено: {len(found_chats)} чатов')

        # Очищаем предыдущие результаты
        for i in reversed(range(self.found_chats_layout.count())):
            widget = self.found_chats_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Добавляем новые чаты
        self.found_chats = found_chats
        for chat_id, chat_data in found_chats.items():
            chat_widget = CompactChatWidget(chat_id, chat_data)
            self.found_chats_layout.addWidget(chat_widget)

        if not found_chats:
            no_chats_label = QLabel('Чаты не найдены. Попробуйте другой запрос.')
            no_chats_label.setStyleSheet('color: gray; font-style: italic; padding: 10px; font-size: 11px;')
            no_chats_label.setAlignment(Qt.AlignCenter)
            self.found_chats_layout.addWidget(no_chats_label)

    def on_search_error(self, error_message):
        self.search_btn.setEnabled(True)
        self.search_btn.setText('🔍 Найти')
        QMessageBox.critical(self, 'Ошибка поиска', error_message)

    def save_selected_chats(self):
        if not hasattr(self, 'found_chats'):
            QMessageBox.warning(self, 'Ошибка', 'Сначала выполните поиск или загрузку чатов')
            return

        selected_chats = {}
        for i in range(self.found_chats_layout.count()):
            widget = self.found_chats_layout.itemAt(i).widget()
            if isinstance(widget, CompactChatWidget) and widget.checkbox.isChecked():
                selected_chats[widget.chat_id] = widget.chat_data

        if not selected_chats:
            QMessageBox.warning(self, 'Ошибка', 'Выберите хотя бы один чат')
            return

        if CommentsManager.add_chats(selected_chats):
            QMessageBox.information(self, 'Успех', f'Добавлено в список: {len(selected_chats)}')
            self.load_chats()
        else:
            QMessageBox.warning(self, 'Ошибка', 'Не удалось добавить чаты в список')

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
                                    f'Выбрано {len(self.selected_chats_for_sending)} чатов для рассылки')

    def delete_selected_chats(self):
        """Удаляет выбранные чаты"""
        dialog = SelectChatsDialog(self)
        dialog.load_chats()
        dialog.setWindowTitle('Выберите чаты для удаления')
        if dialog.exec_() == QDialog.Accepted:
            chats_to_delete = dialog.get_selected_chats()

        if not chats_to_delete:
            return

        reply = QMessageBox.question(self, 'Подтверждение',
                                     f'Удалить {len(chats_to_delete)} чатов из списка?',
                                     QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            if CommentsManager.delete_chats(chats_to_delete):
                # Обновляем список выбранных чатов
                self.selected_chats_for_sending = self.selected_chats_for_sending - set(chats_to_delete)
                self.load_chats()
                QMessageBox.information(self, 'Успех', f'Удалено {len(chats_to_delete)} чатов')
            else:
                QMessageBox.warning(self, 'Ошибка', 'Не удалось удалить чаты')

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

        self.statusBar().showMessage(f'🧪 Тестовый комментарий в {chat_title}...')

        # Для тестового комментария устанавливаем delete_after_send=True
        self.send_thread = SendCommentThread(chat_id, message, video_path, delete_after_send=True,
                                             phone=self.current_phone)
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
            QMessageBox.warning(self, 'Ошибка', 'Сначала выберите чаты для отправки')
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
            QMessageBox.warning(self, 'Ошибка', 'Во все выбранные чаты уже отправляли сегодня')
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
        self.send_thread = SendCommentThread(chat_id, message, video_path, delete_after_send=False,
                                             phone=self.current_phone)
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
            QMessageBox.warning(self, 'Ошибка', 'Сначала выберите чаты для отправки')
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
            self.settings['daily_limit'],
            self.current_phone
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