from pydantic import BaseModel, Field


class ProductBrief(BaseModel):
    """Facts about one product. Scripts may only use what is written here."""

    id: str
    name: str
    price_thb: float
    category: str
    features: list[str]
    audience: str
    notes: str = ""


class Scene(BaseModel):
    voiceover: str = Field(description="Thai narration spoken in this scene")
    on_screen_text: str = Field(description="Short Thai text shown on screen, max ~8 words")
    visual: str = Field(description="What to show, e.g. 'product photo 1 zoom in', 'shocked emoji'")
    duration_sec: float = Field(description="Scene length in seconds")


class VideoScript(BaseModel):
    title: str = Field(description="Internal title for this video, in Thai")
    hook: str = Field(description="The first line, spoken in the first 2 seconds, in Thai")
    scenes: list[Scene]
    cta: str = Field(description="Closing call to action pointing to the yellow basket, in Thai")
    caption: str = Field(description="TikTok post caption in Thai, 1-2 sentences")
    hashtags: list[str] = Field(description="5-8 hashtags without the # sign")
    facts_used: list[str] = Field(description="Every product fact the script mentions, copied from the brief")
