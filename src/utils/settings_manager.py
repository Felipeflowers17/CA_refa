# -*- coding: utf-8 -*-
"""
Gestor de Configuración.
Actualizado: Soporte para horarios específicos (HH:mm) en automatización.
"""

import json
from pathlib import Path
from src.utils.logger import configurar_logger

logger = configurar_logger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2] 
SETTINGS_FILE = BASE_DIR / "settings.json"

# Valores por defecto
DEFAULT_SETTINGS = {
    "auto_extract_enabled": False,
    "auto_extract_time": "08:00", # Hora por defecto
    "auto_update_enabled": False,
    "auto_update_time": "09:00",  # Hora por defecto
    "user_export_path": ""
}

class SettingsManager:
    def __init__(self, file_path=SETTINGS_FILE, defaults=DEFAULT_SETTINGS):
        self.file_path = file_path
        self.defaults = defaults
        self.config = self.load_settings()

    def load_settings(self) -> dict:
        try:
            if self.file_path.exists():
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Asegurar que existan todas las claves nuevas
                    for key, value in self.defaults.items():
                        config.setdefault(key, value)
                    return config
            else:
                logger.info("Creando settings.json con valores por defecto.")
                self.save_settings(self.defaults)
                return self.defaults.copy()
        except Exception as e:
            logger.error(f"Error cargando settings: {e}. Usando defaults.")
            return self.defaults.copy()

    def save_settings(self, config: dict):
        try:
            self.config = config
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            logger.error(f"Error guardando settings: {e}")

    def get_setting(self, key: str):
        return self.config.get(key, self.defaults.get(key))

    def set_setting(self, key: str, value):
        self.config[key] = value