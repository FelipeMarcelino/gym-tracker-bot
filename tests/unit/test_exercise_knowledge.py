"""Unit tests for exercise_knowledge.py"""

import pytest

from services.exercise_knowledge import (
    AEROBIC_TO_EQUIPMENT,
    AEROBIC_TO_MUSCLE,
    EQUIPMENT_KEYWORDS,
    EXERCISE_TO_MUSCLE,
    infer_equipment,
    infer_muscle_group,
)


class TestExerciseKnowledgeMappings:
    """Test the static mappings in exercise_knowledge"""

    def test_exercise_to_muscle_mapping(self):
        """Test that EXERCISE_TO_MUSCLE mapping is valid"""
        # Test some key mappings
        assert EXERCISE_TO_MUSCLE["supino"] == "peitoral"
        assert EXERCISE_TO_MUSCLE["agachamento"] == "quadriceps"
        assert EXERCISE_TO_MUSCLE["remada"] == "dorsais"
        assert EXERCISE_TO_MUSCLE["rosca"] == "biceps"
        assert EXERCISE_TO_MUSCLE["triceps"] == "triceps"
        assert EXERCISE_TO_MUSCLE["desenvolvimento"] == "ombros"
        assert EXERCISE_TO_MUSCLE["abdominal"] == "abdomen"
        assert EXERCISE_TO_MUSCLE["panturrilha"] == "panturrilhas"
        
        # Ensure all values are non-empty strings
        for exercise, muscle in EXERCISE_TO_MUSCLE.items():
            assert isinstance(exercise, str) and exercise
            assert isinstance(muscle, str) and muscle

    def test_aerobic_to_muscle_mapping(self):
        """Test that AEROBIC_TO_MUSCLE mapping is valid"""
        # Test some key mappings
        assert AEROBIC_TO_MUSCLE["corrida"] == "cardiorespiratorio"
        assert AEROBIC_TO_MUSCLE["bicicleta"] == "quadriceps"
        assert AEROBIC_TO_MUSCLE["natacao"] == "corpo_todo"
        assert AEROBIC_TO_MUSCLE["remo"] == "dorsais"
        assert AEROBIC_TO_MUSCLE["eliptico"] == "cardiorespiratorio"
        
        # Ensure all values are non-empty strings
        for exercise, muscle in AEROBIC_TO_MUSCLE.items():
            assert isinstance(exercise, str) and exercise
            assert isinstance(muscle, str) and muscle

    def test_equipment_keywords_mapping(self):
        """Test that EQUIPMENT_KEYWORDS mapping is valid"""
        # Test structure
        assert "barra" in EQUIPMENT_KEYWORDS
        assert "halteres" in EQUIPMENT_KEYWORDS
        assert "maquina" in EQUIPMENT_KEYWORDS
        assert "cabo" in EQUIPMENT_KEYWORDS
        assert "peso corporal" in EQUIPMENT_KEYWORDS
        
        # Test some keyword lists
        assert "barra" in EQUIPMENT_KEYWORDS["barra"]
        assert "halteres" in EQUIPMENT_KEYWORDS["halteres"]
        assert "polia" in EQUIPMENT_KEYWORDS["cabo"]
        assert "flexao" in EQUIPMENT_KEYWORDS["peso corporal"]
        
        # Ensure all values are lists of strings
        for equipment, keywords in EQUIPMENT_KEYWORDS.items():
            assert isinstance(equipment, str) and equipment
            assert isinstance(keywords, list) and len(keywords) > 0
            for keyword in keywords:
                assert isinstance(keyword, str) and keyword

    def test_aerobic_to_equipment_mapping(self):
        """Test that AEROBIC_TO_EQUIPMENT mapping is valid"""
        # Test some key mappings
        assert AEROBIC_TO_EQUIPMENT["corrida de rua"] == "ambiente externo"
        assert AEROBIC_TO_EQUIPMENT["corrida"] == "esteira"
        assert AEROBIC_TO_EQUIPMENT["bicicleta"] == "bike_ergometrica"
        assert AEROBIC_TO_EQUIPMENT["natacao"] == "piscina"
        assert AEROBIC_TO_EQUIPMENT["remo"] == "remo_ergometro"
        assert AEROBIC_TO_EQUIPMENT["eliptico"] == "eliptico"
        
        # Ensure all values are non-empty strings
        for exercise, equipment in AEROBIC_TO_EQUIPMENT.items():
            assert isinstance(exercise, str) and exercise
            assert isinstance(equipment, str) and equipment


class TestInferMuscleGroup:
    """Test the infer_muscle_group function"""

    def test_infer_muscle_resistance_exercises(self):
        """Test muscle group inference for resistance exercises"""
        # Test exact matches
        assert infer_muscle_group("supino", "resistencia") == "peitoral"
        assert infer_muscle_group("agachamento", "resistencia") == "quadriceps"
        assert infer_muscle_group("remada", "resistencia") == "dorsais"
        
        # Test partial matches
        assert infer_muscle_group("supino reto com barra", "resistencia") == "peitoral"
        assert infer_muscle_group("agachamento livre", "resistencia") == "quadriceps"
        assert infer_muscle_group("remada baixa no cabo", "resistencia") == "dorsais"
        assert infer_muscle_group("rosca direta com barra", "resistencia") == "biceps"
        
        # Test case insensitive
        assert infer_muscle_group("SUPINO", "resistencia") == "peitoral"
        assert infer_muscle_group("Agachamento", "resistencia") == "quadriceps"
        assert infer_muscle_group("ReMaDa", "resistencia") == "dorsais"

    def test_infer_muscle_aerobic_exercises(self):
        """Test muscle group inference for aerobic exercises"""
        # Test exact matches
        assert infer_muscle_group("corrida", "aerobico") == "cardiorespiratorio"
        assert infer_muscle_group("bicicleta", "aerobico") == "quadriceps"
        assert infer_muscle_group("natacao", "aerobico") == "corpo_todo"
        
        # Test partial matches
        assert infer_muscle_group("corrida na esteira", "aerobico") == "cardiorespiratorio"
        assert infer_muscle_group("bicicleta ergometrica", "aerobico") == "quadriceps"
        assert infer_muscle_group("natacao estilo crawl", "aerobico") == "corpo_todo"
        
        # Test case insensitive
        assert infer_muscle_group("CORRIDA", "aerobico") == "cardiorespiratorio"
        assert infer_muscle_group("Bicicleta", "aerobico") == "quadriceps"

    def test_infer_muscle_not_in_list(self):
        """Test muscle group inference for exercises not in the list"""
        # Resistance exercises not in list should return "geral"
        assert infer_muscle_group("exercicio_inexistente", "resistencia") == "geral"
        assert infer_muscle_group("movimento_estranho", "resistencia") == "geral"
        assert infer_muscle_group("", "resistencia") == "geral"
        
        # Aerobic exercises not in list should return "cardiorespiratorio"
        assert infer_muscle_group("exercicio_inexistente", "aerobico") == "cardiorespiratorio"
        assert infer_muscle_group("movimento_estranho", "aerobico") == "cardiorespiratorio"
        assert infer_muscle_group("", "aerobico") == "cardiorespiratorio"

    def test_infer_muscle_edge_cases(self):
        """Test edge cases for muscle group inference"""
        # Empty string
        assert infer_muscle_group("", "resistencia") == "geral"
        assert infer_muscle_group("", "aerobico") == "cardiorespiratorio"
        
        # Special characters
        assert infer_muscle_group("supino@#$", "resistencia") == "peitoral"
        assert infer_muscle_group("corrida!@#", "aerobico") == "cardiorespiratorio"
        
        # Numbers in exercise name
        assert infer_muscle_group("supino 45 graus", "resistencia") == "peitoral"
        assert infer_muscle_group("corrida 5km", "aerobico") == "cardiorespiratorio"

    def test_infer_muscle_type_case_insensitive(self):
        """Test that exercise type is case insensitive"""
        # Test different cases for exercise type
        assert infer_muscle_group("supino", "RESISTENCIA") == "peitoral"
        assert infer_muscle_group("supino", "Resistencia") == "peitoral"
        assert infer_muscle_group("supino", "rEsIsTeNcIa") == "peitoral"
        
        assert infer_muscle_group("corrida", "AEROBICO") == "cardiorespiratorio"
        assert infer_muscle_group("corrida", "Aerobico") == "cardiorespiratorio"
        assert infer_muscle_group("corrida", "aErObIcO") == "cardiorespiratorio"

    def test_infer_muscle_with_multiple_keywords(self):
        """Test exercises that contain multiple muscle group keywords"""
        # "rosca triceps" contains both "rosca" (biceps) and "triceps" (triceps)
        # Should match first occurrence in the dictionary
        result = infer_muscle_group("rosca triceps", "resistencia")
        assert result in ["biceps", "triceps"]  # Depends on dict order
        
        # "desenvolvimento de panturrilha" contains both keywords
        result = infer_muscle_group("desenvolvimento de panturrilha", "resistencia")
        assert result in ["ombros", "panturrilhas"]  # Depends on dict order


class TestInferEquipment:
    """Test the infer_equipment function"""

    def test_infer_equipment_resistance_exercises(self):
        """Test equipment inference for resistance exercises"""
        # Test with explicit equipment keywords
        assert infer_equipment("supino com barra", "resistencia") == "barra"
        assert infer_equipment("rosca com halteres", "resistencia") == "halteres"
        assert infer_equipment("leg press na maquina", "resistencia") == "maquina"
        assert infer_equipment("triceps na polia", "resistencia") == "cabo"
        assert infer_equipment("flexao peso corporal", "resistencia") == "peso corporal"
        
        # Test special cases
        assert infer_equipment("cadeira extensora", "resistencia") == "maquina"
        assert infer_equipment("leg press 45 graus", "resistencia") == "maquina"
        assert infer_equipment("agachamento livre", "resistencia") == "barra"
        assert infer_equipment("supino olimpico", "resistencia") == "barra"

    def test_infer_equipment_aerobic_exercises(self):
        """Test equipment inference for aerobic exercises"""
        # Test exact matches
        assert infer_equipment("corrida de rua", "aerobico") == "ambiente externo"
        assert infer_equipment("corrida", "aerobico") == "esteira"
        assert infer_equipment("bicicleta", "aerobico") == "bike_ergometrica"
        assert infer_equipment("natacao", "aerobico") == "piscina"
        assert infer_equipment("remo", "aerobico") == "remo_ergometro"
        assert infer_equipment("eliptico", "aerobico") == "eliptico"
        
        # Test partial matches
        assert infer_equipment("corrida na esteira", "aerobico") == "esteira"
        assert infer_equipment("bicicleta spinning", "aerobico") == "bike_ergometrica"

    def test_infer_equipment_not_in_list(self):
        """Test equipment inference for exercises not in the list"""
        # Resistance exercises not in list should return "maquina"
        assert infer_equipment("exercicio_inexistente", "resistencia") == "maquina"
        assert infer_equipment("movimento_estranho", "resistencia") == "maquina"
        
        # Aerobic exercises not in list should return "atividade_livre"
        assert infer_equipment("exercicio_inexistente", "aerobico") == "atividade_livre"
        assert infer_equipment("movimento_estranho", "aerobico") == "atividade_livre"

    def test_infer_equipment_case_insensitive(self):
        """Test that equipment inference is case insensitive"""
        # Resistance
        assert infer_equipment("SUPINO COM BARRA", "resistencia") == "barra"
        assert infer_equipment("Rosca Com Halteres", "resistencia") == "halteres"
        assert infer_equipment("LEG PRESS", "resistencia") == "maquina"
        
        # Aerobic
        assert infer_equipment("CORRIDA", "aerobico") == "esteira"
        assert infer_equipment("Bicicleta", "aerobico") == "bike_ergometrica"

    def test_infer_equipment_edge_cases(self):
        """Test edge cases for equipment inference"""
        # Empty string
        assert infer_equipment("", "resistencia") == "maquina"
        assert infer_equipment("", "aerobico") == "atividade_livre"
        
        # Special characters
        assert infer_equipment("supino@#$ com barra", "resistencia") == "barra"
        assert infer_equipment("corrida!@#", "aerobico") == "esteira"
        
        # Multiple equipment keywords (should match first found based on priority)
        assert infer_equipment("rosca na maquina com cabo", "resistencia") == "cabo"  # "cabo" has priority over "maquina"
        assert infer_equipment("desenvolvimento livre com halteres", "resistencia") == "halteres"

    def test_infer_equipment_type_case_insensitive(self):
        """Test that exercise type is case insensitive"""
        assert infer_equipment("supino com barra", "RESISTENCIA") == "barra"
        assert infer_equipment("supino com barra", "Resistencia") == "barra"
        assert infer_equipment("corrida", "AEROBICO") == "esteira"
        assert infer_equipment("corrida", "Aerobico") == "esteira"

    def test_infer_equipment_priority(self):
        """Test equipment keyword priority"""
        # When multiple keywords present, test which takes precedence
        # This depends on the order of checking in the function
        
        # "smith" is in maquina keywords, but "livre" triggers barra
        assert infer_equipment("agachamento smith", "resistencia") == "maquina"
        
        # "crossover" is in cabo keywords
        assert infer_equipment("crossover peitoral", "resistencia") == "cabo"
        
        # "hack" is in maquina keywords
        assert infer_equipment("agachamento hack", "resistencia") == "maquina"


class TestDictionaryConsistency:
    """Test consistency across all dictionaries"""

    def test_no_duplicate_keys_across_muscle_dicts(self):
        """Ensure no exercise appears in both resistance and aerobic muscle mappings"""
        resistance_exercises = set(EXERCISE_TO_MUSCLE.keys())
        aerobic_exercises = set(AEROBIC_TO_MUSCLE.keys())
        
        # Some overlap might be intentional (e.g., "costas" could be swimming or back exercise)
        # But let's identify them for awareness
        overlap = resistance_exercises.intersection(aerobic_exercises)
        
        # Known overlaps that are intentional
        expected_overlaps = {"costas", "peito"}  # Swimming strokes vs muscle groups
        
        assert overlap.issubset(expected_overlaps), f"Unexpected overlaps: {overlap - expected_overlaps}"

    def test_muscle_group_values_consistency(self):
        """Test that muscle group values are consistent across dictionaries"""
        all_muscle_groups = set()
        all_muscle_groups.update(EXERCISE_TO_MUSCLE.values())
        all_muscle_groups.update(AEROBIC_TO_MUSCLE.values())
        
        # Common muscle groups that should exist
        expected_groups = {
            "peitoral", "dorsais", "ombros", "biceps", "triceps",
            "quadriceps", "isquiotibiais", "panturrilhas", "abdomen",
            "cardiorespiratorio", "corpo_todo", "trapezio"
        }
        
        # Note: "geral" is not in the dictionaries, it's a fallback value
        # All expected values should be in our muscle groups
        assert expected_groups.issubset(all_muscle_groups)

    def test_equipment_values_consistency(self):
        """Test that equipment values are consistent"""
        resistance_equipment = set(EQUIPMENT_KEYWORDS.keys())
        aerobic_equipment = set(AEROBIC_TO_EQUIPMENT.values())
        
        # Check that common equipment types exist
        assert "barra" in resistance_equipment
        assert "halteres" in resistance_equipment
        assert "maquina" in resistance_equipment
        assert "esteira" in aerobic_equipment
        assert "bike_ergometrica" in aerobic_equipment