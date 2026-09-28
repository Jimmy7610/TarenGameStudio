from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Event, Project
from database.session import SessionLocal, get_session, init_database
from orchestrator.studio_engine import StudioEngine


app = FastAPI(title="Taren Game Studio", version="0.1.0")


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class PromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20_000)


@app.on_event("startup")
def startup() -> None:
    init_database()


@app.get("/")
def hq() -> FileResponse:
    return FileResponse(Path(__file__).resolve().parents[1] / "hq" / "index.html")


@app.post("/api/projects")
def create_project(body: ProjectCreate, session: Session = Depends(get_session)):
    engine = StudioEngine(session)
    project = engine.create_project(body.name)
    session.commit()
    return {"id": str(project.id), "name": project.name}


@app.post("/api/projects/{project_id}/prompt")
def submit_prompt(project_id: uuid.UUID, body: PromptRequest, session: Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    return StudioEngine(session).kickoff(project, body.prompt)


@app.get("/api/studio/state")
def studio_state(project_id: uuid.UUID, session: Session = Depends(get_session)):
    try:
        return StudioEngine(session).state_snapshot(project_id)
    except KeyError:
        raise HTTPException(404, "project not found")


@app.websocket("/ws/events")
async def event_stream(websocket: WebSocket, project_id: uuid.UUID):
    await websocket.accept()
    last_timestamp = None
    last_id = None
    try:
        while True:
            with SessionLocal() as session:
                stmt = select(Event).where(Event.project_id == project_id)
                if last_timestamp is not None:
                    stmt = stmt.where(
                        (Event.timestamp > last_timestamp)
                        | ((Event.timestamp == last_timestamp) & (Event.id != last_id))
                    )
                events = list(session.scalars(stmt.order_by(Event.timestamp.asc(), Event.id.asc()).limit(200)))
                for event in events:
                    await websocket.send_json({
                        "id": str(event.id),
                        "type": event.event_type,
                        "timestamp": event.timestamp.isoformat(),
                        "actor": event.actor,
                        "correlation_id": str(event.correlation_id),
                        "causation_id": str(event.causation_id) if event.causation_id else None,
                        "payload": event.payload_json,
                    })
                    last_timestamp = event.timestamp
                    last_id = event.id
            await asyncio.sleep(0.35)
    except WebSocketDisconnect:
        return
