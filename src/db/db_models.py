# -*- coding: utf-8 -*-
"""
Modelos de la Base de Datos (SQLAlchemy ORM).

Este módulo define la estructura de las tablas de la base de datos utilizando
el sistema declarativo moderno de SQLAlchemy.
"""

import datetime
import enum  
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, JSON, ForeignKey, Enum, Text
)

class Base(DeclarativeBase):
    """Clase base para todos los modelos, define el mapeo de tipos JSON."""
    type_annotation_map = {
        Dict[str, Any]: JSON,
        List[Dict[str, Any]]: JSON,
        List[str]: JSON,  
    }

# --- Tablas de Jerarquía (Organización) ---

class CaSector(Base):
    """Representa el sector industrial al que pertenece un organismo."""
    __tablename__ = "ca_sector"
    
    sector_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    
    # Relaciones
    organismos: Mapped[List["CaOrganismo"]] = relationship(back_populates="sector")

class CaOrganismo(Base):
    """Representa una entidad pública que publica licitaciones."""
    __tablename__ = "ca_organismo"
    
    organismo_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(1000), unique=True, index=True)
    sector_id: Mapped[int] = mapped_column(ForeignKey("ca_sector.sector_id"))
    es_nuevo: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relaciones
    sector: Mapped["CaSector"] = relationship(back_populates="organismos", lazy="joined")
    licitaciones: Mapped[List["CaLicitacion"]] = relationship(back_populates="organismo")

# --- Tablas de Negocio (Licitaciones) ---

class CaLicitacion(Base):
    """
    Tabla Maestra. Almacena la información de cada oportunidad de negocio (Compra Ágil).
    Contiene datos extraídos (Fase 1 y Fase 2) y datos calculados (Puntajes).
    """
    __tablename__ = "ca_licitacion"
    
    ca_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_ca: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    
    # Datos informativos básicos
    nombre: Mapped[Optional[str]] = mapped_column(String(1000))
    descripcion: Mapped[Optional[str]] = mapped_column(String)
    monto_clp: Mapped[Optional[float]] = mapped_column(Float)
    
    # Fechas y Plazos
    fecha_publicacion: Mapped[Optional[datetime.date]] = mapped_column()
    fecha_cierre: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    fecha_cierre_segundo_llamado: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    plazo_entrega: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Estados
    estado_ca_texto: Mapped[Optional[str]] = mapped_column(String(255))
    estado_convocatoria: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    proveedores_cotizando: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Datos Detallados (Fase 2)
    direccion_entrega: Mapped[Optional[str]] = mapped_column(String(1000))
    productos_solicitados: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    
    # Motor de Puntuación
    puntuacion_final: Mapped[int] = mapped_column(Integer, default=0, index=True)
    puntaje_detalle: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    
    # Claves Foráneas y Relaciones
    organismo_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ca_organismo.organismo_id"))
    organismo: Mapped[Optional["CaOrganismo"]] = relationship(back_populates="licitaciones", lazy="joined")
    
    # Relación 1 a 1 con Seguimiento 
    seguimiento: Mapped["CaSeguimiento"] = relationship(back_populates="licitacion", cascade="all, delete-orphan", lazy="joined")

class CaSeguimiento(Base):
    """
    Tabla de Estado del Usuario. Separa la lógica de negocio (Favoritos/Ofertadas)
    de los datos crudos de la licitación.
    """
    __tablename__ = "ca_seguimiento"
    
    ca_id: Mapped[int] = mapped_column(ForeignKey("ca_licitacion.ca_id", ondelete="CASCADE"), primary_key=True)
    
    es_favorito: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    es_ofertada: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    es_oculta: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    licitacion: Mapped["CaLicitacion"] = relationship(back_populates="seguimiento")

# --- Tablas de Configuración (Reglas de Negocio) ---

class CaPalabraClave(Base):
    """
    Almacena las palabras clave (Keywords) que el usuario define para
    puntuar las licitaciones automáticamente.
    """
    __tablename__ = "ca_keyword" 
    
    keyword_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    keyword: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    
    # Configuración de puntos según dónde se encuentre la palabra
    puntos_nombre: Mapped[int] = mapped_column(Integer, default=0)
    puntos_descripcion: Mapped[int] = mapped_column(Integer, default=0)
    puntos_productos: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self):
        return f"<CaPalabraClave('{self.keyword}', N:{self.puntos_nombre}, D:{self.puntos_descripcion}, P:{self.puntos_productos})>"

class TipoReglaOrganismo(enum.Enum):
    """Enumeración para los tipos de reglas aplicables a organismos."""
    PRIORITARIO = 'prioritario'
    NO_DESEADO = 'no_deseado'
    NEUTRO = 'neutro'

class CaOrganismoRegla(Base):
    """
    Configuración específica para un organismo (ej: Cliente VIP o Competencia).
    """
    __tablename__ = "ca_organismo_regla"
    
    regla_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organismo_id: Mapped[int] = mapped_column(ForeignKey("ca_organismo.organismo_id", ondelete="CASCADE"), unique=True, index=True)
    
    tipo: Mapped[TipoReglaOrganismo] = mapped_column(Enum(TipoReglaOrganismo, name='tipo_regla_organismo_enum', native_enum=False), nullable=False, index=True)
    puntos: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    organismo: Mapped["CaOrganismo"] = relationship(lazy="joined")