from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile
import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv

from auth import AuthManager
from image_processor import DocumentProcessor

# Загружаем переменные окружения
load_dotenv()

logger = logging.getLogger(__name__)
user_logger = logging.getLogger('user_activity')

class DocumentFillStates(StatesGroup):
    waiting_for_template = State()
    waiting_for_data = State()
    waiting_for_config = State()

class DocumentBot:
    def __init__(self, bot_token: str):
        self.bot = Bot(token=bot_token)
        self.dp = Dispatcher(storage=MemoryStorage())
        self.auth_manager = AuthManager()
        self.document_processor = DocumentProcessor()

        # ID администратора из переменной окружения
        admin_id_str = os.getenv("ADMIN_ID", "")
        self.admin_id = int(admin_id_str) if admin_id_str.isdigit() else None

        if self.admin_id:
            logger.info(f"Admin ID configured: {self.admin_id}")
        else:
            logger.warning("No admin ID configured - admin commands will be disabled")

        # Регистрируем обработчики
        self._register_handlers()

    def _register_handlers(self):
        """Регистрация обработчиков команд"""
        self.dp.message.register(self.cmd_start, Command("start"))
        self.dp.message.register(self.cmd_help, Command("help"))
        self.dp.message.register(self.cmd_login, Command("login"))
        self.dp.message.register(self.cmd_logout, Command("logout"))
        self.dp.message.register(self.cmd_templates, Command("templates"))
        self.dp.message.register(self.cmd_fill, Command("fill"))
        self.dp.message.register(self.cmd_config, Command("config"))

        # Админские команды
        self.dp.message.register(self.cmd_logs, Command("logs"))
        self.dp.message.register(self.cmd_stats, Command("stats"))

        # FSM handlers
        self.dp.message.register(self.process_template_selection, DocumentFillStates.waiting_for_template)
        self.dp.message.register(self.process_data_input, DocumentFillStates.waiting_for_data)
        self.dp.message.register(self.process_config_input, DocumentFillStates.waiting_for_config)

    async def cmd_start(self, message: types.Message):
        """Команда /start"""
        welcome_text = """
🤖 **Бот для заполнения документов**

Этот бот поможет вам автоматически заполнять документы вашими данными.

🔐 **Для начала работы:**
`/login <пароль>` - войти в систему

📋 **Доступные команды:**
`/templates` - показать доступные шаблоны
`/fill` - заполнить документ
`/config` - настроить поля шаблона
`/help` - помощь
`/logout` - выйти из системы

⚠️ Доступ к боту защищен паролем для сотрудников.
        """
        await message.answer(welcome_text, parse_mode="Markdown")

    async def cmd_help(self, message: types.Message):
        """Команда /help"""
        help_text = """
📖 **Справка по использованию бота**

**Основные команды:**
• `/login <пароль>` - авторизация
• `/templates` - список шаблонов документов
• `/fill` - заполнить документ данными
• `/config` - настроить координаты полей

**Процесс заполнения документа:**
1. Войдите в систему: `/login your_password`
2. Просмотрите шаблоны: `/templates`
3. Заполните документ: `/fill`
4. Выберите шаблон из списка
5. Введите данные в формате: `поле=значение`

**Пример ввода данных:**
```
имя=Иван Петров
должность=Менеджер
дата=01.01.2024
```

**Настройка шаблона:**
Используйте `/config` для настройки координат полей нового шаблона.
        """

        # Добавляем админские команды для администратора
        if self.admin_id and message.from_user.id == self.admin_id:
            help_text += """

**Команды администратора:**
• `/logs` - просмотр логов активности пользователей
• `/stats` - статистика использования бота
            """

        await message.answer(help_text, parse_mode="Markdown")

    async def cmd_login(self, message: types.Message):
        """Команда /login"""
        user_id = message.from_user.id
        username = message.from_user.username or "Unknown"
        first_name = message.from_user.first_name or "Unknown"

        user_logger.info(f"LOGIN_ATTEMPT - User: {user_id} (@{username}, {first_name})")

        args = message.text.split(' ', 1)
        if len(args) < 2:
            user_logger.info(f"LOGIN_FAILED - User: {user_id} - Reason: No password provided")
            await message.answer("❌ Укажите пароль: `/login <пароль>`", parse_mode="Markdown")
            return

        password = args[1]
        if self.auth_manager.authenticate(user_id, password):
            user_logger.info(f"LOGIN_SUCCESS - User: {user_id} (@{username}, {first_name})")
            await message.answer("✅ Успешная авторизация! Теперь вы можете использовать бота.")
        else:
            user_logger.info(f"LOGIN_FAILED - User: {user_id} (@{username}, {first_name}) - Reason: Wrong password")
            await message.answer("❌ Неверный пароль. Доступ запрещен.")

    async def cmd_logout(self, message: types.Message):
        """Команда /logout"""
        self.auth_manager.logout(message.from_user.id)
        await message.answer("👋 Вы вышли из системы.")

    async def cmd_templates(self, message: types.Message):
        """Показать доступные шаблоны"""
        if not self.auth_manager.is_authenticated(message.from_user.id):
            await message.answer("🔐 Доступ запрещен. Введите команду /login <пароль> для входа в систему.")
            return

        templates = self.document_processor.get_available_templates()

        if not templates:
            await message.answer("📄 Шаблоны документов не найдены.")
            return

        template_list = "\n".join([f"• {template}" for template in templates])
        await message.answer(f"📋 Доступные шаблоны:\n\n{template_list}")

    async def cmd_fill(self, message: types.Message, state: FSMContext):
        """Начать процесс заполнения документа"""
        if not self.auth_manager.is_authenticated(message.from_user.id):
            await message.answer("🔐 Доступ запрещен. Введите команду /login <пароль> для входа в систему.")
            return

        templates = self.document_processor.get_available_templates()

        if not templates:
            await message.answer("📄 Шаблоны документов не найдены.")
            return

        template_list = "\n".join([f"{i+1}. {template}" for i, template in enumerate(templates)])

        await message.answer(
            f"📋 Выберите шаблон для заполнения:\n\n{template_list}\n\n"
            "Отправьте номер шаблона или его название:"
        )

        await state.update_data(templates=templates)
        await state.set_state(DocumentFillStates.waiting_for_template)

    async def process_template_selection(self, message: types.Message, state: FSMContext):
        """Обработка выбора шаблона"""
        data = await state.get_data()
        templates = data.get('templates', [])

        selected_template = None

        # Попытка найти шаблон по номеру или названию
        try:
            index = int(message.text) - 1
            if 0 <= index < len(templates):
                selected_template = templates[index]
        except ValueError:
            # Поиск по названию
            for template in templates:
                if message.text.lower() in template.lower():
                    selected_template = template
                    break

        if not selected_template:
            await message.answer("❌ Шаблон не найден. Попробуйте еще раз.")
            return

        # Проверяем конфигурацию шаблона
        config = self.document_processor.load_template_config(selected_template)
        if not config:
            await message.answer(
                f"❌ Конфигурация для шаблона '{selected_template}' не найдена.\n"
                f"Используйте команду /config для настройки полей."
            )
            await state.clear()
            return

        fields = list(config.get('fields', {}).keys())
        if not fields:
            await message.answer(f"❌ Поля для шаблона '{selected_template}' не настроены.")
            await state.clear()
            return

        fields_list = "\n".join([f"• {field}" for field in fields])

        await message.answer(
            f"✅ Выбран шаблон: {selected_template}\n\n"
            f"📝 Доступные поля:\n{fields_list}\n\n"
            f"Введите данные в формате:\n"
            f"поле1=значение1\n"
            f"поле2=значение2\n\n"
            f"Каждое поле с новой строки."
        )

        await state.update_data(selected_template=selected_template, fields=fields)
        await state.set_state(DocumentFillStates.waiting_for_data)

    async def process_data_input(self, message: types.Message, state: FSMContext):
        """Обработка ввода данных для заполнения"""
        data = await state.get_data()
        selected_template = data.get('selected_template')

        if not selected_template:
            await message.answer("❌ Ошибка: шаблон не выбран.")
            await state.clear()
            return

        # Парсинг данных
        fill_data = {}
        lines = message.text.strip().split('\n')

        for line in lines:
            if '=' in line:
                key, value = line.split('=', 1)
                fill_data[key.strip()] = value.strip()

        if not fill_data:
            await message.answer(
                "❌ Данные не распознаны. Используйте формат:\n"
                "`поле=значение`"
            )
            return

        # Генерируем документ
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"filled_{timestamp}_{selected_template}"
        output_path = os.path.join("filled_documents", output_filename)

        success = self.document_processor.fill_document(
            selected_template, fill_data, output_path
        )

        if success:
            try:
                user_id = message.from_user.id
                username = message.from_user.username or "Unknown"
                user_logger.info(f"DOCUMENT_FILLED - User: {user_id} (@{username}) - Template: {selected_template} - Fields: {list(fill_data.keys())}")

                # Отправляем заполненный документ
                photo = FSInputFile(output_path)
                await message.answer_photo(
                    photo,
                    caption=f"✅ Документ успешно заполнен!\n\n"
                           f"📄 Шаблон: {selected_template}\n"
                           f"📝 Заполненные поля: {', '.join(fill_data.keys())}"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки документа: {e}")
                user_logger.error(f"DOCUMENT_SEND_ERROR - User: {message.from_user.id} - Error: {e}")
                await message.answer("❌ Ошибка при отправке документа.")
        else:
            user_logger.error(f"DOCUMENT_FILL_ERROR - User: {message.from_user.id} - Template: {selected_template}")
            await message.answer("❌ Ошибка при заполнении документа.")

        await state.clear()

    async def cmd_config(self, message: types.Message, state: FSMContext):
        """Настройка полей шаблона"""
        if not self.auth_manager.is_authenticated(message.from_user.id):
            await message.answer("🔐 Доступ запрещен. Введите команду /login <пароль> для входа в систему.")
            return

        await message.answer(
            "⚙️ **Настройка полей шаблона**\n\n"
            "Отправьте конфигурацию в JSON формате:\n\n"
            "```json\n"
            "{\n"
            '  "template_name": "document.jpg",\n'
            '  "fields": {\n'
            '    "имя": {"x": 100, "y": 200, "font_size": 24},\n'
            '    "дата": {"x": 300, "y": 400, "font_size": 20}\n'
            "  }\n"
            "}\n"
            "```",
            parse_mode="Markdown"
        )
        await state.set_state(DocumentFillStates.waiting_for_config)

    async def process_config_input(self, message: types.Message, state: FSMContext):
        """Обработка ввода конфигурации"""
        try:
            import json
            config = json.loads(message.text)

            template_name = config.get('template_name')
            fields = config.get('fields', {})

            if not template_name or not fields:
                await message.answer("❌ Неверный формат конфигурации.")
                return

            success = self.document_processor.save_template_config(template_name, config)

            if success:
                await message.answer(f"✅ Конфигурация для '{template_name}' сохранена!")
            else:
                await message.answer("❌ Ошибка сохранения конфигурации.")

        except json.JSONDecodeError:
            await message.answer("❌ Ошибка в JSON формате.")
        except Exception as e:
            logger.error(f"Ошибка обработки конфигурации: {e}")
            await message.answer("❌ Ошибка обработки конфигурации.")

        await state.clear()

    async def cmd_logs(self, message: types.Message):
        """Команда просмотра логов (только для администратора)"""
        if not self.admin_id:
            await message.answer("❌ Администратор не настроен в системе.")
            return

        if message.from_user.id != self.admin_id:
            await message.answer("🚫 Доступ запрещен. Команда доступна только администратору.")
            return

        try:
            # Читаем последние 20 строк из user_activity.log
            if os.path.exists("user_activity.log"):
                with open("user_activity.log", "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    recent_logs = lines[-20:] if len(lines) > 20 else lines

                if recent_logs:
                    log_text = "".join(recent_logs)
                    # Разбиваем на части если слишком длинно
                    if len(log_text) > 4000:
                        parts = [log_text[i:i+4000] for i in range(0, len(log_text), 4000)]
                        for i, part in enumerate(parts):
                            await message.answer(f"📊 Логи активности (часть {i+1}/{len(parts)}):\n\n```\n{part}\n```", parse_mode="Markdown")
                    else:
                        await message.answer(f"📊 Последние записи логов активности:\n\n```\n{log_text}\n```", parse_mode="Markdown")
                else:
                    await message.answer("📊 Логи активности пусты.")
            else:
                await message.answer("📊 Файл логов не найден.")
        except Exception as e:
            logger.error(f"Ошибка чтения логов: {e}")
            await message.answer("❌ Ошибка при чтении логов.")

    async def cmd_stats(self, message: types.Message):
        """Команда просмотра статистики (только для администратора)"""
        if not self.admin_id:
            await message.answer("❌ Администратор не настроен в системе.")
            return

        if message.from_user.id != self.admin_id:
            await message.answer("🚫 Доступ запрещен. Команда доступна только администратору.")
            return

        try:
            # Анализируем логи для получения статистики
            stats = {
                'total_logins': 0,
                'successful_logins': 0,
                'failed_logins': 0,
                'documents_filled': 0,
                'unique_users': set()
            }

            if os.path.exists("user_activity.log"):
                with open("user_activity.log", "r", encoding="utf-8") as f:
                    for line in f:
                        if "LOGIN_ATTEMPT" in line:
                            stats['total_logins'] += 1
                            # Извлекаем user_id из строки
                            try:
                                user_part = line.split("User: ")[1].split(" ")[0]
                                stats['unique_users'].add(user_part)
                            except:
                                pass
                        elif "LOGIN_SUCCESS" in line:
                            stats['successful_logins'] += 1
                        elif "LOGIN_FAILED" in line:
                            stats['failed_logins'] += 1
                        elif "DOCUMENT_FILLED" in line:
                            stats['documents_filled'] += 1

            # Подсчитываем шаблоны
            templates = self.document_processor.get_available_templates()
            template_count = len(templates) if templates else 0

            # Подсчитываем заполненные документы
            filled_count = 0
            if os.path.exists("filled_documents"):
                filled_count = len([f for f in os.listdir("filled_documents") if f.endswith(('.jpg', '.png', '.jpeg'))])

            stats_text = f"""📈 **Статистика бота**

👥 **Пользователи:**
• Уникальных пользователей: {len(stats['unique_users'])}
• Всего попыток входа: {stats['total_logins']}
• Успешных входов: {stats['successful_logins']}
• Неудачных входов: {stats['failed_logins']}

📄 **Документы:**
• Доступных шаблонов: {template_count}
• Заполненных документов: {stats['documents_filled']}
• Сохраненных файлов: {filled_count}

🔐 **Система:**
• Текущих авторизованных: {len(self.auth_manager.authenticated_users)}
"""

            await message.answer(stats_text, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            await message.answer("❌ Ошибка при получении статистики.")

    async def start_polling(self):
        """Запуск бота"""
        logger.info("Запуск бота...")
        await self.dp.start_polling(self.bot)