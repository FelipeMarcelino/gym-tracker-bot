"""Unit tests for messages module, focusing on format_single_exercise function"""


from config.messages import Messages


class TestFormatSingleExercise:
    """Test Messages._format_single_exercise function"""

    def test_basic_exercise_with_same_weight_all_sets(self):
        """Test formatting exercise with same weight for all sets"""
        exercise_data = {
            "name": "supino reto com barra",
            "sets": 3,
            "reps": [12, 10, 8],
            "weights_kg": [60, 60, 60],
        }

        result = Messages._format_single_exercise(exercise_data)

        assert "**Supino Reto Com Barra**" in result
        assert "3× (12, 10, 8) com 60kg" in result
        assert "Série" not in result  # Should not show individual series when weights are same

    def test_exercise_with_different_weights_per_set(self):
        """Test formatting exercise with different weights per set"""
        exercise_data = {
            "name": "agachamento livre",
            "sets": 4,
            "reps": [12, 10, 8, 6],
            "weights_kg": [80, 90, 100, 110],
        }

        result = Messages._format_single_exercise(exercise_data)

        assert "**Agachamento Livre**" in result
        assert "Série 1: 12 reps × 80kg" in result
        assert "Série 2: 10 reps × 90kg" in result
        assert "Série 3: 8 reps × 100kg" in result
        assert "Série 4: 6 reps × 110kg" in result

    def test_exercise_with_rest_time_seconds(self):
        """Test formatting exercise with rest time in seconds"""
        exercise_data = {
            "name": "rosca direta",
            "sets": 3,
            "reps": [12, 12, 12],
            "weights_kg": [20, 20, 20],
            "rest_seconds": 45,
        }

        result = Messages._format_single_exercise(exercise_data)

        assert "⏱️ Descanso: 45s" in result

    def test_exercise_with_rest_time_minutes(self):
        """Test formatting exercise with rest time in minutes"""
        exercise_data = {
            "name": "leg press",
            "sets": 3,
            "reps": [15, 15, 15],
            "weights_kg": [200, 200, 200],
            "rest_seconds": 120,
        }

        result = Messages._format_single_exercise(exercise_data)

        assert "⏱️ Descanso: 2min" in result

    def test_exercise_with_rest_time_minutes_and_seconds(self):
        """Test formatting exercise with rest time in minutes and seconds"""
        exercise_data = {
            "name": "supino inclinado",
            "sets": 3,
            "reps": [10, 10, 10],
            "weights_kg": [70, 70, 70],
            "rest_seconds": 90,
        }

        result = Messages._format_single_exercise(exercise_data)

        assert "⏱️ Descanso: 1min 30s" in result

    def test_exercise_with_low_difficulty(self):
        """Test formatting exercise with low perceived difficulty"""
        exercise_data = {
            "name": "elevação lateral",
            "sets": 3,
            "reps": [15, 15, 15],
            "weights_kg": [10, 10, 10],
            "perceived_difficulty": 2,
        }

        result = Messages._format_single_exercise(exercise_data)

        assert "😊 RPE: 2/10 (Muito fácil)" in result

    def test_exercise_with_moderate_difficulty(self):
        """Test formatting exercise with moderate perceived difficulty"""
        exercise_data = {
            "name": "remada curvada",
            "sets": 4,
            "reps": [12, 12, 10, 10],
            "weights_kg": [60, 60, 60, 60],
            "perceived_difficulty": 6,
        }

        result = Messages._format_single_exercise(exercise_data)

        assert "😐 RPE: 6/10 (Moderado)" in result

    def test_exercise_with_high_difficulty(self):
        """Test formatting exercise with high perceived difficulty"""
        exercise_data = {
            "name": "terra",
            "sets": 5,
            "reps": [5, 5, 5, 3, 3],
            "weights_kg": [140, 140, 140, 150, 150],
            "perceived_difficulty": 9,
        }

        result = Messages._format_single_exercise(exercise_data)

        assert "🔥 RPE: 9/10 (Muito difícil)" in result

    def test_exercise_with_all_optional_fields(self):
        """Test formatting exercise with all optional fields present"""
        exercise_data = {
            "name": "desenvolvimento com halteres",
            "sets": 3,
            "reps": [12, 10, 8],
            "weights_kg": [30, 35, 40],
            "rest_seconds": 75,
            "perceived_difficulty": 7,
        }

        result = Messages._format_single_exercise(exercise_data)

        # Check all components are present
        assert "**Desenvolvimento Com Halteres**" in result
        assert "Série 1: 12 reps × 30kg" in result
        assert "Série 2: 10 reps × 35kg" in result
        assert "Série 3: 8 reps × 40kg" in result
        assert "⏱️ Descanso: 1min 15s" in result
        assert "😤 RPE: 7/10 (Difícil)" in result

    def test_exercise_missing_weights_kg_but_has_weight_kg(self):
        """Test backward compatibility with weight_kg instead of weights_kg"""
        exercise_data = {
            "name": "prancha abdominal",
            "sets": 3,
            "reps": [1, 1, 1],
            "weight_kg": 10,  # Legacy field name with non-zero value
        }

        result = Messages._format_single_exercise(exercise_data)

        # When weights_kg is missing but weight_kg exists (and is truthy), it creates the array
        assert "Série 1: 1 segundos com 10 kgs" in result
        assert "Série 2: 1 segundos com 10 kgs" in result
        assert "Série 3: 1 segundos com 10 kgs" in result

    def test_exercise_missing_weights_with_zero_weight_kg(self):
        """Test that weight_kg=0 is not used (because 0 is falsy)"""
        exercise_data = {
            "name": "prancha",
            "sets": 3,
            "reps": [60, 60, 60],
            "weight_kg": 0,  # This won't be used because 0 is falsy
        }

        result = Messages._format_single_exercise(exercise_data)

        # When weight_kg is 0 (falsy), it's ignored and shows ?
        assert "Série 1: 60 segundos" in result
        assert "Série 2: 60 segundos" in result
        assert "Série 3: 60 segundos" in result

    def test_exercise_with_missing_reps_data(self):
        """Test handling of missing or incomplete reps data with same weights"""
        exercise_data = {
            "name": "flexão de braço",
            "sets": 4,
            "reps": [20, 18],  # Only 2 reps for 4 sets
            "weights_kg": [0, 0, 0, 0],  # All same weight
        }

        result = Messages._format_single_exercise(exercise_data)

        # When all weights are the same, it uses compact format
        assert "4× (20, 18) com 0kg" in result

    def test_exercise_with_missing_weights_data(self):
        """Test handling of missing or incomplete weights data"""
        exercise_data = {
            "name": "barra fixa",
            "sets": 3,
            "reps": [10, 8, 6],
            "weights_kg": [10],  # Only 1 weight for 3 sets - treats as same weight
        }

        result = Messages._format_single_exercise(exercise_data)

        # When weights list has only one value, it's treated as same weight for all
        assert "3× (10, 8, 6) com 10kg" in result

    def test_exercise_with_no_weights_at_all(self):
        """Test handling exercise with no weights specified"""
        exercise_data = {
            "name": "abdominal",
            "sets": 3,
            "reps": [20, 20, 20],
        }

        result = Messages._format_single_exercise(exercise_data)

        assert "3× (20, 20, 20) com ?kg" in result

    def test_exercise_name_title_case_conversion(self):
        """Test that exercise names are properly converted to title case"""
        test_cases = [
            ("supino reto", "Supino Reto"),
            ("LEG PRESS", "Leg Press"),
            ("rosca DIRETA com barra", "Rosca Direta Com Barra"),
            ("desenvolvimento", "Desenvolvimento"),
        ]

        for input_name, expected_title in test_cases:
            exercise_data = {
                "name": input_name,
                "sets": 1,
                "reps": [10],
                "weights_kg": [50],
            }

            result = Messages._format_single_exercise(exercise_data)
            assert f"**{expected_title}**" in result

    def test_difficulty_level_boundaries(self):
        """Test all difficulty level boundaries and descriptions"""
        difficulty_tests = [
            (1, "😊", "Muito fácil"),
            (2, "😊", "Muito fácil"),
            (3, "🙂", "Fácil"),
            (4, "🙂", "Fácil"),
            (5, "😐", "Moderado"),
            (6, "😐", "Moderado"),
            (7, "😤", "Difícil"),
            (8, "😤", "Difícil"),
            (9, "🔥", "Muito difícil"),
            (10, "🔥", "Muito difícil"),
        ]

        for difficulty, expected_emoji, expected_desc in difficulty_tests:
            exercise_data = {
                "name": "teste",
                "sets": 1,
                "reps": [10],
                "weights_kg": [50],
                "perceived_difficulty": difficulty,
            }

            result = Messages._format_single_exercise(exercise_data)
            assert f"{expected_emoji} RPE: {difficulty}/10 ({expected_desc})" in result

    def test_exercise_ends_with_newline(self):
        """Test that formatted exercise always ends with double newline"""
        exercise_data = {
            "name": "test exercise",
            "sets": 1,
            "reps": [10],
            "weights_kg": [50],
        }

        result = Messages._format_single_exercise(exercise_data)

        assert result.endswith("\n\n")

    def test_exercise_with_zero_sets(self):
        """Test edge case with zero sets"""
        exercise_data = {
            "name": "test exercise",
            "sets": 0,
            "reps": [],
            "weights_kg": [],
        }

        result = Messages._format_single_exercise(exercise_data)

        assert "**Test Exercise**" in result
        assert "0×" in result

    def test_exercise_formatting_structure(self):
        """Test the overall structure and indentation of formatted exercise"""
        exercise_data = {
            "name": "supino",
            "sets": 2,
            "reps": [10, 8],
            "weights_kg": [60, 70],
            "rest_seconds": 60,
            "perceived_difficulty": 5,
        }

        result = Messages._format_single_exercise(exercise_data)

        # Check structure with proper indentation
        lines = result.strip().split("\n")
        assert lines[0] == "• **Supino**:"
        assert lines[1].startswith("  └ Série 1:")
        assert lines[2].startswith("  └ Série 2:")
        assert lines[3].startswith("  └ ⏱️ Descanso:")
        assert lines[4].startswith("  └ 😐 RPE:")

    def test_empty_reps_list_handling(self):
        """Test handling of empty reps list"""
        exercise_data = {
            "name": "test",
            "sets": 3,
            "reps": [],
            "weights_kg": [50, 50, 50],
        }

        result = Messages._format_single_exercise(exercise_data)

        assert "3× () com 50kg" in result

    def test_exercise_with_different_weights_missing_data(self):
        """Test handling of different weights with missing rep data"""
        exercise_data = {
            "name": "rosca scott",
            "sets": 3,
            "reps": [12],  # Only one rep entry
            "weights_kg": [20, 25, 30],  # Different weights
        }

        result = Messages._format_single_exercise(exercise_data)

        # Should show individual series because weights differ
        assert "Série 1: 12 reps × 20kg" in result
        assert "Série 2: ? reps × 25kg" in result
        assert "Série 3: ? reps × 30kg" in result

    def test_exercise_name_with_special_characters(self):
        """Test exercise name with special characters and formatting"""
        exercise_data = {
            "name": "leg press 45°",
            "sets": 3,
            "reps": [15, 12, 10],
            "weights_kg": [180, 200, 220],
        }

        result = Messages._format_single_exercise(exercise_data)

        assert "**Leg Press 45°**" in result

    def test_format_isometric_exercise(self):
        """Test formatting of isometric exercises like plank"""
        exercise_data = {
            "name": "prancha abdominal",
            "sets": 3,
            "reps": [60, 45, 30],
            "weights_kg": [0, 0, 0],
            "rest_seconds": 30,
            "perceived_difficulty": 8,
        }

        result = Messages._format_single_exercise(exercise_data)

        # Check that it shows seconds instead of reps × kg
        assert "• **Prancha Abdominal**:" in result
        assert "Série 1: 60 segundos" in result
        assert "Série 2: 45 segundos" in result
        assert "Série 3: 30 segundos" in result
        assert "⏱️ Descanso: 30s" in result
        assert "😤 RPE: 8/10" in result

        # Should not contain "com" (but can contain kg if weight is added)
        assert "com 0kg" not in result

    def test_format_isometric_exercise_same_duration(self):
        """Test formatting of isometric exercise with same duration"""
        exercise_data = {
            "name": "prancha lateral",
            "sets": 4,
            "reps": [45, 45, 45, 45],
            "weights_kg": [0, 0, 0, 0],
        }

        result = Messages._format_single_exercise(exercise_data)

        # Should still show individual series for isometric
        assert "Série 1: 45 segundos" in result
        assert "Série 2: 45 segundos" in result
        assert "Série 3: 45 segundos" in result
        assert "Série 4: 45 segundos" in result

    def test_format_isometric_exercise_with_weight(self):
        """Test formatting of isometric exercise with additional weight"""
        exercise_data = {
            "name": "prancha abdominal",
            "sets": 3,
            "reps": [60, 50, 40],
            "weights_kg": [10, 10, 10],  # Added weight on back
            "rest_seconds": 45,
        }

        result = Messages._format_single_exercise(exercise_data)

        # Should still show seconds for isometric, even with weight
        assert "• **Prancha Abdominal**:" in result
        assert "Série 1: 60 segundos" in result
        assert "Série 2: 50 segundos" in result
        assert "Série 3: 40 segundos" in result

        # Note: Current implementation doesn't show weight for isometric
        # This could be enhanced in the future

    def test_format_bodyweight_non_isometric(self):
        """Test formatting of bodyweight exercise that is NOT isometric"""
        exercise_data = {
            "name": "flexão de braço",
            "sets": 3,
            "reps": [20, 15, 12],
            "weights_kg": [0, 0, 0],  # No additional weight
        }

        result = Messages._format_single_exercise(exercise_data)

        # Should show reps, not seconds
        assert "• **Flexão De Braço**:" in result
        assert "3× (20, 15, 12) com 0kg" in result
        assert "segundos" not in result

