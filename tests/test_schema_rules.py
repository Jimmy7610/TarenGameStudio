import pytest
from sqlalchemy.exc import IntegrityError

from database.models import Agent, Project, Review, Task, TaskDependency


def test_task_cannot_depend_on_itself(session):
    project = Project(name="Game")
    session.add(project)
    session.flush()
    task = Task(project_id=project.id, title="Task")
    session.add(task)
    session.flush()

    session.add(TaskDependency(task_id=task.id, depends_on_task_id=task.id))
    with pytest.raises(IntegrityError):
        session.commit()


def test_agent_cannot_review_own_work(session):
    project = Project(name="Game")
    agent = Agent(id="claude", role="lead_engineer")
    session.add_all([project, agent])
    session.flush()
    task = Task(project_id=project.id, title="Task", owner_agent_id="claude")
    session.add(task)
    session.flush()

    session.add(
        Review(
            project_id=project.id,
            task_id=task.id,
            creator_agent_id="claude",
            reviewer_agent_id="claude",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
