import json
from pathlib import Path
from pydantic import BaseModel

PROFILE_PATH = Path("profile.json")


class UserProfile(BaseModel):
    background: str = ""
    preferences: str = ""
    cover_letter_tone: str = "professional"


def load_profile() -> UserProfile:
    if PROFILE_PATH.exists():
        return UserProfile(**json.loads(PROFILE_PATH.read_text()))
    return UserProfile()


def save_profile(profile: UserProfile) -> None:
    PROFILE_PATH.write_text(profile.model_dump_json(indent=2))
