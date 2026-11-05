from pydantic import BaseModel


class DocSummary(BaseModel):
    name: str  # "week1"
    title: str  # "1주차 — FastAPI + Pydantic + Depends"


class DocContent(BaseModel):
    name: str
    title: str
    markdown: str


class GlossaryEntry(BaseModel):
    term: str
    meaning: str
    frontend: str  # 프론트 대응 (없으면 "")
    source: str  # 어느 문서에서 왔나 ("week3")


class LayerInfo(BaseModel):
    key: str  # "router"
    name: str  # "라우터"
    folder: str  # "app/api/v1/"
    role: str  # 한 줄 역할
    knows: list[str]  # 아는 것
    never: list[str]  # 모르는 것
    company: str  # 회사 레포 대응
    files: list[str]


class FileInfo(BaseModel):
    path: str
    layer: str
    summary: str
    company: str = ""


class StructureResponse(BaseModel):
    layers: list[LayerInfo]
    files: list[FileInfo]
    request_flow: list[str]  # 요청이 지나는 순서 (layer key)
