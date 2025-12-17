from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any
from datetime import datetime

class ProductoSchema(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    cantidad: float = 0.0
    unidad_medida: Optional[str] = None

class LicitacionDetalleSchema(BaseModel):
    """
    Define el contrato de datos para el detalle de una licitación.
    Si los datos no cumplen este esquema, Pydantic lanzará un error controlado.
    """
    descripcion: Optional[str] = None
    direccion_entrega: Optional[str] = None
    fecha_cierre_p1: Optional[datetime] = None
    fecha_cierre_p2: Optional[datetime] = None
    productos_solicitados: List[ProductoSchema] = Field(default_factory=list)
    estado: Optional[str] = None
    cantidad_provedores_cotizando: Optional[int] = 0
    estado_convocatoria: Optional[int] = None
    plazo_entrega: Optional[int] = None
    organismo_nombre: Optional[str] = None
    monto_estimado: Optional[float] = 0.0
    fecha_publicacion: Optional[datetime] = None

    @field_validator('monto_estimado', mode='before')
    @classmethod
    def limpiar_monto(cls, v: Any) -> float:
        """Convierte strings de dinero ($ 1.500) a float puro (1500.0)."""
        if v is None:
            return 0.0
        if isinstance(v, (float, int)):
            return float(v)
        if isinstance(v, str):
            # Elimina símbolos de moneda y separadores de miles
            limpio = v.replace('$', '').replace('.', '').replace(',', '.')
            try:
                return float(limpio)
            except ValueError:
                return 0.0
        return 0.0