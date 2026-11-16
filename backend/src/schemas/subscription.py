from pydantic import BaseModel, Field


class SubscriptionInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    source: str = Field(min_length=2, max_length=200)
    params: dict = Field(default_factory=dict)


class SubscriptionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    params: dict | None = None
