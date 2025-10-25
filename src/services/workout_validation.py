"""Workout data validation service"""

from typing import Any, Dict, List, Optional, Union


class ValidationError(Exception):
    """Custom exception for workout validation errors"""
    pass


# Isometric exercises (exercises where you hold a position for time)
ISOMETRIC_EXERCISES = {
    "prancha", "prancha abdominal", "prancha lateral", "prancha frontal",
    "ponte", "ponte lateral", "isometria", "wall sit", "parede",
    "superman", "bird dog", "hollow body", "dead bug"
}


def is_isometric_exercise(exercise_name: str) -> bool:
    """
    Check if an exercise is isometric (doesn't require weights).
    
    Args:
        exercise_name: Name of the exercise
        
    Returns:
        True if the exercise is isometric
    """
    if not exercise_name:
        return False
    
    exercise_lower = exercise_name.lower()
    
    # Check if any isometric keyword is in the exercise name
    for isometric_keyword in ISOMETRIC_EXERCISES:
        if isometric_keyword in exercise_lower:
            return True
    
    return False


def infer_sets_from_reps(reps: Optional[List[int]]) -> int:
    """
    Infer the number of sets from the repetitions array.
    
    Args:
        reps: List of repetitions per set
        
    Returns:
        Number of sets (0 if reps is None or empty)
    """
    if not reps:
        return 0
    return len(reps)


def validate_exercise_data(exercise_data: Dict[str, Any], exercise_type: str = "resistance") -> bool:
    """
    Validate individual exercise data for completeness.
    
    Args:
        exercise_data: Dictionary containing exercise information
        exercise_type: Type of exercise ("resistance" or "aerobic")
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If data is incomplete or invalid
    """
    # Skip validation for aerobic exercises
    if exercise_type.lower() == "aerobic":
        return True
    
    exercise_name = exercise_data.get("name", "Exercício sem nome")
    
    # Check for reps
    reps = exercise_data.get("reps")
    if not reps:
        raise ValidationError(
            f"Exercício '{exercise_name}' está sem as repetições. "
            f"Por favor, informe o número de repetições para cada série."
        )
    
    if not isinstance(reps, list) or len(reps) == 0:
        raise ValidationError(
            f"Exercício '{exercise_name}' está sem as repetições. "
            f"Por favor, informe o número de repetições para cada série."
        )
    
    # Check if it's an isometric exercise (by name or explicit type)
    is_isometric = (
        exercise_data.get("exercise_type") == "isometric" or
        is_isometric_exercise(exercise_name)
    )
    
    # Check for weights (not required for isometric exercises)
    weights = exercise_data.get("weights_kg")
    
    if not is_isometric:
        # Only require weights for non-isometric exercises
        if not weights:
            raise ValidationError(
                f"Exercício '{exercise_name}' está sem os pesos. "
                f"Por favor, informe os pesos (em kg) utilizados em cada série."
            )
        
        if not isinstance(weights, list) or len(weights) == 0:
            raise ValidationError(
                f"Exercício '{exercise_name}' está sem os pesos. "
                f"Por favor, informe os pesos (em kg) utilizados em cada série."
            )
    else:
        # For isometric exercises, if weights are not provided, create array of zeros
        if not weights:
            weights = [0] * len(reps)
            exercise_data["weights_kg"] = weights
    
    # Validate reps and weights count match
    if len(reps) != len(weights):
        raise ValidationError(
            f"Exercício '{exercise_name}' tem número diferente de repetições ({len(reps)}) "
            f"e pesos ({len(weights)}). Por favor, informe os dados completos para cada série."
        )
    
    # Validate numeric values
    for i, rep in enumerate(reps):
        if not isinstance(rep, (int, float)) or rep < 0:
            raise ValidationError(
                f"Exercício '{exercise_name}' tem valor inválido de repetições na série {i+1}. "
                f"As repetições devem ser números positivos."
            )
    
    for i, weight in enumerate(weights):
        if not isinstance(weight, (int, float)) or weight < 0:
            raise ValidationError(
                f"Exercício '{exercise_name}' tem valor inválido de peso na série {i+1}. "
                f"Os pesos devem ser números não-negativos (use 0 para exercícios com peso corporal)."
            )
    
    # Infer or correct sets
    inferred_sets = infer_sets_from_reps(reps)
    if "sets" not in exercise_data or exercise_data.get("sets") != inferred_sets:
        exercise_data["sets"] = inferred_sets
    
    return True


def format_validation_error_message(
    error_type: str, 
    exercise_name: str, 
    reps_count: Optional[int] = None, 
    weights_count: Optional[int] = None
) -> str:
    """
    Format a user-friendly error message for validation errors.
    
    Args:
        error_type: Type of validation error
        exercise_name: Name of the exercise with error
        reps_count: Number of reps provided (for mismatch errors)
        weights_count: Number of weights provided (for mismatch errors)
        
    Returns:
        Formatted error message
    """
    if error_type == "missing_reps":
        return (
            f"⚠️ O exercício '{exercise_name}' está sem as repetições.\n"
            f"Por favor, envie novamente informando quantas repetições fez em cada série.\n"
            f"Exemplo: '3 séries de 12, 10, 8 repetições'"
        )
    
    elif error_type == "missing_weights":
        return (
            f"⚠️ O exercício '{exercise_name}' está sem os pesos.\n"
            f"Por favor, envie novamente informando os pesos (em kg) usados.\n"
            f"Exemplo: 'com 20kg' ou 'com 20, 25, 30kg' (se usou pesos diferentes)"
        )
    
    elif error_type == "mismatched_count":
        return (
            f"⚠️ O exercício '{exercise_name}' tem informações incompletas:\n"
            f"- {reps_count} repetições informadas\n"
            f"- {weights_count} pesos informados\n\n"
            f"Por favor, informe o mesmo número de repetições e pesos para cada série."
        )
    
    return f"⚠️ Erro no exercício '{exercise_name}'. Por favor, verifique os dados e envie novamente."


def validate_workout_data(workout_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate complete workout data from LLM parsing.
    
    Args:
        workout_data: Dictionary containing complete workout information
        
    Returns:
        Dictionary with validation results:
        {
            "is_valid": bool,
            "errors": List of error dictionaries
        }
    """
    errors = []
    
    # Validate resistance exercises
    resistance_exercises = workout_data.get("resistance_exercises", [])
    for exercise in resistance_exercises:
        try:
            validate_exercise_data(exercise, exercise_type="resistance")
        except ValidationError as e:
            errors.append({
                "exercise": exercise.get("name", "Exercício sem nome"),
                "error_type": _get_error_type(str(e)),
                "message": str(e)
            })
    
    # Aerobic exercises don't need reps/weights validation
    # They are validated differently (duration is required)
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors
    }


def get_user_friendly_error_message(errors: List[Dict[str, Any]]) -> str:
    """
    Generate a user-friendly message summarizing validation errors.
    
    Args:
        errors: List of error dictionaries from validate_workout_data
        
    Returns:
        Formatted message for the user
    """
    if not errors:
        return ""
    
    message_parts = ["⚠️ **Alguns exercícios precisam de mais informações:**\n"]
    
    # Group errors by type
    missing_reps = []
    missing_weights = []
    other_errors = []
    
    for error in errors:
        exercise = error["exercise"]
        error_type = error.get("error_type", "other")
        
        if error_type == "missing_reps":
            missing_reps.append(exercise)
        elif error_type == "missing_weights":
            missing_weights.append(exercise)
        else:
            other_errors.append((exercise, error["message"]))
    
    # Format grouped errors
    if missing_reps:
        message_parts.append(
            f"\n📝 **Faltam as repetições para:**\n"
            + "\n".join(f"  • {ex}" for ex in missing_reps)
            + "\n\n_Exemplo: 'Fiz 3 séries de 12, 10, 8 repetições'_"
        )
    
    if missing_weights:
        message_parts.append(
            f"\n⚖️ **Faltam os pesos para:**\n"
            + "\n".join(f"  • {ex}" for ex in missing_weights)
            + "\n\n_Exemplo: 'Com 50kg' ou 'Com 40, 50, 60kg' (se variou o peso)_"
        )
    
    if other_errors:
        message_parts.append("\n❗ **Outros problemas:**")
        for exercise, msg in other_errors:
            # Extract just the key part of the error
            if "número diferente" in msg:
                message_parts.append(f"  • {exercise}: número de séries e pesos não correspondem")
            else:
                message_parts.append(f"  • {exercise}: {msg.split('.')[0]}")
    
    message_parts.append(
        "\n\n💡 **Por favor, envie novamente com as informações completas.**"
    )
    
    return "\n".join(message_parts)


def _get_error_type(error_message: str) -> str:
    """
    Determine error type from error message.
    
    Args:
        error_message: The validation error message
        
    Returns:
        Error type string
    """
    error_lower = error_message.lower()
    
    if "repetições" in error_lower and "sem" in error_lower:
        return "missing_reps"
    elif "pesos" in error_lower and "sem" in error_lower:
        return "missing_weights"
    elif "número diferente" in error_lower:
        return "mismatched_count"
    else:
        return "other"