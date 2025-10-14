import json
import logging
from typing import Any, Dict

from groq import AsyncGroq

from config.settings import settings
from services.exceptions import LLMParsingError, ServiceUnavailableError, ValidationError

logger = logging.getLogger(__name__)


class LLMParsingService:
    """Serviço para parsear transcrições usando Groq API"""

    def __init__(self) -> None:
        if not settings.GROQ_API_KEY:
            raise ServiceUnavailableError(
                "GROQ_API_KEY não configurada",
                "Configure a variável de ambiente GROQ_API_KEY",
            )

        try:
            self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
            self.model = settings.LLM_MODEL
            logger.info(f"LLM Service inicializado: {self.model} (Async Groq API)")
        except Exception as e:
            raise ServiceUnavailableError(
                "Falha ao inicializar cliente Groq LLM",
                f"Erro: {e!s}",
            )

    async def parse_workout(self, transcription: str) -> Dict[str, Any]:
        """Parse uma transcrição de treino usando Groq API
        
        Args:
            transcription: Texto transcrito do áudio
            
        Returns:
            Dict com dados estruturados do treino
            
        Raises:
            ValidationError: Se a transcrição é inválida
            LLMParsingError: Se o parsing falhar
            ServiceUnavailableError: Se o serviço Groq estiver indisponível

        """
        if not transcription or not transcription.strip():
            raise ValidationError("Transcrição vazia ou inválida")

        if len(transcription) > settings.MAX_TRANSCRIPTION_LENGTH:
            raise ValidationError(f"Transcrição muito longa (máximo {settings.MAX_TRANSCRIPTION_LENGTH:,} caracteres)")

        prompt = self._build_prompt(transcription)

        logger.info(f"Enviando transcrição para Groq API ({self.model})...")

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": prompt,
                }],
                temperature=settings.LLM_TEMPERATURE,
                max_completion_tokens=settings.LLM_MAX_TOKENS,
            )

            if not response.choices or not response.choices[0].message:
                raise LLMParsingError(
                    "Resposta vazia do LLM",
                    "O modelo não retornou uma resposta válida",
                )

            content = response.choices[0].message.content
            if not content:
                raise LLMParsingError(
                    "Conteúdo vazio na resposta do LLM",
                    "O modelo retornou uma resposta vazia",
                )

            # Limpar markdown se presente
            content = content.replace("```json", "").replace("```", "").strip()

            # Parsear JSON
            try:
                parsed_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Erro ao parsear JSON: {e}")
                logger.error(f"Resposta do Groq: {content[:500]}...")
                raise LLMParsingError(
                    "Resposta do LLM não é JSON válido",
                    f"Erro de parsing: {e!s}",
                )

            # Validar estrutura básica
            if not isinstance(parsed_data, dict):
                raise LLMParsingError(
                    "Resposta do LLM deve ser um objeto JSON",
                    f"Recebido: {type(parsed_data)}",
                )

            logger.info("Groq API parseou com sucesso!")
            return parsed_data

        except (ValidationError, LLMParsingError):
            # Re-raise custom exceptions
            raise
        except Exception as e:
            if "rate_limit" in str(e).lower():
                raise ServiceUnavailableError(
                    "Limite de taxa do Groq API excedido",
                    "Tente novamente em alguns segundos",
                )
            if "unauthorized" in str(e).lower():
                raise ServiceUnavailableError(
                    "Chave API Groq inválida",
                    "Verifique a configuração GROQ_API_KEY",
                )
            logger.exception("Erro inesperado no LLM parsing")
            raise LLMParsingError(
                "Erro inesperado no parsing",
                f"Erro interno: {e!s}",
            )

    def _build_prompt(self, transcription: str) -> str:
        """Constrói o prompt para o LLM"""
        return f"""Você é um assistente especializado em fitness brasileiro. Extraia informações do seguinte treino:

"{transcription}"

IMPORTANTE sobre NOMES DE EXERCÍCIOS:
- Preserve SEMPRE as variações e qualificadores: "supino reto", "supino inclinado", "supino declinado"
- Preserve ângulos: "leg press 45 graus", "supino 30 graus"
- Preserve tipos: "rosca direta", "rosca martelo", "rosca scott"
- Preserve equipamentos: "agachamento livre", "agachamento smith", "leg press"
- Use APENAS português brasileiro
- Normalize para minúsculas
- Caso erro de escrita, tente achar o exercício mais próximo utilizando fuzzy

EQUIPAMENTOS que devem ser SEMPRE mencionados quando usados:
- "com barra" (barra livre olímpica)
- "com halteres" (dumbbells, pesos individuais)
- "na máquina" ou nome específico da máquina (smith, hack, etc)
- "no cabo" ou "na polia"
- "peso corporal" (sem equipamento)

EXEMPLOS DE NOMES CORRETOS:

❌ ERRADO (genérico):
- "supino" → Faltou: qual equipamento?
- "rosca" → Faltou: qual tipo e equipamento?
- "leg press" → OK, nome da máquina já é específico

✅ CERTO (específico):
- "supino reto com barra"
- "supino inclinado com halteres"
- "rosca direta com barra"
- "rosca martelo com halteres"
- "desenvolvimento na máquina"
- "tríceps na polia com corda"
- "flexão de braço peso corporal"
- "agachamento livre com barra" (livre = não é smith)
- "leg press 45 graus" (já específico)



REGRAS DE NOMENCLATURA:
1. Se mencionou "com barra", "com halteres", etc → mantenha no nome
2. Se NÃO mencionou equipamento:
   - Exercícios com barra livre (supino, agachamento, terra) → assume "com barra"
   - Exercícios em máquina (leg press, cadeira, polia) → use nome da máquina
   - Exercícios com halteres típicos (rosca alternada, elevação) → "com halteres"
3. Para rosca: se não especificou, assume "rosca direta"
4. Para supino: se não especificou, assume "supino reto com barra"
5. Para agachamento: se não especificou, assume "agachamento livre com barra"

INFERÊNCIAS DE EQUIPAMENTO por padrão:
- "supino" sem especificar → "supino reto com barra"
- "rosca" sem especificar → "rosca direta com barra"
- "desenvolvimento" sem especificar → "desenvolvimento com barra"
- "agachamento" sem especificar → "agachamento livre com barra"
- "leg press" → "leg press 45 graus" (se não especificou ângulo)
- "cadeira extensora/flexora" → nome já é específico
- "puxada" ou "pulldown" → "puxada alta no cabo"
- "remada baixa" → "remada baixa no cabo"
- "tríceps" → precisa especificar: "tríceps na polia", "tríceps testa com barra", etc

IMPORTANTE sobre PESOS:
- Se mencionou DIFERENTES pesos para cada série, use um array: "weights_kg": [10, 15, 20]
- Se mencionou MESMO peso para todas as séries, repita no array: "weights_kg": [60, 60, 60]
- O tamanho do array weights_kg DEVE ser igual ao número de séries

EXEMPLOS DE PARSING DE PESOS:

Exemplo 1 - Pesos diferentes (pirâmide crescente):
Entrada: "3 séries de 12, 10, 8 com 10, 15 e 20 kg"
Saída: {{"sets": 3, "reps": [12, 10, 8], "weights_kg": [10, 15, 20]}}

Exemplo 2 - Pesos diferentes (pirâmide decrescente):
Entrada: "4 séries de 8, 10, 12, 12 com 80, 70, 60, 60 kg"
Saída: {{"sets": 4, "reps": [8, 10, 12, 12], "weights_kg": [80, 70, 60, 60]}}

Exemplo 3 - Mesmo peso para todas:
Entrada: "3 séries de 12 com 60 kg"
Saída: {{"sets": 3, "reps": [12, 12, 12], "weights_kg": [60, 60, 60]}}

Exemplo 4 - Dropset:
Entrada: "3 séries de 10 repetições, primeira com 50kg, segunda com 40kg, terceira com 30kg"
Saída: {{"sets": 3, "reps": [10, 10, 10], "weights_kg": [50, 40, 30]}}

EXEMPLOS CORRETOS:
❌ ERRADO: {{"name": "supino"}} (muito genérico!)
✅ CERTO: {{"name": "supino reto"}} (específico)

❌ ERRADO: {{"name": "rosca"}} (qual rosca?)
✅ CERTO: {{"name": "rosca direta"}} (específica)

❌ ERRADO: {{"name": "leg press"}} (qual variação?)
✅ CERTO: {{"name": "leg press 45 graus"}} (específico)


IMPORTANTE sobre DESCANSO:
- Extraia tempo de descanso entre séries se mencionado
- Converta para segundos: "1 minuto" → 60, "30 segundos" → 30, "1 min e meio" → 90
- Se não mencionado, deixe null

IMPORTANTE sobre DIFICULDADE (RPE - Rate of Perceived Exertion):
- Escala de 1 a 10, onde:
  * 1-2: Muito fácil
  * 3-4: Fácil
  * 5-6: Moderado
  * 7-8: Difícil/Pesado
  * 9-10: Muito difícil/Máximo esforço
- Palavras-chave que indicam dificuldade:
  * "fácil", "tranquilo", "leve" → RPE 3-4
  * "pesado", "difícil", "puxado" → RPE 7-8
  * "muito pesado", "quase não consegui", "à falha" → RPE 9-10
  * "confortável", "bom" → RPE 5-6
- Se não mencionado, deixe null

EXEMPLOS DE PARSING:

Exemplo 1 - Completo com descanso e dificuldade:
Entrada: "Supino reto 3 séries de 12, 10, 8 com 40, 50, 60 kg, 1 minuto de descanso, estava bem pesado"
Saída: {{
  "name": "supino reto",
  "sets": 3,
  "reps": [12, 10, 8],
  "weights_kg": [40, 50, 60],
  "rest_seconds": 60,
  "perceived_difficulty": 8
}}

Exemplo 2 - Com descanso diferente:
Entrada: "Agachamento 4x10 com 100kg, descansando 2 minutos, bem puxado"
Saída: {{
  "name": "agachamento livre",
  "sets": 4,
  "reps": [10, 10, 10, 10],
  "weights_kg": [100, 100, 100, 100],
  "rest_seconds": 120,
  "perceived_difficulty": 8
}}

Exemplo 3 - Fácil:
Entrada: "Rosca direta 3x15 com 10kg, 45 segundos de intervalo, estava bem leve"
Saída: {{
  "name": "rosca direta",
  "sets": 3,
  "reps": [15, 15, 15],
  "weights_kg": [10, 10, 10],
  "rest_seconds": 45,
  "perceived_difficulty": 3
}}

Exemplo 4 - Sem descanso/dificuldade mencionados:
Entrada: "Leg press 3x12 com 150kg"
Saída: {{
  "name": "leg press 45 graus",
  "sets": 3,
  "reps": [12, 12, 12],
  "weights_kg": [150, 150, 150],
  "rest_seconds": null,
  "perceived_difficulty": null
}}

Exemplo 5 - À falha muscular:
Entrada: "Desenvolvimento 3 séries de 10, 8, 6 com 30kg, indo até a falha, bem difícil"
Saída: {{
  "name": "desenvolvimento",
  "sets": 3,
  "reps": [10, 8, 6],
  "weights_kg": [30, 30, 30],
  "rest_seconds": null,
  "perceived_difficulty": 9
}}

{{
  "body_weight_kg": float ou null,
  "energy_level": int de 1-10 ou null,
  "start_time": "HH:MM" ou null,
  "end_time": "HH:MM" ou null,
  "resistance_exercises": [
    {{
      "name": "nome COMPLETO e ESPECÍFICO com equipamento em minúsculas",
      "sets": número de séries,
      "reps": [array com repetições de cada série],
      "weight_kg": [array com peso de cada série - obrigatório]
      "rest_seconds": tempo de descanso em segundos ou null,
      "perceived_difficulty": RPE de 1-10 ou null,
      "notes": null
    }}
  ],
  "aerobic_exercises": [
    {{
      "name": "nome do exercício em minúsculas",
      "duration_minutes": duração,
      "distance_km": distância ou null,
      "average_heart_rate": frequência cardíaca média ou null,
      "calories_burned": calorias queimadas ou null,
      "intensity_level": "low|moderate|high|hiit",
      "notes": null
    }}
  ],
  "notes": null
}}


EXEMPLOS COMPLETOS:

Entrada: "Fiz 3 séries de supino com 60kg"
Saída: {{"name": "supino reto com barra", "sets": 3, "reps": [3,3,3], "weights_kg": [60,60,60]}}

Entrada: "Rosca alternada 3x12 com 12kg"
Saída: {{"name": "rosca alternada com halteres", "sets": 3, "reps": [12,12,12], "weights_kg": [12,12,12]}}

Entrada: "Leg press 4 séries de 15 com 200kg"
Saída: {{"name": "leg press 45 graus", "sets": 4, "reps": [15,15,15,15], "weights_kg": [200,200,200,200]}}

Entrada: "Tríceps na polia 3x15"
Saída: {{"name": "tríceps na polia com corda", "sets": 3, "reps": [15,15,15]}}

EXEMPLOS DE EXERCÍCIOS AERÓBICOS:

Entrada: "Corri 30 minutos na esteira"
Saída: {{"name": "corrida na esteira", "duration_minutes": 30, "distance_km": null, "average_heart_rate": null, "calories_burned": null, "intensity_level": "moderate"}}

Entrada: "Fiz 45 minutos de bicicleta, queimei 350 calorias"
Saída: {{"name": "bicicleta ergométrica", "duration_minutes": 45, "distance_km": null, "average_heart_rate": null, "calories_burned": 350, "intensity_level": "moderate"}}

Entrada: "Caminhei 5km em 1 hora, frequência cardíaca média de 140 bpm"
Saída: {{"name": "caminhada", "duration_minutes": 60, "distance_km": 5, "average_heart_rate": 140, "calories_burned": null, "intensity_level": "moderate"}}

Entrada: "Spinning 30 minutos, FC média 165, queimei 280 calorias"
Saída: {{"name": "spinning", "duration_minutes": 30, "distance_km": null, "average_heart_rate": 165, "calories_burned": 280, "intensity_level": "high"}}

Entrada: "Natação 20 minutos intenso"
Saída: {{"name": "natação", "duration_minutes": 20, "distance_km": null, "average_heart_rate": null, "calories_burned": null, "intensity_level": "high"}}

IMPORTANTE sobre EXERCÍCIOS AERÓBICOS:
- Se mencionou "calorias", "kcal", "cal" → extrair para "calories_burned"
- Se mencionou "frequência cardíaca", "FC", "bpm", "batimentos" → extrair para "average_heart_rate"
- Se mencionou distância em "km", "quilômetros", "metros" → converter para km e usar "distance_km"
- Intensidade: "leve/fácil" = low, "moderado/normal" = moderate, "intenso/pesado/difícil" = high, "intervalado/HIIT" = hiit
- Sempre transforme "corrida na rua" em "corrida de rua", mesmo coisa para corrida livre em corrida de rua, corrida ao
  ar livre em corrida de rua. Serve também para caminha 

 SEMPRE use "weights_kg" como array (nunca "weight_kg" singular)
- O array weights_kg DEVE ter o mesmo tamanho que o número de séries
- Se não especificar variação e for supino, assuma "supino reto"
- Se não especificar variação e for agachamento, assuma "agachamento livre"
- "3 séries de 12, 10, 8" → {{"sets": 3, "reps": [12, 10, 8]}}
- "4x15" → {{"sets": 4, "reps": [15, 15, 15, 15]}}
- Se campo não mencionado, use null
- Não invente dados

Retorne APENAS o JSON, sem texto adicional."""

# Service instantiation moved to container.py
# This module only defines the service class
