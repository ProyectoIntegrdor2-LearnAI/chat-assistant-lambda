import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.append(str(SRC_PATH))

from services.context_builder import CourseSummary, LearningPathContextBuilder  # noqa: E402


def test_resolve_course_progress_selects_first_non_completed():
    courses = [
        CourseSummary("1", "Curso 1", "completed", 100.0, 1),
        CourseSummary("2", "Curso 2", "in_progress", 50.0, 2),
        CourseSummary("3", "Curso 3", "not_started", 0.0, 3),
    ]
    current, next_course = LearningPathContextBuilder._resolve_course_progress(courses)
    assert current["course_id"] == "2"
    assert next_course["course_id"] == "3"
