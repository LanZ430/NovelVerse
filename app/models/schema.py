from typing import List, Optional, Dict
from pydantic import BaseModel
from datetime import datetime

class Chapter(BaseModel):
    number: int
    title: str
    content: str
    summary: str
    key_events: List[str]
    characters: List[str]
    locations: List[str]

class Character(BaseModel):
    name: str
    description: str
    relationships: Dict[str, str]  # character_name: relationship_type
    traits: List[str]
    background: str
    image_url: Optional[str] = None

class Location(BaseModel):
    name: str
    description: str
    connected_locations: List[str]
    key_features: List[str]
    image_url: Optional[str] = None

class WorldState(BaseModel):
    current_chapter: int
    current_location: str
    active_characters: List[str]
    time_period: str
    events_history: List[Dict]

class UserRole(BaseModel):
    character_name: str
    role_type: str  # protagonist, secondary, observer
    current_goals: List[str]
    inventory: List[str]
    relationships: Dict[str, str]
    dialogue_history: List[Dict]

class StoryProgress(BaseModel):
    session_id: str
    start_time: datetime
    current_world_state: WorldState
    user_role: UserRole
    completed_chapters: List[int]
    decision_points: List[Dict]
    generated_content: Dict[str, List[str]]  # type: urls

class NovelMetadata(BaseModel):
    title: str
    author: str
    genre: str
    upload_date: datetime
    total_chapters: int
    processed: bool
    vector_store_path: Optional[str]
    world_knowledge_base: Dict
    main_characters: List[Character]
    locations: List[Location]