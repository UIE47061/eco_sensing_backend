from typing import Any
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.crud import (
    create_record,
    delete_record,
    get_record,
    list_records,
    update_record,
)

router = APIRouter(prefix="/api", tags=["Organizations"])


class CompanyCreate(BaseModel):
    name: str = Field(..., examples=["Eco Sensing Inc."])
    baseline_year: int | None = Field(default=None, examples=[2024])
    net_zero_year: int | None = Field(default=None, examples=[2050])


class CompanyUpdate(BaseModel):
    name: str | None = None
    baseline_year: int | None = None
    net_zero_year: int | None = None


class DepartmentCreate(BaseModel):
    company_id: UUID
    name: str = Field(..., examples=["Operations"])
    primary_metric: str | None = Field(default=None, examples=["co2e_kg"])


class DepartmentUpdate(BaseModel):
    company_id: UUID | None = None
    name: str | None = None
    primary_metric: str | None = None


class EmployeeCreate(BaseModel):
    department_id: UUID
    id_token: str | None = None
    display_name: str = Field(..., examples=["Alex Chen"])
    email: str = Field(..., examples=["alex@example.com"])
    level: int = 1
    carbon_coin: int = 0


class EmployeeUpdate(BaseModel):
    department_id: UUID | None = None
    id_token: str | None = None
    display_name: str | None = None
    email: str | None = None
    level: int | None = None
    carbon_coin: int | None = None


def dump_payload(payload: BaseModel) -> dict[str, Any]:
    return payload.model_dump(exclude_none=True, mode="json")


@router.get("/companies")
def list_companies(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return list_records("company", limit=limit, offset=offset)


@router.post("/companies", status_code=201)
def create_company(payload: CompanyCreate) -> dict[str, Any]:
    return create_record("company", dump_payload(payload))


@router.get("/companies/{company_id}")
def get_company(company_id: UUID) -> dict[str, Any]:
    return get_record("company", company_id)


@router.patch("/companies/{company_id}")
def update_company(company_id: UUID, payload: CompanyUpdate) -> dict[str, Any]:
    return update_record("company", company_id, dump_payload(payload))


@router.delete("/companies/{company_id}")
def delete_company(company_id: UUID) -> dict[str, Any]:
    return delete_record("company", company_id)


@router.get("/departments")
def list_departments(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return list_records("department", limit=limit, offset=offset)


@router.post("/departments", status_code=201)
def create_department(payload: DepartmentCreate) -> dict[str, Any]:
    return create_record("department", dump_payload(payload))


@router.get("/departments/{department_id}")
def get_department(department_id: UUID) -> dict[str, Any]:
    return get_record("department", department_id)


@router.patch("/departments/{department_id}")
def update_department(department_id: UUID, payload: DepartmentUpdate) -> dict[str, Any]:
    return update_record("department", department_id, dump_payload(payload))


@router.delete("/departments/{department_id}")
def delete_department(department_id: UUID) -> dict[str, Any]:
    return delete_record("department", department_id)


@router.get("/employees")
def list_employees(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return list_records("employee", limit=limit, offset=offset)


@router.post("/employees", status_code=201)
def create_employee(payload: EmployeeCreate) -> dict[str, Any]:
    return create_record("employee", dump_payload(payload))


@router.get("/employees/{employee_id}")
def get_employee(employee_id: UUID) -> dict[str, Any]:
    return get_record("employee", employee_id)


@router.patch("/employees/{employee_id}")
def update_employee(employee_id: UUID, payload: EmployeeUpdate) -> dict[str, Any]:
    return update_record("employee", employee_id, dump_payload(payload))


@router.delete("/employees/{employee_id}")
def delete_employee(employee_id: UUID) -> dict[str, Any]:
    return delete_record("employee", employee_id)
