import unittest
from unittest.mock import MagicMock

# Importamos los módulos refactorizados
from src.scraper import api_handler
from src.logic.score_engine import MotorPuntajes
from src.db.db_service import DbService

class TestRefactorizacion(unittest.TestCase):

    # --- 1. TEST LIMPIEZA (API Handler) ---
    def test_normalizar_datos_ficha_limpieza(self):
        """Valida que la nueva función en api_handler extraiga datos correctamente de un JSON sucio."""
        
        # Simulamos un JSON complejo/sucio como el que llega de la API
        payload_ejemplo = {
            'descripcion': 'Compra de Insumos Médicos',
            'informacion_institucion': {
                'organismo_comprador': 'Hospital Regional'
            },
            'estado': 'Publicada',
            'presupuesto_estimado': 500000,
            'fecha_publicacion': '2023-10-01',
            # Campos extra que deberían ser ignorados o procesados
            'CamposBasura': 'Info irrelevante' 
        }

        # Ejecutamos la función refactorizada
        resultado = api_handler.normalizar_datos_ficha(payload_ejemplo)

        # Verificaciones (Asserts)
        self.assertEqual(resultado['organismo_nombre'], 'Hospital Regional')
        self.assertEqual(resultado['estado'], 'Publicada')
        self.assertEqual(resultado['monto_estimado'], 500000)
        print("\n✅ API Handler (Limpieza): OK")

    # --- 2. TEST OPTIMIZACIÓN (Score Engine Cache) ---
    def test_score_engine_cache(self):
        """Valida que el lru_cache esté funcionando en normalizar_texto."""
        
        # Mockeamos el servicio de BD porque MotorPuntajes lo pide en __init__
        mock_db_service = MagicMock()
        motor = MotorPuntajes(mock_db_service)

        texto_dificil = "I. MUNICIPALIDAD DE CONCEPCIÓN"
        
        # Primera llamada (Procesa y guarda en caché)
        res1 = motor._normalizar_texto(texto_dificil)
        
        # Segunda llamada (Debe venir del caché instantáneamente)
        res2 = motor._normalizar_texto(texto_dificil)

        # Verificamos que la lógica funciona
        self.assertEqual(res1, "i. municipalidad de concepcion")
        self.assertEqual(res1, res2)

        # Verificamos que el caché está activo revisando sus estadísticas
        info_cache = motor._normalizar_texto.cache_info()
        # hits debe ser al menos 1 por la segunda llamada
        self.assertGreaterEqual(info_cache.hits, 1) 
        print(f"✅ Score Engine (Cache): OK (Hits: {info_cache.hits})")

    # --- 3. TEST DRY (DbService) ---
    def test_db_service_dry_exportacion(self):
        """Valida que exportar_candidatas use internamente el helper _ejecutar_exportacion."""
        
        mock_session_factory = MagicMock()
        servicio = DbService(mock_session_factory)

        # Simulamos (Mock) los métodos internos para no necesitar una BD real
        # Hacemos que obtener_candidatas_filtradas devuelva una lista falsa
        servicio.obtener_candidatas_filtradas = MagicMock(return_value=['dato1', 'dato2'])
        
        # Hacemos que el conversor devuelva diccionarios falsos
        servicio._convertir_a_diccionario_seguro = MagicMock(return_value=[{'id': 1}, {'id': 2}])

        # Ejecutamos el método público refactorizado
        resultado = servicio.exportar_candidatas()

        # Verificaciones
        # 1. Confirmamos que llamó a obtener_candidatas_filtradas
        servicio.obtener_candidatas_filtradas.assert_called_once()
        
        # 2. Confirmamos que llamó al conversor (prueba de que _ejecutar_exportacion funcionó)
        servicio._convertir_a_diccionario_seguro.assert_called_once()
        
        self.assertEqual(len(resultado), 2)
        print("✅ DbService (DRY): OK")

if __name__ == '__main__':
    unittest.main()