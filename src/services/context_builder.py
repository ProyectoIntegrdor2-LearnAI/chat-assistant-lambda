from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from clients.postgres_client import get_postgres_client, PostgresClient
from clients.mongodb_client import get_mongo_client, MongoCourseClient


class LearningPathNotFound(Exception):
    """Raised when the requested learning path does not belong to the user."""


@dataclass
class CourseSummary:
    course_id: Optional[str]
    title: str
    status: str
    progress_percentage: float
    sequence_order: int
    url: Optional[str] = None
    platform: Optional[str] = None
    description: Optional[str] = None


class LearningPathContextBuilder:
    def __init__(
        self,
        postgres_client: Optional[PostgresClient] = None,
        mongo_client: Optional[MongoCourseClient] = None,
    ) -> None:
        self._postgres = postgres_client or get_postgres_client()
        # Mongo es opcional; si la conexión falla se puede ejecutar sin detalles enriquecidos.
        try:
            self._mongo = mongo_client or get_mongo_client()
        except Exception:
            self._mongo = None

    def build_context(
        self, user_id: str, learning_path_id: str
    ) -> Dict[str, Any]:
        path = self._postgres.fetch_learning_path(user_id, learning_path_id)
        if not path:
            raise LearningPathNotFound(f"Learning path {learning_path_id} not found for user")

        courses = self._postgres.fetch_courses(user_id, learning_path_id)
        course_summaries = self._enrich_courses(courses)
        current_course, next_course = self._resolve_course_progress(course_summaries)

        overall_progress = float(path.get("progress_percentage") or 0.0)
        rounded_progress = int(round(overall_progress))

        context = {
            "learning_path_id": learning_path_id,
            "name": path.get("name") or "Ruta de Aprendizaje",
            "description": path.get("description") or "",
            "overall_progress": rounded_progress,
            "target_hours_per_week": path.get("target_hours_per_week"),
            "target_completion_date": (
                path.get("target_completion_date").isoformat() if path.get("target_completion_date") is not None else None
            ),
            "current_course": current_course,
            "next_course": next_course,
            "courses": [course.__dict__ for course in course_summaries],
        }
        return context

    def build_system_prompt(self, context: Dict[str, Any]) -> str:
        name = context.get("name", "Ruta de Aprendizaje")
        description = context.get("description", "")
        progress = context.get("overall_progress", 0)
        current = context.get("current_course")
        next_course = context.get("next_course")

        current_course_text = "No hay un curso actual identificado."
        if current:
            current_course_text = (
                f"Curso actual: {current['title']} "
                f"(avance {current['progress_percentage']}%, estado {current['status']})."
            )
        next_course_text = (
            "Aún no hay un curso siguiente definido."
            if not next_course
            else f"Siguiente curso sugerido: {next_course['title']}."
        )

        course_lines = []
        for course in context.get("courses", [])[:8]:
            line = (
                f"- {course['title']} (estado: {course['status']}, orden: {course['sequence_order']}, "
                f"avance: {course['progress_percentage']}%)."
            )
            if course.get("platform"):
                line += f" Plataforma: {course['platform']}."
            course_lines.append(line)

        course_block = "\n".join(course_lines) if course_lines else "No hay cursos registrados todavía."

        prompt = (
            "Eres LearnIA, un tutor personalizado que ayuda al estudiante con su ruta de aprendizaje.\n"
            "Debes responder únicamente sobre los cursos y objetivos de la ruta y mantener un tono motivador.\n"
            "Si el usuario pregunta algo fuera de contexto, redirígelo amablemente al contenido de su ruta.\n\n"
            f"Nombre de la ruta: {name}\n"
            f"Descripción: {description}\n"
            f"Progreso global: {progress}%\n"
            f"{current_course_text}\n"
            f"{next_course_text}\n\n"
            "Lista de cursos planificados:\n"
            f"{course_block}\n\n"
            "Responde en español, en un máximo de 1 párrafos (Intenta que las respuestas sean lo más concisas posible), y ofrece recursos o consejos prácticos cuando sea útil."
        )
        return prompt

    def _enrich_courses(self, raw_courses: List[Dict[str, Any]]) -> List[CourseSummary]:
        summaries: List[CourseSummary] = []
        for course in raw_courses:
            course_id = course.get("mongodb_course_id")
            title = course_id or "Curso"
            description = None
            platform = None
            url = None

            if self._mongo and course_id:
                try:
                    mongo_data = self._mongo.get_course(course_id)
                except Exception:
                    mongo_data = None
                if mongo_data:
                    title = mongo_data.get("title") or title
                    description = mongo_data.get("description")
                    platform = mongo_data.get("platform")
                    url = mongo_data.get("url")

            sequence = course.get("sequence_order")
            try:
                sequence_order = int(sequence if sequence is not None else 0)
            except (TypeError, ValueError):
                sequence_order = 0
            progress_value = course.get("progress_percentage") or 0.0
            try:
                progress = float(progress_value)
            except (TypeError, ValueError):
                progress = 0.0

            summaries.append(
                CourseSummary(
                    course_id=course_id,
                    title=title,
                    description=description,
                    platform=platform,
                    url=url,
                    status=course.get("status", "not_started"),
                    progress_percentage=progress,
                    sequence_order=sequence_order,
                )
            )
        return summaries

    @staticmethod
    def _resolve_course_progress(
        courses: List[CourseSummary],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        if not courses:
            return None, None

        sorted_courses = sorted(courses, key=lambda c: c.sequence_order)
        current: Optional[CourseSummary] = None
        next_course: Optional[CourseSummary] = None
        for course in sorted_courses:
            if course.status not in {"completed", "skipped"}:
                current = course
                break
        if not current:
            current = sorted_courses[-1]

        # Next course is the next in sequence after current
        for course in sorted_courses:
            if course.sequence_order > current.sequence_order:
                next_course = course
                break
        return current.__dict__ if current else None, next_course.__dict__ if next_course else None
