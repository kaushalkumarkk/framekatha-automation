from pydantic import Field, model_validator

from api.schemas.leads import StrictInput


class ScriptRequest(StrictInput):
    requirement: str | None = Field(default=None, min_length=1, max_length=20000)
    language: str = Field(default="English", min_length=1, max_length=80)
    duration_seconds: int = Field(default=30, ge=5, le=600)
    tone: str = Field(default="Cinematic and warm", min_length=1, max_length=300)


class Shot(StrictInput):
    scene_id: str = Field(min_length=1, max_length=80)
    shot_number: int = Field(ge=1)
    duration_seconds: float = Field(gt=0, le=600)
    visual: str = Field(min_length=1, max_length=4000)
    dialogue: str = Field(max_length=4000)
    camera: str = Field(min_length=1, max_length=1000)
    audio: str = Field(max_length=1000)


class MusicSuggestion(StrictInput):
    mood: str = Field(min_length=1, max_length=300)
    tempo_bpm: int = Field(ge=20, le=240)
    instrumentation: str = Field(min_length=1, max_length=1000)
    licensing_note: str = Field(min_length=1, max_length=1000)


class ScriptDocument(StrictInput):
    title: str = Field(min_length=1, max_length=300)
    shooting_script: list[Shot] = Field(min_length=1, max_length=200)
    screenplay: str = Field(min_length=1, max_length=30000)
    editing_direction: list[str] = Field(min_length=1, max_length=50)
    bgm_suggestions: list[MusicSuggestion] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique_shots(self):
        numbers = [shot.shot_number for shot in self.shooting_script]
        if len(numbers) != len(set(numbers)) or numbers != sorted(numbers):
            raise ValueError("Shot numbers must be unique and ascending")
        return self
