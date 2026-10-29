#!/usr/bin/env python3
"""Seed data script for ReleaseGuard.

Creates deterministic seed data showing ONE COMPLETE LIFECYCLE:
- 1 project "ReleaseGuard Core"
- 3 requirements: REQ-001, REQ-002, REQ-003
- 1 proposal that goes through: draft → context_review → implementation → test_review → security_review → release_ready → released
- Test evidence attached
- Security review passed
- Release decision approved
"""
import argparse
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal, init_db
from app.models.project import Project
from app.models.requirement import Requirement, Priority, RequirementStatus
from app.models.proposal import Proposal, WorkflowStatus, RiskLevel
from app.models.proposal_requirement import ProposalRequirement
from app.models.test_evidence import TestEvidence, TestType, TestResult
from app.models.security_review import SecurityReview, SecurityReviewStatus
from app.models.release_decision import ReleaseDecision, Decision
from app.services.workflow_service import WorkflowService


class SeedRefusedError(RuntimeError):
    """Raised when seeding would touch a database that already has data."""


def seed_data(db=None, force=False):
    """Create seed data for ReleaseGuard.

    Refuses to run against a database that already contains projects unless
    ``force`` is True. An explicit ``db`` session is used as-is (and not closed).
    """
    owns_session = db is None
    if owns_session:
        init_db()
        db = SessionLocal()

    try:
        if not force and db.query(Project).count() > 0:
            raise SeedRefusedError(
                "Database already contains data; refusing to seed. "
                "Re-run with --force to seed anyway."
            )

        # Create project "ReleaseGuard Core"
        project = Project(name="ReleaseGuard Core", description="Core release governance system")
        db.add(project)
        db.commit()
        db.refresh(project)
        print(f"Created project: {project.name} (id={project.id})")

        # Create 3 requirements
        requirements_data = [
            {
                "project_id": project.id,
                "requirement_id": "REQ-001",
                "title": "User Authentication",
                "description": "System shall support user authentication via OAuth2",
                "priority": Priority.HIGH,
                "acceptance_criteria": "Users can log in using external OAuth2 provider",
            },
            {
                "project_id": project.id,
                "requirement_id": "REQ-002",
                "title": "Release Workflow",
                "description": "System shall manage release approval workflow",
                "priority": Priority.HIGH,
                "acceptance_criteria": "Proposals can transition through all workflow states",
            },
            {
                "project_id": project.id,
                "requirement_id": "REQ-003",
                "title": "Audit Logging",
                "description": "System shall maintain audit trail of all actions",
                "priority": Priority.MEDIUM,
                "acceptance_criteria": "All create/update/delete operations are logged",
            },
        ]

        requirements = []
        for req_data in requirements_data:
            req = Requirement(**req_data)
            db.add(req)
            db.commit()
            db.refresh(req)
            requirements.append(req)
            print(f"Created requirement: {req.requirement_id} (id={req.id})")

        # Create proposal
        proposal = Proposal(
            project_id=project.id,
            proposal_id="PROP-001",
            summary="Implement OAuth2 authentication and release workflow",
            generated_by="product_owner",
            files_expected=["auth.py", "workflow.py", "audit.py"],
            risk_level=RiskLevel.MEDIUM,
            rationale="Required for Phase 2 release",
            workflow_status=WorkflowStatus.DRAFT,
        )
        db.add(proposal)
        db.commit()
        db.refresh(proposal)
        print(f"Created proposal: {proposal.proposal_id} (id={proposal.id})")

        # Link requirements to proposal
        for req in requirements:
            link = ProposalRequirement(proposal_id=proposal.id, requirement_id=req.id)
            db.add(link)
        db.commit()
        print(f"Linked {len(requirements)} requirements to proposal {proposal.proposal_id}")

        # Create test evidence
        test_evidence_data = [
            {
                "proposal_id": proposal.id,
                "test_type": TestType.UNIT,
                "command_or_procedure": "pytest tests/unit/test_auth.py",
                "result": TestResult.PASSED,
                "evidence_notes": "All authentication unit tests pass",
            },
            {
                "proposal_id": proposal.id,
                "test_type": TestType.INTEGRATION,
                "command_or_procedure": "pytest tests/integration/test_workflow.py",
                "result": TestResult.PASSED,
                "evidence_notes": "Integration tests confirm workflow state transitions",
            },
        ]

        for te_data in test_evidence_data:
            te = TestEvidence(**te_data)
            db.add(te)
            db.commit()
            db.refresh(te)
            print(f"Created test evidence: {te.test_type.value} - {te.result.value} (id={te.id})")

        # Create security review (passed)
        security_review = SecurityReview(
            proposal_id=proposal.id,
            status=SecurityReviewStatus.PASSED,
            reviewer="security_team",
            notes="All security controls verified. No critical issues found.",
        )
        db.add(security_review)
        db.commit()
        db.refresh(security_review)
        print(f"Created security review: {security_review.status.value} (id={security_review.id})")

        # Create release decision (approved)
        release_decision = ReleaseDecision(
            proposal_id=proposal.id,
            decision=Decision.APPROVED,
            decision_maker="release_manager",
            decision_notes="All gates passed. Approved for release.",
        )
        db.add(release_decision)
        db.commit()
        db.refresh(release_decision)
        print(f"Created release decision: {release_decision.decision.value} (id={release_decision.id})")

        # Transition proposal through all workflow states
        workflow_transitions = [
            WorkflowStatus.CONTEXT_REVIEW,
            WorkflowStatus.IMPLEMENTATION,
            WorkflowStatus.TEST_REVIEW,
            WorkflowStatus.SECURITY_REVIEW,
            WorkflowStatus.RELEASE_READY,
            WorkflowStatus.RELEASED,
        ]

        for target_status in workflow_transitions:
            proposal, message = WorkflowService.transition_proposal(
                db, proposal.id, target_status, actor="system"
            )
            print(f"Transitioned proposal to {target_status.value}: {message}")

        print("\nSeed data created successfully!")
        print(f"  Project: {project.name}")
        print(f"  Requirements: {len(requirements)}")
        print(f"  Proposal: {proposal.proposal_id} (final status: {proposal.workflow_status.value})")

    finally:
        if owns_session:
            db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Seed ReleaseGuard demo data.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="seed even if the database already contains data",
    )
    args = parser.parse_args(argv)
    try:
        seed_data(force=args.force)
    except SeedRefusedError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())