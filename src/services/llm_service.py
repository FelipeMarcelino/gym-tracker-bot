import json
from typing import Any, Dict

import ollama

from config.settings import settings


class LLMParsingService:
    """Serviço para parsear transcrições usando LLM local (Ollama)"""

    def __init__(self, model: str, host: str):
        self.model = model
        self.host = host
        print(f"🤖 LLM Service inicializado: {model}")

    def parse_workout(self, transcription: str) -> Dict[str, Any]:
        """Parse uma transcrição de treino usando LLM
        
        Args:
            transcription: Texto transcrito do áudio
            
        Returns:
            Dict com dados estruturados do treino

        """
        prompt = self._build_prompt(transcription)

        print(f"🤖 Enviando para LLM ({self.model})...")

        try:
            response = ollama.chat(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": prompt,
                }],
            )

            content = response["message"]["content"]

            # Limpar markdown se presente
            content = content.replace("```json", "").replace("```", "").strip()

            # Parsear JSON
            parsed_data = json.loads(content)

            print("✅ LLM parseou com sucesso!")
            return parsed_data

        except json.JSONDecodeError as e:
            print(f"❌ Erro ao parsear JSON do LLM: {e}")
            print(f"Resposta do LLM: {content[:200]}...")
            return {}
        except Exception as e:
            print(f"❌ Erro no LLM: {e}")
            return {}

    def _build_prompt(self, transcription: str) -> str:
        """Constrói o prompt para o LLM"""
        return f"""Você é um assistente especializado em fitness. Extraia informações estruturadas do seguinte relato de treino em português:

"{transcription}"

IMPORTANTE: Retorne APENAS um JSON válido (sem markdown, sem explicações, sem texto adicional).

Formato esperado:
{{
  "body_weight_kg": float ou null,
  "energy_level": int de 1-10 ou null,
  "start_time": "HH:MM" ou null,
  "end_time": "HH:MM" ou null,
  "resistance_exercises": [
    {{
      "name": "nome do exercício em minúsculas",
      "sets": número de séries,
      "reps": [repetições por série],
      "weight_kg": carga em kg,
      "notes": "observações ou null"
    }}
  ],
  "aerobic_exercises": [
    {{
      "name": "nome do exercício em minúsculas",
      "duration_minutes": duração em minutos,
      "distance_km": distância em km ou null,
      "intensity_level": "low" ou "moderate" ou "high" ou "hiit",
      "notes": "observações ou null"
    }}
  ],
  "notes": "observações gerais ou null"
}}

Regras:
- Se um campo não foi mencionado, use null
- Nomes de exercícios em minúsculas: "supino", "agachamento", "corrida"
- Se ouvir "3x12", significa 3 séries de 12 repetições: {{"sets": 3, "reps": [12, 12, 12]}}
- Se ouvir "3 séries de 12, 10 e 8", use: {{"sets": 3, "reps": [12, 10, 8]}}
- Não invente dados que não foram mencionados
- Retorne APENAS o JSON, sem texto antes ou depois"""

# Instância global
_llm_service = None

def get_llm_service() -> LLMParsingService:
    """Retorna instância única do serviço de LLM"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMParsingService(
            model=settings.LLM_MODEL,
            host=settings.OLLAMA_HOST,
        )
    return _llm_service
