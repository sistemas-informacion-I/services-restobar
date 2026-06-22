import os
import json
import logging
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

from app.services.catalog import ReportCatalog

logger = logging.getLogger(__name__)
load_dotenv()

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client

    try:
        from google import genai
        from google.genai.types import HttpOptions

        project_id = os.getenv("GCP_PROJECT_ID", "project-5ed4e5c6-d00d-4ed4-86c")
        location = os.getenv("GCP_LOCATION", "global")

        _client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
            http_options=HttpOptions(api_version="v1"),
        )
        logger.info("Gemini client: project=%s, location=%s", project_id, location)
        return _client

    except ImportError:
        raise ImportError(
            "google-genai no está instalado. Ejecuta: pip install google-genai"
        )


MODEL_NAME = "gemini-3.5-flash"


class ReportAIService:

    @staticmethod
    def _get_catalog_description() -> str:
        catalog = ReportCatalog()
        lines = []
        for r in catalog.all():
            lines.append(
                f"Tipo de Reporte (reportType): '{r.key}' "
                f"(Etiqueta: {r.label}, Categoría: {r.category.value})"
            )
            lines.append("Campos/Columnas permitidas:")
            for field in r.fields.values():
                lines.append(
                    f"  - '{field.key}' ({field.label}) "
                    f"[Tipo: {field.type.value}, Tipo de Campo: {field.kind.value}]"
                )
            lines.append("")
        return "\n".join(lines)

    @classmethod
    def parse_prompt(cls, prompt: str) -> Optional[dict]:
        catalog_desc = cls._get_catalog_description()

        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        year = now.year
        month_names = [
            "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
        ]
        dow_names = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        day_of_week = dow_names[now.weekday()]
        month_name = month_names[now.month]
        first_day_month = f"{year}-{now.month:02d}-01"

        instruction = (
            f"CONTEXTO TEMPORAL:\n"
            f"- Fecha actual: {today_str} ({day_of_week} {now.day} de {month_name} de {year})\n"
            f"- Año actual: {year}\n"
            f"- Mes actual: {now.month:02d} ({month_name})\n"
            f"- Primer día del mes actual: {first_day_month}\n\n"
            "Eres un asistente experto en análisis de datos para un sistema de gestión "
            "de restaurante (ventas, productos, comandas, caja, reservas, proveedores, "
            "empleados, inventario, mesas, métodos de pago).\n"
            "Interpreta la solicitud del usuario en español y tradúcela a JSON.\n\n"
            "CATÁLOGO DE REPORTES:\n"
            f"{catalog_desc}\n\n"
            "PASO 1 - SELECCIONAR REPORTE:\n"
            "Elige el 'reportType' más adecuado. Algunos ejemplos:\n"
            "- 'ventas del día' -> 'ventas'\n"
            "- 'ventas por producto' -> 'ventas_por_producto'\n"
            "- 'pedidos activos' -> 'comandas'\n"
            "- 'cierre de caja' -> 'caja'\n"
            "- 'reservas de hoy' -> 'reservas'\n"
            "- 'estado de mesas' -> 'mesas'\n"
            "- 'compras realizadas' -> 'compras'\n"
            "- 'proveedores registrados' -> 'proveedores'\n\n"
            "PASO 2 - COLUMNAS (selectedFields):\n"
            "Selecciona los campos solicitados. Deben existir en el catálogo del reporte.\n"
            "Si el usuario no especifica, elige 3-5 campos clave.\n\n"
            "PASO 3 - FILTROS (filters):\n"
            "Cada filtro es un objeto {field, operator, value}.\n"
            "Operadores (siempre en MAYÚSCULAS):\n"
            "- 'igual a', 'es', 'del estado' -> 'EQ'\n"
            "- 'diferente de', 'no es' -> 'NE'\n"
            "- 'mayor que' -> 'GT'\n"
            "- 'menor que' -> 'LT'\n"
            "- 'mayor o igual que' -> 'GTE'\n"
            "- 'menor o igual que' -> 'LTE'\n"
            "- 'que contenga', 'contiene', 'como' -> 'LIKE'\n"
            "- 'es nulo', 'no tiene', 'vacío' -> 'IS_NULL' (NO incluir campo value)\n"
            "- 'no es nulo', 'tiene', 'no vacío' -> 'IS_NOT_NULL' (NO incluir campo value)\n\n"
            "VALORES POR TIPO DE CAMPO:\n"
            "- Campo STRING: value = texto entre comillas. Ej: \"PAGADA\", \"Juan\"\n"
            "- Campo NUMBER: value = número sin comillas. Ej: 5, 100.50\n"
            "- Campo DATE: value = 'YYYY-MM-DD'. Ej: '2026-06-22'\n"
            "- Campo BOOLEAN: value = 'true' o 'false' (string). Ej: 'true'\n\n"
            "PASO 4 - FECHAS RELATIVAS:\n"
            "Para expresiones como 'hoy', 'ayer', 'esta semana', 'este mes':\n"
            "Usa 'dateFrom' y 'dateTo' (formato 'YYYY-MM-DD'). NO uses filtros sobre campos de fecha.\n"
            f"- 'hoy' -> dateFrom='{today_str}', dateTo='{today_str}'\n"
            f"- 'ayer' -> dateFrom='{(now - __import__('datetime').timedelta(days=1)).strftime('%Y-%m-%d')}', "
            f"dateTo='{(now - __import__('datetime').timedelta(days=1)).strftime('%Y-%m-%d')}'\n"
            f"- 'esta semana' -> dateFrom='{(now - __import__('datetime').timedelta(days=now.weekday())).strftime('%Y-%m-%d')}', "
            f"dateTo='{(now + __import__('datetime').timedelta(days=6 - now.weekday())).strftime('%Y-%m-%d')}'\n"
            f"- 'este mes' -> dateFrom='{first_day_month}', dateTo='{now.strftime('%Y-%m-%d')}'\n"
            f"- 'últimos 30 días' -> dateFrom='{(now - __import__('datetime').timedelta(days=30)).strftime('%Y-%m-%d')}', "
            f"dateTo='{today_str}'\n"
            f"- 'este año' -> dateFrom='{year}-01-01', dateTo='{today_str}'\n"
            f"- 'mes pasado' -> dateFrom='{(now.replace(day=1) - __import__('datetime').timedelta(days=1)).replace(day=1).strftime('%Y-%m-%d')}', "
            f"dateTo='{(now.replace(day=1) - __import__('datetime').timedelta(days=1)).strftime('%Y-%m-%d')}'\n\n"
            "PASO 5 - ORDEN Y LÍMITE:\n"
            "- Si el usuario pide orden ('los más vendidos', 'los más caros'), usa sortField + sortOrder.\n"
            "- Si pide cantidad ('top 5', 'los primeros 10'), usa limit.\n"
            "- Si pide 'los últimos registrados', ordena por fecha descendente (sortOrder: 'desc').\n\n"
            "FORMATO DE SALIDA: Solo el objeto JSON, sin texto adicional.\n\n"
            "Ejemplo:\n"
            "{\n"
            '  "reportType": "ventas",\n'
            '  "selectedFields": ["fechaEmision", "total", "estado", "clienteNombre"],\n'
            '  "filters": [\n'
            '    {"field": "estado", "operator": "EQ", "value": "PAGADA"},\n'
            '    {"field": "total", "operator": "GT", "value": 50}\n'
            "  ],\n"
            f'  "dateFrom": "{today_str}",\n'
            f'  "dateTo": "{today_str}",\n'
            '  "sortField": "total",\n'
            '  "sortOrder": "desc",\n'
            '  "limit": 20,\n'
            '  "offset": 0\n'
            "}"
        )

        try:
            client = _get_client()
            from google.genai.types import GenerateContentConfig

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[instruction, f"Solicitud del usuario: {prompt}"],
                config=GenerateContentConfig(
                    temperature=0.1,
                    top_p=0.8,
                    response_mime_type="application/json",
                ),
            )

            raw_text = (response.text or "").strip()
            if not raw_text:
                raw_text = "{}"
            if raw_text.startswith("```"):
                raw_text = raw_text.strip("`")
                if raw_text.lower().startswith("json"):
                    raw_text = raw_text[4:].strip()

            start = raw_text.find("{")
            end = raw_text.rfind("}")
            if start != -1 and end != -1 and end > start:
                raw_text = raw_text[start : end + 1]

            result_dict = json.loads(raw_text)
            return result_dict

        except Exception as e:
            logger.exception("Error al parsear el prompt con Gemini: %s", e)
            return None

    @classmethod
    def transcribe_audio(cls, file_bytes: bytes, filename: str) -> Optional[str]:
        try:
            client = _get_client()
            from google.genai.types import GenerateContentConfig, Part

            suffix = os.path.splitext(filename)[1] or ".webm"
            mime_map = {
                ".webm": "audio/webm",
                ".mp3": "audio/mpeg",
                ".wav": "audio/wav",
                ".ogg": "audio/ogg",
                ".m4a": "audio/mp4",
            }
            mime_type = mime_map.get(suffix, "audio/webm")

            audio_part = Part.from_bytes(data=file_bytes, mime_type=mime_type)

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[
                    "Por favor, transcribe este audio en español. "
                    "Solo devuelve la transcripción literal, nada de texto adicional.",
                    audio_part,
                ],
                config=GenerateContentConfig(
                    temperature=0.1,
                ),
            )

            transcript = (response.text or "").strip()
            if transcript:
                logger.info("Transcripción exitosa: %s", transcript)
            return transcript or None

        except Exception as e:
            logger.exception("Error al transcribir audio con Gemini: %s", e)
            return None
