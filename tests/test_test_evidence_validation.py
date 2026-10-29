


import pytest


class TestCommandOrProcedureValidation:
    """Regression tests for KI-008: blank command_or_procedure must be rejected."""

    def test_create_rejects_empty_command(self):
        """TestEvidenceCreate must reject an empty command_or_procedure."""
        from pydantic import ValidationError

        from app.schemas.test_evidence import TestEvidenceCreate as TECreate
        from app.schemas.test_evidence import TestResult
        from app.schemas.test_evidence import TestType

        with pytest.raises(ValidationError):
            TECreate(
                proposal_id=1,
                test_type=TestType.UNIT,
                command_or_procedure="",
                result=TestResult.PASSED,
            )

    def test_create_rejects_whitespace_command(self):
        """TestEvidenceCreate must reject a whitespace-only command_or_procedure."""
        from pydantic import ValidationError

        from app.schemas.test_evidence import TestEvidenceCreate as TECreate
        from app.schemas.test_evidence import TestResult
        from app.schemas.test_evidence import TestType

        with pytest.raises(ValidationError):
            TECreate(
                proposal_id=1,
                test_type=TestType.UNIT,
                command_or_procedure="   ",
                result=TestResult.PASSED,
            )

    def test_create_accepts_normal_command(self):
        """TestEvidenceCreate must accept a non-empty command_or_procedure."""
        from app.schemas.test_evidence import TestEvidenceCreate as TECreate
        from app.schemas.test_evidence import TestResult
        from app.schemas.test_evidence import TestType

        payload = TECreate(
            proposal_id=1,
            test_type=TestType.UNIT,
            command_or_procedure="pytest -q tests/",
            result=TestResult.PASSED,
        )
        assert payload.command_or_procedure == "pytest -q tests/"

    def test_update_rejects_empty_command(self):
        """TestEvidenceUpdate must reject an empty command_or_procedure when provided."""
        from pydantic import ValidationError

        from app.schemas.test_evidence import TestEvidenceUpdate as TEUpdate

        with pytest.raises(ValidationError):
            TEUpdate(command_or_procedure="")

    def test_update_rejects_whitespace_command(self):
        """TestEvidenceUpdate must reject a whitespace-only command_or_procedure."""
        from pydantic import ValidationError

        from app.schemas.test_evidence import TestEvidenceUpdate as TEUpdate

        with pytest.raises(ValidationError):
            TEUpdate(command_or_procedure="\t\n ")

    def test_update_accepts_none_command(self):
        """TestEvidenceUpdate must allow command_or_procedure=None (no change)."""
        from app.schemas.test_evidence import TestEvidenceUpdate as TEUpdate

        payload = TEUpdate(command_or_procedure=None)
        assert payload.command_or_procedure is None

    def test_update_accepts_normal_command(self):
        """TestEvidenceUpdate must accept a non-empty command_or_procedure."""
        from app.schemas.test_evidence import TestEvidenceUpdate as TEUpdate

        payload = TEUpdate(command_or_procedure="npm test")
        assert payload.command_or_procedure == "npm test"
