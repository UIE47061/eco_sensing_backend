"""Idempotently seed test employee accounts (§0.2 of the App auth reference doc).

Usage: python seed_test_accounts.py

Requires SEED_TEST_ACCOUNT_PASSWORD in the environment (see .env.example) —
the plaintext password never lives in this file, only in .env, so this
script stays safe to commit. All test accounts use the @test.local domain;
clear them before going to production with:
    DELETE FROM employee WHERE email LIKE '%@test.local';
"""

import sys

from db.supabase import request_supabase
from services.auth import hash_password
from util.config import Env

TEST_COMPANY_NAME = "QA Sandbox"
TEST_DEPARTMENT_NAME = "QA"
TEST_ACCOUNTS = [
    {"email": "guava@test.local", "display_name": "Guava Tester"},
    {"email": "uie@test.local", "display_name": "UIE Tester"},
    {"email": "chun@test.local", "display_name": "Chun Tester"},
    {"email": "genie@test.local", "display_name": "Genie Tester"},
]


def find_one(table: str, **filters: str) -> dict | None:
    params: dict[str, str | int] = {"select": "*", "limit": 1}
    params.update({key: f"eq.{value}" for key, value in filters.items()})
    data = request_supabase("GET", table, params=params)
    return data[0] if data else None


def ensure_test_department() -> str:
    company = find_one("company", name=TEST_COMPANY_NAME)
    if not company:
        company = request_supabase(
            "POST",
            "company",
            json={"name": TEST_COMPANY_NAME},
            prefer="return=representation",
        )[0]
        print(f"created company {TEST_COMPANY_NAME}")

    department = find_one(
        "department", company_id=company["id"], name=TEST_DEPARTMENT_NAME
    )
    if not department:
        department = request_supabase(
            "POST",
            "department",
            json={"company_id": company["id"], "name": TEST_DEPARTMENT_NAME},
            prefer="return=representation",
        )[0]
        print(f"created department {TEST_DEPARTMENT_NAME}")

    return department["id"]


def seed() -> None:
    if not Env.SEED_TEST_ACCOUNT_PASSWORD:
        sys.exit(
            "SEED_TEST_ACCOUNT_PASSWORD is not set (see .env.example); refusing to seed."
        )

    password_hash = hash_password(Env.SEED_TEST_ACCOUNT_PASSWORD)
    department_id = ensure_test_department()

    for account in TEST_ACCOUNTS:
        existing = find_one("employee", email=account["email"])
        if existing:
            request_supabase(
                "PATCH",
                "employee",
                params={"id": f"eq.{existing['id']}"},
                json={"password_hash": password_hash},
            )
            print(f"updated password_hash for {account['email']}")
        else:
            request_supabase(
                "POST",
                "employee",
                json={
                    "department_id": department_id,
                    "email": account["email"],
                    "display_name": account["display_name"],
                    "password_hash": password_hash,
                },
                prefer="return=representation",
            )
            print(f"created {account['email']}")


if __name__ == "__main__":
    seed()
