#!/usr/bin/env python3
"""
ArxPrism preflight checks ("doctor")

Goal: fail fast before running the pipeline by validating:
- required envs (LLM_*)
- Redis connectivity (optional)
- Neo4j connectivity
- arXiv search reachability (optional)
- LLM call + schema validation (optional, costs tokens)

Usage:
  python run_doctor.py
  DOCTOR_RUN_ARXIV=1 python run_doctor.py
  DOCTOR_RUN_LLM=1 python run_doctor.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


def _print(result: CheckResult) -> None:
    status = "OK" if result.ok else "FAIL"
    line = f"[{status}] {result.name}"
    if result.detail:
        line += f" - {result.detail}"
    print(line)


def _is_placeholder_key(value: str) -> bool:
    v = (value or "").strip()
    if not v:
        return True
    lowered = v.lower()
    return "your-api-key" in lowered or "sk-your" in lowered or v.endswith("-here")


async def _check_env() -> CheckResult:
    from src.core.config import settings

    if not settings.llm_api_key or _is_placeholder_key(settings.llm_api_key):
        return CheckResult(
            name="LLM_API_KEY",
            ok=False,
            detail="missing or placeholder; set LLM_API_KEY in .env",
        )

    for name, val in (
        ("LLM_TRIAGE_MODEL", settings.llm_triage_model),
        ("LLM_EXTRACTOR_MODEL", settings.llm_extractor_model),
        ("LLM_RESOLUTION_MODEL", settings.llm_resolution_model),
    ):
        if not val or not str(val).strip():
            return CheckResult(
                name=name,
                ok=False,
                detail=f"missing; set {name} in .env",
            )

    if settings.llm_base_url is not None and settings.llm_base_url.strip() == "":
        return CheckResult(name="LLM_BASE_URL", ok=False, detail="empty string; unset it or provide a URL")

    return CheckResult(
        name="LLM envs",
        ok=True,
        detail=(
            f"triage={settings.llm_triage_model}, extract={settings.llm_extractor_model}, "
            f"resolution={settings.llm_resolution_model}, base_url={settings.llm_base_url or '(default)'}"
        ),
    )


async def _check_redis() -> CheckResult:
    try:
        import redis  # type: ignore
        from src.core.config import settings

        r = redis.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        return CheckResult(name="Redis", ok=True, detail=settings.redis_url)
    except Exception as e:
        return CheckResult(name="Redis", ok=False, detail=str(e))


async def _check_neo4j() -> CheckResult:
    try:
        from src.database.neo4j_client import neo4j_client

        await neo4j_client.connect()
        ok = await neo4j_client.verify_connectivity()
        return CheckResult(name="Neo4j", ok=ok, detail="connected" if ok else "connectivity check failed")
    except Exception as e:
        return CheckResult(name="Neo4j", ok=False, detail=str(e))


async def _check_arxiv() -> CheckResult:
    try:
        from src.services.arxiv_radar import arxiv_radar

        papers = await arxiv_radar.fetch_recent_papers("site reliability engineering", max_results=1)
        if not papers:
            return CheckResult(name="arXiv search+fetch", ok=False, detail="no paper fetched (rate limit or fetch fail)")
        return CheckResult(name="arXiv search+fetch", ok=True, detail=f"fetched {papers[0].arxiv_id}")
    except Exception as e:
        return CheckResult(name="arXiv search+fetch", ok=False, detail=str(e))


async def _check_llm() -> CheckResult:
    try:
        from src.services.llm_extractor import llm_extractor

        # Minimal paper text to validate JSON mode + schema
        paper_text = "Title: Test Paper\nAbstract: This paper studies site reliability engineering practices.\n"
        extraction = await llm_extractor.extract(
            paper_text=paper_text,
            paper_id="0000.00000",
            title="Test Paper",
            authors=["Test Author"],
            publication_date="1970-01-01",
        )
        if extraction is None:
            return CheckResult(name="LLM call + schema validate", ok=False, detail="returned None (see logs)")
        return CheckResult(name="LLM call + schema validate", ok=True, detail=f"is_relevant={extraction.is_relevant_to_domain}")
    except Exception as e:
        return CheckResult(name="LLM call + schema validate", ok=False, detail=str(e))


async def main() -> int:
    print("ArxPrism doctor\n")

    results: list[CheckResult] = []

    results.append(await _check_env())
    results.append(await _check_neo4j())

    if os.getenv("DOCTOR_RUN_REDIS", "1") == "1":
        results.append(await _check_redis())

    if os.getenv("DOCTOR_RUN_ARXIV", "0") == "1":
        results.append(await _check_arxiv())

    if os.getenv("DOCTOR_RUN_LLM", "0") == "1":
        results.append(await _check_llm())

    print("")
    for r in results:
        _print(r)

    failed = [r for r in results if not r.ok]
    if failed:
        print(f"\nDoctor: {len(failed)} check(s) failed.")
        return 1

    print("\nDoctor: all checks passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        raise SystemExit(130)

