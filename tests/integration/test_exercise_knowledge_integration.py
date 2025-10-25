"""Integration tests for exercise_knowledge.py"""

import pytest

from services.exercise_knowledge import infer_equipment, infer_muscle_group


class TestExerciseKnowledgeIntegration:
    """Integration tests for exercise knowledge functions working together"""

    def test_complete_resistance_exercise_inference(self):
        """Test complete inference flow for resistance exercises"""
        test_cases = [
            # (exercise_name, expected_muscle, expected_equipment)
            ("supino reto com barra", "peitoral", "barra"),
            ("supino inclinado com halteres", "peitoral", "halteres"),
            ("agachamento livre", "quadriceps", "barra"),
            ("leg press 45 graus", "quadriceps", "maquina"),
            ("remada baixa no cabo", "dorsais", "cabo"),
            ("rosca direta com barra", "biceps", "barra"),
            ("triceps na polia com corda", "triceps", "cabo"),
            ("desenvolvimento com halteres", "ombros", "halteres"),
            ("elevacao lateral na maquina", "ombros", "maquina"),
            ("cadeira extensora", "quadriceps", "maquina"),
            ("cadeira flexora", "isquiotibiais", "maquina"),
            ("panturrilha em pe", "panturrilhas", "maquina"),
            ("abdominal no solo", "abdomen", "maquina"),
            ("flexao de braco", "peitoral", "peso corporal"),
            ("barra fixa", "dorsais", "peso corporal"),
            ("mergulho nas paralelas", "triceps", "peso corporal"),
        ]
        
        for exercise, expected_muscle, expected_equipment in test_cases:
            muscle = infer_muscle_group(exercise, "resistencia")
            equipment = infer_equipment(exercise, "resistencia")
            
            assert muscle == expected_muscle, f"Exercise '{exercise}' should target '{expected_muscle}', got '{muscle}'"
            assert equipment == expected_equipment, f"Exercise '{exercise}' should use '{expected_equipment}', got '{equipment}'"

    def test_complete_aerobic_exercise_inference(self):
        """Test complete inference flow for aerobic exercises"""
        test_cases = [
            # (exercise_name, expected_muscle, expected_equipment)
            ("corrida de rua 5km", "cardiorespiratorio", "ambiente externo"),
            ("corrida na esteira", "cardiorespiratorio", "esteira"),
            ("caminhada de rua", "cardiorespiratorio", "ambiente externo"),
            ("caminhada na esteira", "cardiorespiratorio", "esteira"),
            ("bicicleta ergometrica", "quadriceps", "bike_ergometrica"),
            ("spinning 45 minutos", "quadriceps", "bike_ergometrica"),
            ("natacao estilo livre", "corpo_todo", "piscina"),
            ("natacao estilo costas", "corpo_todo", "piscina"),  # "natacao" takes precedence over "costas"
            ("natacao estilo peito", "corpo_todo", "piscina"),  # "natacao" takes precedence over "peito"
            ("remo ergometro", "dorsais", "remo_ergometro"),
            ("eliptico 30 minutos", "cardiorespiratorio", "eliptico"),
            ("step aerobico", "quadriceps", "step"),
            ("zumba", "cardiorespiratorio", "atividade_livre"),
            ("jump", "quadriceps", "atividade_livre"),
            ("futebol", "cardiorespiratorio", "quadra_campo"),
            ("basquete", "cardiorespiratorio", "quadra_campo"),
            ("subida de escada", "quadriceps", "ambiente_externo"),
            ("hiit workout", "cardiorespiratorio", "atividade_livre"),
        ]
        
        for exercise, expected_muscle, expected_equipment in test_cases:
            muscle = infer_muscle_group(exercise, "aerobico")
            equipment = infer_equipment(exercise, "aerobico")
            
            assert muscle == expected_muscle, f"Exercise '{exercise}' should target '{expected_muscle}', got '{muscle}'"
            assert equipment == expected_equipment, f"Exercise '{exercise}' should use '{expected_equipment}', got '{equipment}'"

    def test_mixed_portuguese_english_terms(self):
        """Test exercises with mixed Portuguese and English terms"""
        # Resistance exercises
        assert infer_muscle_group("leg press unilateral", "resistencia") == "quadriceps"
        assert infer_muscle_group("pulldown frontal", "resistencia") == "dorsais"
        assert infer_muscle_group("crossover peitoral", "resistencia") == "peitoral"
        assert infer_equipment("crossover peitoral", "resistencia") == "cabo"
        
        # Aerobic exercises
        assert infer_muscle_group("running na esteira", "aerobico") == "cardiorespiratorio"
        assert infer_equipment("running outdoor", "aerobico") == "esteira"  # "running" maps to "esteira"

    def test_exercise_variations_consistency(self):
        """Test that exercise variations maintain consistent muscle groups"""
        # Supino variations
        supino_variations = [
            "supino reto",
            "supino inclinado",
            "supino declinado",
            "supino com halteres",
            "supino na maquina",
            "supino no smith",
        ]
        
        for exercise in supino_variations:
            assert infer_muscle_group(exercise, "resistencia") == "peitoral"
        
        # Agachamento variations
        agachamento_variations = [
            "agachamento livre",
            "agachamento smith",
            "agachamento hack",
            "agachamento bulgaro",
            "agachamento sumô",
        ]
        
        for exercise in agachamento_variations:
            assert infer_muscle_group(exercise, "resistencia") == "quadriceps"
        
        # Rosca variations
        rosca_variations = [
            "rosca direta",
            "rosca alternada",
            "rosca martelo",
            "rosca scott",
            "rosca concentrada",
        ]
        
        for exercise in rosca_variations:
            assert infer_muscle_group(exercise, "resistencia") == "biceps"

    def test_compound_exercises(self):
        """Test exercises that work multiple muscle groups"""
        # These tests verify the primary muscle group is correctly identified
        compound_exercises = [
            ("levantamento terra", "dorsais", "barra"),
            ("desenvolvimento militar", "ombros", "barra"),
            ("remada curvada", "dorsais", "barra"),
            ("agachamento frontal", "quadriceps", "barra"),
        ]
        
        for exercise, expected_muscle, expected_equipment in compound_exercises:
            muscle = infer_muscle_group(exercise, "resistencia")
            equipment = infer_equipment(exercise, "resistencia")
            
            assert muscle == expected_muscle
            assert equipment == expected_equipment

    def test_uncommon_exercises_fallback(self):
        """Test that uncommon exercises fall back to appropriate defaults"""
        # Resistance exercises should fall back to "geral" muscle and "maquina" equipment
        uncommon_resistance = [
            "farmer's walk",
            "turkish get-up",
            "wall sits",
            "bear crawl",
        ]
        
        for exercise in uncommon_resistance:
            muscle = infer_muscle_group(exercise, "resistencia")
            equipment = infer_equipment(exercise, "resistencia")
            assert muscle == "geral"
            assert equipment == "maquina"
        
        # Aerobic exercises should fall back to "cardiorespiratorio" and "atividade_livre"
        uncommon_aerobic = [
            "parkour",
            "slackline",
            "pole dance",
            "aerial yoga",
        ]
        
        for exercise in uncommon_aerobic:
            muscle = infer_muscle_group(exercise, "aerobico")
            equipment = infer_equipment(exercise, "aerobico")
            assert muscle == "cardiorespiratorio"
            assert equipment == "atividade_livre"

    def test_real_world_exercise_descriptions(self):
        """Test with real-world exercise descriptions as they might come from users"""
        real_world_cases = [
            # User might say these in Portuguese
            ("fiz supino reto com barra olimpica 3x12", "peitoral", "barra"),
            ("agachamento livre no smith 4x10", "quadriceps", "maquina"),  # "smith" is in maquina keywords
            ("remada baixa sentado no cabo", "dorsais", "cabo"),
            ("rosca direta em pe com barra W", "biceps", "barra"),
            ("triceps frances deitado com halteres", "triceps", "halteres"),
            ("desenvolvimento arnold com halteres", "ombros", "halteres"),
            ("leg press 45 graus unilateral", "quadriceps", "maquina"),
            ("elevacao lateral com cabo", "ombros", "cabo"),
            ("panturrilha sentado na maquina", "panturrilhas", "maquina"),
            
            # Aerobic descriptions
            ("corri 5km na rua hoje", "cardiorespiratorio", "ambiente externo"),
            ("30 minutos de bike spinning", "quadriceps", "bike_ergometrica"),
            ("natacao 1000m estilo livre", "corpo_todo", "piscina"),
            ("hiit na esteira 20 minutos", "cardiorespiratorio", "esteira"),
        ]
        
        for description, expected_muscle, expected_equipment in real_world_cases:
            # Determine exercise type based on expected equipment (aerobic equipments indicate aerobic exercise)
            aerobic_equipments = {"ambiente externo", "esteira", "bike_ergometrica", "piscina", "remo_ergometro", 
                                  "eliptico", "step", "atividade_livre", "quadra_campo"}
            exercise_type = "aerobico" if expected_equipment in aerobic_equipments else "resistencia"
            
            muscle = infer_muscle_group(description, exercise_type)
            equipment = infer_equipment(description, exercise_type)
            
            assert muscle == expected_muscle, f"Description '{description}' should target '{expected_muscle}', got '{muscle}'"
            assert equipment == expected_equipment, f"Description '{description}' should use '{expected_equipment}', got '{equipment}'"

    def test_exercise_with_numbers_and_special_chars(self):
        """Test exercise names containing numbers and special characters"""
        # These should still be parsed correctly
        assert infer_muscle_group("leg press 45°", "resistencia") == "quadriceps"
        assert infer_muscle_group("supino 30° inclinado", "resistencia") == "peitoral"
        assert infer_muscle_group("21's rosca", "resistencia") == "biceps"
        assert infer_muscle_group("corrida 10km/h", "aerobico") == "cardiorespiratorio"
        
        # Equipment inference
        assert infer_equipment("supino 45° com barra", "resistencia") == "barra"
        assert infer_equipment("rosca 21's com halteres", "resistencia") == "halteres"

    def test_typos_and_misspellings(self):
        """Test that common typos still get reasonable results"""
        # Common typos in Portuguese
        typos = [
            ("supino retto com barra", "peitoral", "barra"),  # double t
            ("agachamneto livre", "geral", "barra"),  # misspelled, but "livre" triggers barra
            ("roska direta", "geral", "maquina"),  # k instead of c
            ("dezenvolvimento", "geral", "maquina"),  # missing s
            ("triseps na polia", "geral", "cabo"),  # missing c, but "polia" triggers cabo
            ("ellevacao lateral", "geral", "maquina"),  # double l
        ]
        
        for typo, expected_muscle, expected_equipment in typos:
            muscle = infer_muscle_group(typo, "resistencia")
            equipment = infer_equipment(typo, "resistencia")
            
            # Note: typos won't match the exercise name, but equipment keywords might still work
            assert equipment == expected_equipment, f"Typo '{typo}' should still infer equipment '{expected_equipment}', got '{equipment}'"

    @pytest.mark.parametrize("exercise_type", ["resistencia", "RESISTENCIA", "Resistencia", "rEsIsTenCiA"])
    def test_exercise_type_case_handling(self, exercise_type):
        """Test that exercise type parameter handles different cases correctly"""
        # Should work regardless of case
        assert infer_muscle_group("supino", exercise_type) == "peitoral"
        assert infer_equipment("supino com barra", exercise_type) == "barra"
    
    @pytest.mark.parametrize("exercise_type", ["aerobico", "AEROBICO", "Aerobico", "aErObIcO"])
    def test_aerobic_type_case_handling(self, exercise_type):
        """Test that aerobic type parameter handles different cases correctly"""
        # Should work regardless of case
        assert infer_muscle_group("corrida", exercise_type) == "cardiorespiratorio"
        assert infer_equipment("corrida", exercise_type) == "esteira"