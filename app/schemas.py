from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from pathlib import Path

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ProductInput(BaseModel):
    sample_dir: str
    name: str
    detail: Optional[str] = None
    image: Path

class SceneItem(BaseModel):
    id: int
    scene_name: str
    description: str
    surrounding_objects: str
    details: str
    selling_point: str
    source: Optional[str] = None

class SceneSummary(BaseModel):
    is_match: bool
    mismatch_reason: Optional[str] = ""
    scene_count: int
    scenes: List[SceneItem]

class RefinedScene(BaseModel):
    scenes: List[SceneItem]

class ScenePhrase(BaseModel):
    scene_no: int
    scene_description: str

class PhraseResult(BaseModel):
    phrases: List[ScenePhrase]
    positive_prompt_template: str = "把图像中的商品，放在带有{{}}的场景中，商品占比不低于75%。综合以上生成一张商品展示图。"

class GeneratedImage(BaseModel):
    scene_no: int
    image_path: Path
    prompt: str

class ImageGenerationResult(BaseModel):
    images: List[GeneratedImage]

class GenerationTask(BaseModel):
    task_id: str
    product: ProductInput
    status: TaskStatus = TaskStatus.PENDING
    summary: Optional[SceneSummary] = None
    refined_scene: Optional[RefinedScene] = None
    phrase_result: Optional[PhraseResult] = None
    image_result: Optional[ImageGenerationResult] = None
    error: Optional[str] = None
