# -*- coding: utf-8 -*-
"""
Configuración de la Sesión de Base de Datos (SQLAlchemy).

Este módulo establece la conexión con la base de datos PostgreSQL y 
configura la fábrica de sesiones para el manejo de transacciones.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config.config import DATABASE_URL
from src.utils.logger import configurar_logger

logger = configurar_logger(__name__)

# --- Creación del Motor de Base de Datos (Engine) ---
try:
    engine = create_engine(
        DATABASE_URL,
        # 'pool_pre_ping': Verifica la conexión antes de usarla, 
        # recuperándose automáticamente de desconexiones del servidor.
        pool_pre_ping=True,  
        echo=False
    )
    logger.info("Motor SQLAlchemy (Engine) inicializado correctamente.")
except Exception as e:
    logger.critical(f"Error crítico al inicializar el motor de base de datos: {e}")
    raise e

# --- Fábrica de Sesiones ---
# SessionLocal se utilizará para instanciar sesiones de base de datos
# en cada hilo o petición de servicio.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
)