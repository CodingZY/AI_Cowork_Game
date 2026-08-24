from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from .project import Project  # noqa: E402,F401
from .event import Event  # noqa: E402,F401
from .project_repository import ProjectRepository  # noqa: E402,F401
from .game_build import GameBuild  # noqa: E402,F401
from .game_observation import GameObservation  # noqa: E402,F401

__all__ = ["Base", "Project", "Event", "ProjectRepository", "GameBuild", "GameObservation"]
