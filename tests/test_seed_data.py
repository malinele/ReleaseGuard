"""Tests for the seed data script safety guard."""
import importlib.util
from pathlib import Path

import pytest

from app.models.project import Project
from app.models.proposal import Proposal, WorkflowStatus

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "seed_data.py"
_spec = importlib.util.spec_from_file_location("seed_data", SCRIPT_PATH)
seed_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed_module)


def test_seed_populates_empty_database(db_session):
    seed_module.seed_data(db=db_session)

    assert db_session.query(Project).count() == 1
    proposal = db_session.query(Proposal).one()
    assert proposal.workflow_status == WorkflowStatus.RELEASED


def test_seed_refuses_when_data_exists(db_session):
    db_session.add(Project(name="Existing", description="real data"))
    db_session.commit()

    with pytest.raises(seed_module.SeedRefusedError, match="--force"):
        seed_module.seed_data(db=db_session)

    assert db_session.query(Project).count() == 1


def test_seed_force_seeds_despite_existing_data(db_session):
    db_session.add(Project(name="Existing", description="real data"))
    db_session.commit()

    seed_module.seed_data(db=db_session, force=True)

    assert db_session.query(Project).count() == 2


def test_main_returns_error_code_when_refused(monkeypatch, capsys):
    def refuse(force=False):
        raise seed_module.SeedRefusedError("nope")

    monkeypatch.setattr(seed_module, "seed_data", refuse)

    assert seed_module.main([]) == 1
    assert "nope" in capsys.readouterr().err


def test_main_passes_force_flag(monkeypatch):
    seen = {}
    monkeypatch.setattr(seed_module, "seed_data", lambda force=False: seen.update(force=force))

    assert seed_module.main(["--force"]) == 0
    assert seen == {"force": True}
