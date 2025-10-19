"""Pytest configuration and shared fixtures"""

import asyncio
import os
import shutil

# Add src to path for tests
import sys
import tempfile
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from config.logging_config import get_logger
from database.async_connection import async_db
from services.async_backup_service import BackupService
from services.async_health_service import HealthService
from services.async_shutdown_service import ShutdownService

logger = get_logger(__name__)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    temp_dir = tempfile.mkdtemp(prefix="gym_tracker_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_db_path(temp_dir):
    """Create a test database path"""
    return os.path.join(temp_dir, "test_gym_tracker.db")


@pytest.fixture
def test_backup_dir(temp_dir):
    """Create a test backup directory"""
    backup_dir = os.path.join(temp_dir, "test_backups")
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


@pytest.fixture(scope="function")
async def test_database(test_db_path):
    """Create a test database instance using async connection"""
    # Mock settings for testing
    original_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{test_db_path}"

    try:
        # Reset the async_db instance to ensure clean state
        async_db._engine = None
        async_db._session_factory = None
        await async_db.initialize()
        yield test_db_path
    finally:
        # Clean up the async database connection
        if async_db._engine:
            await async_db.close()
            async_db._engine = None
            async_db._session_factory = None
        
        # Restore original settings
        if original_db_url:
            os.environ["DATABASE_URL"] = original_db_url
        else:
            os.environ.pop("DATABASE_URL", None)


@pytest.fixture
def test_backup_service(test_backup_dir, test_db_path):
    """Create a test backup service"""
    service = BackupService(
        backup_dir=test_backup_dir,
        max_backups=5,
        backup_frequency_hours=1,
    )
    service.database_path = test_db_path
    return service


@pytest.fixture
def test_health_service():
    """Create a test health service"""
    return HealthService()


@pytest.fixture
def test_shutdown_service():
    """Create a test shutdown service"""
    service = ShutdownService()
    service.emergency_backup_on_shutdown = False  # Disable for tests
    return service


@pytest.fixture
def mock_telegram_update():
    """Create a mock Telegram update"""
    update = Mock()
    update.effective_user.id = 12345
    update.effective_user.first_name = "Test User"
    update.effective_user.username = "testuser"
    update.message.text = "Test message"
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_telegram_context():
    """Create a mock Telegram context"""
    context = Mock()
    context.args = []
    return context


@pytest.fixture
def mock_audio_file(temp_dir):
    """Create a mock audio file for testing"""
    audio_path = os.path.join(temp_dir, "test_audio.ogg")
    # Create a dummy file
    with open(audio_path, "wb") as f:
        f.write(b"fake audio data")
    return audio_path


@pytest.fixture
def sample_workout_data():
    """Sample workout data for testing"""
    return {
        "transcription": "Fiz supino reto com barra, 3 séries de 12, 10 e 8 repetições com 40, 50 e 60 kg",
        "exercises": [
            {
                "name": "supino reto com barra",
                "sets": 3,
                "reps": [12, 10, 8],
                "weights_kg": [40, 50, 60],
                "rest_seconds": 90,
                "perceived_difficulty": 7,
                "muscle_groups": ["chest", "triceps", "shoulders"],
            },
        ],
        "session_notes": "Treino pesado, boa execução",
        "energy_level": 8,
        "body_weight_kg": 75.5,
    }


@pytest.fixture
def sample_user_data():
    """Sample user data for testing"""
    return {
        "user_id": 12345,
        "first_name": "Test User",
        "username": "testuser",
        "is_admin": False,
        "is_active": True,
    }


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Helper functions for tests
async def create_test_database_with_data(db_path):
    """Create a test database with sample data"""
    from database.async_connection import get_async_session_context
    from database.models import Exercise, User, ExerciseType

    async with get_async_session_context() as session:
        try:
            # Add test user
            user = User(
                user_id=12345,
                first_name="Test User",
                username="testuser",
                is_admin=False,
                is_active=True,
            )
            session.add(user)

            # Add test exercises
            exercises = [
                Exercise(name="supino reto", type=ExerciseType.RESISTENCIA, muscle_group="chest"),
                Exercise(name="agachamento", type=ExerciseType.RESISTENCIA, muscle_group="legs"),
                Exercise(name="deadlift", type=ExerciseType.RESISTENCIA, muscle_group="back"),
            ]
            session.add_all(exercises)

            await session.commit()
            return db_path
        except Exception as e:
            await session.rollback()
            raise e


@pytest.fixture(scope="function")
async def populated_test_database(test_db_path):
    """Create a test database with sample data using async connection"""
    # Set up async database URL
    original_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{test_db_path}"
    
    try:
        # Ensure clean state - remove database file if it exists
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
            
        # Reset the async_db instance to ensure clean state
        async_db._engine = None
        async_db._session_factory = None
        await async_db.initialize()
        await create_test_database_with_data(test_db_path)
        yield test_db_path
    finally:
        # Clean up the async database connection
        if async_db._engine:
            await async_db.close()
            async_db._engine = None
            async_db._session_factory = None
            
        # Remove database file after test
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except (OSError, PermissionError):
                pass  # Ignore cleanup errors
            
        # Restore original settings
        if original_db_url:
            os.environ["DATABASE_URL"] = original_db_url
        else:
            os.environ.pop("DATABASE_URL", None)


# Legacy sync fixture for backward compatibility
@pytest.fixture(scope="function")
def sync_test_database(test_db_path):
    """Create a sync test database for backward compatibility"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database.models import Base

    # Mock settings for testing
    original_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

    try:
        engine = create_engine(f"sqlite:///{test_db_path}")
        Base.metadata.create_all(engine)
        yield test_db_path
    finally:
        # Restore original settings
        if original_db_url:
            os.environ["DATABASE_URL"] = original_db_url
        else:
            os.environ.pop("DATABASE_URL", None)


@pytest.fixture(scope="function")
def sync_populated_test_database(test_db_path):
    """Create a sync test database with sample data for backward compatibility"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database.models import Base, Exercise, User, ExerciseType

    # Mock settings for testing
    original_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

    try:
        engine = create_engine(f"sqlite:///{test_db_path}")
        Base.metadata.create_all(engine)

        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            # Add test user
            user = User(
                user_id=12345,
                first_name="Test User",
                username="testuser",
                is_admin=False,
                is_active=True,
            )
            session.add(user)

            # Add test exercises
            exercises = [
                Exercise(name="supino reto", type=ExerciseType.RESISTENCIA, muscle_group="chest"),
                Exercise(name="agachamento", type=ExerciseType.RESISTENCIA, muscle_group="legs"),
                Exercise(name="deadlift", type=ExerciseType.RESISTENCIA, muscle_group="back"),
            ]
            session.add_all(exercises)

            session.commit()
            yield test_db_path
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    finally:
        # Restore original settings
        if original_db_url:
            os.environ["DATABASE_URL"] = original_db_url
        else:
            os.environ.pop("DATABASE_URL", None)


# Test configuration
pytest.main.__doc__ = """
Test configuration for Gym Tracker Bot

To run tests:
    pytest tests/                    # All tests
    pytest tests/unit/              # Unit tests only
    pytest tests/integration/       # Integration tests only
    pytest -v                       # Verbose output
    pytest --tb=short              # Short traceback format
    pytest -x                       # Stop on first failure
    pytest -k "test_name"          # Run specific test pattern

Test categories:
- Unit tests: Test individual functions/classes in isolation
- Integration tests: Test component interactions
- Fixtures: Reusable test data and mocks
"""

