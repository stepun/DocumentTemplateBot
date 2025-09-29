from PIL import Image, ImageDraw, ImageFont
import json
import os
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self, templates_dir: str = "templates", config_dir: str = "config"):
        self.templates_dir = templates_dir
        self.config_dir = config_dir
        self.default_font_size = 24

    def get_available_templates(self) -> List[str]:
        """Получить список доступных шаблонов"""
        templates = []
        if os.path.exists(self.templates_dir):
            for file in os.listdir(self.templates_dir):
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    templates.append(file)
        return templates

    def load_template_config(self, template_name: str) -> Optional[Dict]:
        """Загрузить конфигурацию полей для шаблона"""
        config_file = os.path.join(self.config_dir, f"{template_name}.json")
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Ошибка загрузки конфигурации {config_file}: {e}")
        return None

    def save_template_config(self, template_name: str, config: Dict) -> bool:
        """Сохранить конфигурацию полей для шаблона"""
        os.makedirs(self.config_dir, exist_ok=True)
        config_file = os.path.join(self.config_dir, f"{template_name}.json")
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации {config_file}: {e}")
            return False

    def fill_document(self, template_name: str, data: Dict[str, str], output_path: str) -> bool:
        """
        Заполнить документ данными

        Args:
            template_name: имя файла шаблона
            data: словарь с данными для заполнения {'field_name': 'value'}
            output_path: путь для сохранения результата
        """
        try:
            # Загружаем изображение шаблона
            template_path = os.path.join(self.templates_dir, template_name)
            if not os.path.exists(template_path):
                logger.error(f"Шаблон не найден: {template_path}")
                return False

            image = Image.open(template_path)
            draw = ImageDraw.Draw(image)

            # Загружаем конфигурацию полей
            config = self.load_template_config(template_name)
            if not config:
                logger.error(f"Конфигурация не найдена для шаблона: {template_name}")
                return False

            # Заполняем поля
            for field_name, field_config in config.get('fields', {}).items():
                if field_name in data:
                    self._draw_text(
                        draw=draw,
                        text=data[field_name],
                        position=(field_config['x'], field_config['y']),
                        font_size=field_config.get('font_size', self.default_font_size),
                        color=field_config.get('color', '#000000')
                    )

            # Сохраняем результат
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            image.save(output_path, quality=95)
            logger.info(f"Документ сохранен: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Ошибка заполнения документа: {e}")
            return False

    def _draw_text(self, draw: ImageDraw.Draw, text: str, position: Tuple[int, int],
                   font_size: int, color: str = '#000000'):
        """Нарисовать текст на изображении"""
        try:
            # Пытаемся найти подходящий шрифт с поддержкой кириллицы
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
                "/System/Library/Fonts/Arial.ttf",
                "/Windows/Fonts/arial.ttf",
                "arial.ttf"
            ]

            font = None
            for font_path in font_paths:
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    break
                except:
                    continue

            if font is None:
                # Если не удалось загрузить TrueType шрифт, используем базовый
                font = ImageFont.load_default()
                logger.warning("Используется базовый шрифт, кириллица может отображаться некорректно")

            # Рисуем текст с поддержкой кириллицы
            draw.text(position, text, fill=color, font=font)

        except Exception as e:
            logger.error(f"Ошибка рисования текста: {e}")
            # Fallback - рисуем без шрифта
            try:
                draw.text(position, text, fill=color)
            except Exception as fallback_error:
                logger.error(f"Критическая ошибка рисования текста: {fallback_error}")

    def create_template_config(self, template_name: str, fields: Dict[str, Dict]) -> bool:
        """
        Создать конфигурацию для нового шаблона

        Args:
            template_name: имя файла шаблона
            fields: словарь полей {'field_name': {'x': int, 'y': int, 'font_size': int, 'color': str}}
        """
        config = {
            'template_name': template_name,
            'fields': fields,
            'created_at': '2024-01-01'
        }
        return self.save_template_config(template_name, config)