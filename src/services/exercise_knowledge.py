"""Base de conhecimento de exercícios para inferência automática
"""
import logging

logger = logging.getLogger(__file__)

# Mapeamento: Exercício → Grupo Muscular Primário
EXERCISE_TO_MUSCLE = {

    # COSTAS
    "remada": "dorsais",
    "pulldown": "dorsais",
    "puxada": "dorsais",
    "barra fixa": "dorsais",
    "levantamento terra": "dorsais",
    "terra": "dorsais",
    "serrote": "dorsais",

    # OMBROS
    "desenvolvimento": "ombros",
    "elevacao lateral": "ombros",
    "elevacao frontal": "ombros",
    "crucifixo inverso": "ombros",
    "remada alta": "ombros",
    "encolhimento": "trapezio",

    # BRAÇOS
    "rosca": "biceps",
    "triceps": "triceps",
    "mergulho": "triceps",
    "frances": "triceps",
    "testa": "triceps",
    "corda": "triceps",
    "martelo": "biceps",
    "scott": "biceps",

    # PERNAS
    "agachamento": "quadriceps",
    "leg press": "quadriceps",
    "extensora": "quadriceps",
    "cadeira extensora": "quadriceps",
    "flexora": "isquiotibiais",
    "cadeira flexora": "isquiotibiais",
    "stiff": "isquiotibiais",
    "afundo": "quadriceps",
    "passada": "quadriceps",
    "bulgaro": "quadriceps",
    "panturrilha": "panturrilhas",
    "gemeo": "panturrilhas",

    # ABDOMEN
    "abdominal": "abdomen",
    "prancha": "abdomen",
    "obliquo": "abdomen",
    "crunch": "abdomen",

    # PEITO
    "supino": "peitoral",
    "crucifixo": "peitoral",
    "pullover": "peitoral",
    "crossover": "peitoral",
    "flexao": "peitoral",
    "press": "peitoral",
}

# Palavras-chave que indicam equipamento
EQUIPMENT_KEYWORDS = {
    "barra": ["barra", "livre"],
    "halteres": ["halteres", "halter", "dumbbell"],
    "maquina": ["maquina", "smith", "hack", "articulada"],
    "cabo": ["cabo", "polia", "crossover", "pulley"],
    "peso corporal": ["peso corporal", "livre", "barra fixa", "flexao", "mergulho", "paralelas"],
    "kettlebell": ["kettlebell", "girya"],
    "elastico": ["elastico", "band"],
}

def infer_muscle_group(exercise_name: str) -> str:
    """Infere o grupo muscular baseado no nome do exercício
    """
    exercise_lower = exercise_name.lower()
    logger.info(f"Exercício a ser inferido o musculo: {exercise_lower}")

    for keyword, muscle in EXERCISE_TO_MUSCLE.items():
        if keyword in exercise_lower:
            return muscle

    return "geral"  # Fallback

def infer_equipment(exercise_name: str) -> str:
    """Infere o equipamento baseado no nome do exercício
    """
    exercise_lower = exercise_name.lower()

    logger.info(f"Exercício a ser inferido o equipamento: {exercise_lower}")

    # Verificar palavras-chave explícitas
    for equipment, keywords in EQUIPMENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in exercise_lower:
                return equipment

    # Inferências baseadas em padrões
    if "cadeira" in exercise_lower or "leg press" in exercise_lower:
        return "maquina"

    if "livre" in exercise_lower or "olimpico" in exercise_lower:
        return "barra"

    # Fallback: se não tem indicação, provavelmente é máquina
    return "maquina"
