"""Validation route."""

from __future__ import annotations

from fastapi import APIRouter

from studio.adapters.inbound.http.dependencies import ActorDep, ContainerDep
from studio.adapters.inbound.http.dtos.validation_report_response import ValidationReportResponse
from studio.adapters.inbound.http.mappers.validation_mapper import map_validation_report

__all__ = ["router"]

router = APIRouter()


@router.post("/validate", response_model=ValidationReportResponse)
def run_validation(container: ContainerDep, actor: ActorDep) -> ValidationReportResponse:
    """Run the playbook's intent tests + link checker and return the report."""
    return map_validation_report(container.run_validation().execute(actor=actor))
