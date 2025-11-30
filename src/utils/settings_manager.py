# -*- coding: utf-8 -*-
"""
Gestor de Configuración (Settings).
Maneja la persistencia de las preferencias del usuario en un archivo JSON.
"""

import json
from pathlib import Path
from src.utils.logger import configurar_logger

logger = configurar_logger(__name__)

DIR_BASE = Path(__file__).resolve().parents[2] 
ARCHIVO_SETTINGS = DIR_BASE / "settings.json"

# Valores por defecto del sistema
CONFIG_POR_DEFECTO = {
    "auto_extract_enabled": False,
    "auto_extract_time": "08:00",
    "auto_update_enabled": False,
    "auto_update_time": "09:00",
    "user_export_path": "",
    "umbral_puntaje_minimo": 5
}

class GestorConfiguracion:
    def __init__(self, ruta_archivo=ARCHIVO_SETTINGS, defaults=CONFIG_POR_DEFECTO):
        self.ruta_archivo = ruta_archivo
        self.defaults = defaults
        self.config = self.cargar_configuracion()

    def cargar_configuracion(self) -> dict:
        """Lee el JSON de configuración o crea uno nuevo si no existe."""
        try:
            if self.ruta_archivo.exists():
                with open(self.ruta_archivo, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Migración: Asegurar que existan claves nuevas si actualizamos la app
                    cambios = False
                    for clave, valor in self.defaults.items():
                        if clave not in config:
                            config[clave] = valor
                            cambios = True
                    
                    if cambios:
                        self.guardar_configuracion(config)
                    return config
            else:
                logger.info("Archivo settings.json no encontrado. Creando valores por defecto.")
                self.guardar_configuracion(self.defaults)
                return self.defaults.copy()
        except Exception as e:
            logger.error(f"Error cargando configuración: {e}. Usando defaults.")
            return self.defaults.copy()

    def guardar_configuracion(self, config: dict):
        try:
            self.config = config
            with open(self.ruta_archivo, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            logger.error(f"Error guardando configuración: {e}")

    def obtener_valor(self, clave: str):
        return self.config.get(clave, self.defaults.get(clave))

    def establecer_valor(self, clave: str, valor):
        self.config[clave] = valor