import unittest
from datetime import datetime
from src.logic.schemas import LicitacionDetalleSchema
from src.scraper import api_handler

class TestPydanticValidation(unittest.TestCase):

    def test_limpieza_montos(self):
        """Prueba que el validador limpie strings de dinero correctamente."""
        
        # Caso 1: Monto sucio con símbolo y punto de mil
        data_sucia = {"monto_estimado": "$ 1.500.000"}
        objeto = LicitacionDetalleSchema(**data_sucia)
        self.assertEqual(objeto.monto_estimado, 1500000.0)
        self.assertIsInstance(objeto.monto_estimado, float)

        # Caso 2: Monto con decimales y coma
        data_decimal = {"monto_estimado": "500,50"}
        objeto2 = LicitacionDetalleSchema(**data_decimal)
        self.assertEqual(objeto2.monto_estimado, 500.50)

        # Caso 3: Monto None/Nulo
        data_nula = {"monto_estimado": None}
        objeto3 = LicitacionDetalleSchema(**data_nula)
        self.assertEqual(objeto3.monto_estimado, 0.0)
        
        print("\n✅ Validación de Montos: OK")

    def test_integracion_api_handler(self):
        """Prueba que el api_handler devuelva un Objeto Schema y no un dict."""
        
        payload_realista = {
            'descripcion': 'Licitación de Prueba',
            'presupuesto_estimado': '$ 10.000', # Ojo: api_handler mapea esto a monto_estimado
            'estado': 'Publicada',
            'productos_solicitados': [{'nombre': 'PC', 'cantidad': 1}]
        }

        # Ejecutamos la función refactorizada
        resultado = api_handler.normalizar_datos_ficha(payload_realista)

        # Verificamos que NO sea un diccionario, sino una clase
        self.assertIsInstance(resultado, LicitacionDetalleSchema)
        
        # Verificamos que la limpieza ocurrió
        self.assertEqual(resultado.monto_estimado, 10000.0)
        self.assertEqual(resultado.descripcion, 'Licitación de Prueba')
        
        # Verificamos lista de productos (Pydantic la procesa como lista de objetos)
        self.assertEqual(len(resultado.productos_solicitados), 1)
        self.assertEqual(resultado.productos_solicitados[0].nombre, 'PC')

        print("✅ Integración API Handler -> Esquema: OK")

if __name__ == '__main__':
    unittest.main()