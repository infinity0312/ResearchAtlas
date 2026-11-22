"""Adapters keep acquisition, parsing and model providers independent of domains."""
from typing import Protocol, Literal
from pydantic import BaseModel, Field

class SourceAdapter(Protocol):
    def fetch(self, query: str, start: int, size: int) -> tuple[list[dict], int]: ...
class ParserAdapter(Protocol):
    def parse(self, path: str) -> list[dict]: ...
class ModelAdapter(Protocol):
    def generate(self, prompt: str) -> dict: ...

class SourceQuote(BaseModel):
    page: int = Field(ge=1)
    quote: str = Field(min_length=12, max_length=2000)

class Claim(BaseModel):
    kind: Literal['method','contribution','limitation']
    text: str = Field(min_length=1, max_length=1500)
    basis: Literal['author','observation','hypothesis'] = 'author'
    page: int = Field(ge=1)
    quote: str = Field(min_length=12, max_length=2000)
    supporting_evidence: list[SourceQuote] = Field(default_factory=list,max_length=8)

class Extraction(BaseModel):
    summary: str = Field(max_length=3000)
    topics: list[str] = Field(default_factory=list, max_length=12)
    methods: list[str] = Field(default_factory=list, max_length=15)
    problems: list[str] = Field(default_factory=list, max_length=8,description='Short names of research problems this paper directly solves, not limitations or future work.')
    claims: list[Claim] = Field(default_factory=list, max_length=50)
    field_evidence: dict[str,list[int]] = Field(default_factory=dict, description='Optional zero-based claim references for summary, topics.N, methods.N, problems.N. Unbound presentation fields are discarded by the evidence pipeline.')

class Topic(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    definition: str = Field(max_length=1000)
    page: int = Field(ge=1)
    quote: str = Field(min_length=12, max_length=2000)
class SurveyExtraction(BaseModel):
    topics: list[Topic] = Field(default_factory=list, max_length=30)

class Synthesis(BaseModel):
    summary: str = Field(min_length=1,max_length=3000)
    topics: list[str] = Field(default_factory=list,max_length=3)
    methods: list[str] = Field(default_factory=list,max_length=8)
    problems: list[str] = Field(default_factory=list,max_length=5)
    selected_claims: list[int] = Field(min_length=1,max_length=15)
