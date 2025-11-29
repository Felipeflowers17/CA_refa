# -*- coding: utf-8 -*-
"""
Configuración de la Sesión de Base de Datos (SQLAlchemy).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config.config import DATABASE_URL
from src.utils.logger import configurar_logger

logger = configurar_logger(__name__)

# --- Creación del Engine ---
try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Verifica la conexión antes de usarla (evita errores de desconexión)
        echo=False
    )
    logger.info("Engine de SQLAlchemy creado exitosamente.")
except Exception as e:
    logger.critical(f"Error al crear el engine de SQLAlchemy: {e}")
    raise e

# --- Fábrica de Sesiones ---
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
)