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

# Mapeamento: Exercício Aeróbico → Grupo Muscular Primário
AEROBIC_TO_MUSCLE = {
    # CARDIO GERAL (corpo todo)
    "corrida de rua": "cardiorespiratorio",
    "caminhada de rua": "cardiorespiratorio",
    "corrida": "cardiorespiratorio",
    "caminhada": "cardiorespiratorio",
    "trote": "cardiorespiratorio",
    "maratona": "cardiorespiratorio",
    "running": "cardiorespiratorio",

    # CICLISMO
    "bicicleta": "quadriceps",
    "bike": "quadriceps",
    "ciclismo": "quadriceps",
    "spinning": "quadriceps",
    "ergometrica": "quadriceps",

    # NATAÇÃO
    "natacao": "corpo_todo",
    "piscina": "corpo_todo",
    "crawl": "corpo_todo",
    "costas": "dorsais",
    "peito": "peitoral",
    "borboleta": "corpo_todo",

    # REMO
    "remo": "dorsais",
    "ergometro": "dorsais",

    # ELÍPTICO/STEP
    "eliptico": "cardiorespiratorio",
    "step": "quadriceps",
    "stepper": "quadriceps",

    # ESTEIRA/EQUIPAMENTOS
    "esteira": "cardiorespiratorio",
    "transport": "cardiorespiratorio",

    # DANÇA/AERÓBICA
    "zumba": "cardiorespiratorio",
    "aerobica": "cardiorespiratorio",
    "danca": "cardiorespiratorio",
    "jump": "quadriceps",

    # ESPORTES
    "futebol": "cardiorespiratorio",
    "basquete": "cardiorespiratorio",
    "tenis": "cardiorespiratorio",
    "volei": "cardiorespiratorio",
    "handball": "cardiorespiratorio",

    # OUTROS
    "caminhada": "cardiorespiratorio",
    "subida": "quadriceps",
    "escada": "quadriceps",
    "hiit": "cardiorespiratorio",
}

# Palavras-chave que indicam equipamento (RESISTÊNCIA)
EQUIPMENT_KEYWORDS = {
    "barra": ["barra", "livre"],
    "halteres": ["halteres", "halter", "dumbbell"],
    "maquina": ["maquina", "smith", "hack", "articulada"],
    "cabo": ["cabo", "polia", "crossover", "pulley"],
    "peso corporal": ["peso corporal", "livre", "barra fixa", "flexao", "mergulho", "paralelas", "prancha"],
    "kettlebell": ["kettlebell", "girya"],
    "elastico": ["elastico", "band"],
}

# Mapeamento: Exercício Aeróbico → Equipamento
AEROBIC_TO_EQUIPMENT = {
    # AMBIENTE EXTERNO (verificar primeiro - mais específicos)
    "corrida de rua": "ambiente externo",
    "caminhada de rua": "ambiente externo",
    "corri na rua": "ambiente externo",
    "correndo na rua": "ambiente externo",
    "na rua": "ambiente externo",
    
    # ESTEIRA (menos específicos)
    "corrida": "esteira",
    "corri": "esteira",
    "correndo": "esteira",
    "caminhada": "esteira",
    "caminhando": "esteira",
    "trote": "esteira",
    "running": "esteira",

    # BICICLETA ERGOMÉTRICA
    "bicicleta": "bike_ergometrica",
    "bike": "bike_ergometrica",
    "ciclismo": "bike_ergometrica",
    "spinning": "bike_ergometrica",
    "ergometrica": "bike_ergometrica",

    # PISCINA
    "natacao": "piscina",
    "piscina": "piscina",
    "crawl": "piscina",
    "costas": "piscina",
    "peito": "piscina",
    "borboleta": "piscina",

    # REMO ERGÔMETRO
    "remo": "remo_ergometro",
    "ergometro": "remo_ergometro",

    # ELÍPTICO
    "eliptico": "eliptico",

    # STEP
    "step": "step",
    "stepper": "step",

    # TRANSPORT/ESTEIRA
    "esteira": "esteira",
    "transport": "esteira",

    # ATIVIDADES LIVRES
    "zumba": "atividade_livre",
    "aerobica": "atividade_livre",
    "danca": "atividade_livre",
    "jump": "atividade_livre",

    # ESPORTES
    "futebol": "quadra_campo",
    "basquete": "quadra_campo",
    "tenis": "quadra_campo",
    "volei": "quadra_campo",
    "handball": "quadra_campo",

    # OUTROS
    "subida": "ambiente_externo",
    "escada": "ambiente_externo",
    "hiit": "atividade_livre",
    "maratona": "ambiente_externo",
}

def infer_muscle_group(exercise_name: str, exercise_type: str = "resistencia") -> str:
    """Infere o grupo muscular baseado no nome do exercício
    
    Args:
        exercise_name: Nome do exercício
        exercise_type: Tipo do exercício ("resistencia" ou "aerobico")

    """
    exercise_lower = exercise_name.lower()
    logger.info(f"Exercício a ser inferido o musculo: {exercise_lower} (tipo: {exercise_type})")

    print(exercise_type)
    print(exercise_name)
    # Para exercícios aeróbicos, usar mapeamento específico
    if exercise_type.lower() == "aerobico":
        for keyword, muscle in AEROBIC_TO_MUSCLE.items():
            if keyword in exercise_lower:
                return muscle
        return "cardiorespiratorio"  # Fallback para aeróbicos

    # Para exercícios de resistência, usar mapeamento original
    for keyword, muscle in EXERCISE_TO_MUSCLE.items():
        if keyword in exercise_lower:
            return muscle

    return "geral"  # Fallback para resistência

def infer_equipment(exercise_name: str, exercise_type: str = "resistencia") -> str:
    """Infere o equipamento baseado no nome do exercício
    
    Args:
        exercise_name: Nome do exercício
        exercise_type: Tipo do exercício ("resistencia" ou "aerobico")

    """
    exercise_lower = exercise_name.lower()

    logger.info(f"Exercício a ser inferido o equipamento: {exercise_lower} (tipo: {exercise_type})")

    # Para exercícios aeróbicos, usar mapeamento específico
    if exercise_type.lower() == "aerobico":
        # Primeiro, verificar matches mais específicos (compostos)
        matches = []
        for keyword, equipment in AEROBIC_TO_EQUIPMENT.items():
            if keyword in exercise_lower:
                matches.append((len(keyword), keyword, equipment))
        
        # Se encontrou matches, retornar o mais específico (mais longo)
        if matches:
            matches.sort(reverse=True)  # Ordenar por tamanho, maior primeiro
            return matches[0][2]
        
        return "atividade_livre"  # Fallback para aeróbicos

    # Para exercícios de resistência, usar mapeamento original
    # Primeiro, verificar casos especiais compostos
    if "barra fixa" in exercise_lower:
        return "peso corporal"
    
    # Verificar palavras-chave explícitas com prioridade
    # Ordem de prioridade: equipamentos específicos primeiro
    priority_order = ["halteres", "barra", "cabo", "maquina", "kettlebell", "elastico", "peso corporal"]
    
    for equipment in priority_order:
        if equipment in EQUIPMENT_KEYWORDS:
            keywords = EQUIPMENT_KEYWORDS[equipment]
            for keyword in keywords:
                if keyword in exercise_lower:
                    # Verificação especial para evitar conflitos
                    if keyword == "livre":
                        # "livre" só deve indicar "barra" se não houver outro equipamento mencionado
                        if not any(equip_word in exercise_lower for equip_word in ["halteres", "maquina", "smith", "hack", "cabo", "kettlebell", "elastico"]):
                            return "barra"
                    elif keyword == "barra fixa":
                        # Já foi tratado acima
                        continue
                    else:
                        return equipment

    # Inferências baseadas em padrões
    if "cadeira" in exercise_lower or "leg press" in exercise_lower:
        return "maquina"

    if "livre" in exercise_lower or "olimpico" in exercise_lower:
        return "barra"
    
    # Exercícios clássicos que são tradicionalmente feitos com barra
    classic_barbell_exercises = [
        "levantamento terra", "terra",
        "desenvolvimento militar",
        "remada curvada",
        "agachamento frontal",
        "agachamento costas",
        "supino reto",
        "remada cavalinho",
        "barra fixa",
        "encolhimento"
    ]
    
    for classic_exercise in classic_barbell_exercises:
        if classic_exercise in exercise_lower:
            # Caso especial: barra fixa é peso corporal
            if classic_exercise == "barra fixa":
                return "peso corporal"
            return "barra"

    # Fallback: se não tem indicação, provavelmente é máquina
    return "maquina"
