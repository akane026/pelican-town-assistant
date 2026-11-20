#!/usr/bin/env python3
"""Offline environment smoke using synthetic fixtures, never a V02 result.

Run with the project's virtual environment:
    .venv/bin/python verification/probes/environment_probe.py

The parent uses only the standard library. Each phase runs in a fresh process;
the graph/provenance writer exits before the reader starts. Every invocation
keeps its own artifacts and logs, including failed invocations.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from uuid import uuid4


SCOPE = "ENVIRONMENT_SMOKE"
NOTICE = (
    "Synthetic environment fixtures only. This does not verify real Wiki data, "
    "game rules, screenshots, retrieval quality, or V02."
)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULT_ROOT = PROJECT_ROOT / "verification/results/environment/smoke"
LOG_ROOT = PROJECT_ROOT / "verification/logs/environment"
OPTIONAL_ML_DISTRIBUTIONS = (
    "torch", "spacy", "transformers", "sentence-transformers", "gensim"
)
OPTIONAL_ML_MODULES = (
    "torch", "spacy", "transformers", "sentence_transformers", "gensim"
)
FIXTURE_SOURCE = "fixture:environment-smoke"
FIXTURE_LOCATION = "environment_probe.py:synthetic_fixture"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def check(result: dict, name: str, condition: bool, detail: object = None) -> None:
    result["assertions"].append(
        {"name": name, "passed": bool(condition), "detail": detail}
    )
    if not condition:
        raise AssertionError(name)


def installed_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def deny_network(attempts: list[dict]) -> None:
    """Prevent any dependency from using the network during a smoke worker."""
    def audit(event: str, args: tuple) -> None:
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
            # Deliberately omit addresses, headers, and environment values.
            attempts.append({"event": event, "blocked": True})
            raise RuntimeError("Network access is disabled for ENVIRONMENT_SMOKE")
    sys.addaudithook(audit)


def fixture_data() -> dict:
    return {
        "entities": [
            {
                "id": "fixture:item",
                "type": "Item",
                "name": "环境测试物品",
                "metadata": {"fixture": True, "scope": SCOPE},
            },
            {
                "id": "fixture:machine",
                "type": "ProcessingMachine",
                "name": "环境测试设备",
                "metadata": {"fixture": True, "scope": SCOPE},
            },
        ],
        "relationships": [
            {
                "id": "fixture:can_process",
                "source": "fixture:machine",
                "target": "fixture:item",
                "type": "CAN_PROCESS",
                "metadata": {"fixture": True, "scope": SCOPE, "batch_size": 2},
            }
        ],
    }


def check_graph(result: dict, graph: dict, prefix: str) -> None:
    check(result, f"{prefix}_is_dict", isinstance(graph, dict))
    entities = graph.get("entities", [])
    relationships = graph.get("relationships", [])
    check(result, f"{prefix}_two_entities", len(entities) == 2, len(entities))
    check(result, f"{prefix}_one_relationship", len(relationships) == 1, len(relationships))
    check(
        result, f"{prefix}_entity_ids",
        {entity["id"] for entity in entities} == {"fixture:item", "fixture:machine"},
    )
    edge = relationships[0]
    check(
        result, f"{prefix}_edge_identity_and_direction",
        (edge.get("id"), edge.get("source"), edge.get("target"), edge.get("type"))
        == ("fixture:can_process", "fixture:machine", "fixture:item", "CAN_PROCESS"),
    )
    check(
        result, f"{prefix}_edge_metadata",
        edge.get("metadata") == {"fixture": True, "scope": SCOPE, "batch_size": 2},
    )
    check(
        result, f"{prefix}_unicode_name",
        next(entity for entity in entities if entity["id"] == "fixture:item")["name"]
        == "环境测试物品",
    )


def check_provenance(result: dict, manager: object, prefix: str) -> None:
    from semantica.provenance import verify_checksum

    summaries = []
    for entity_id in ("fixture:item", "fixture:can_process"):
        record = manager.get_provenance(entity_id)
        check(result, f"{prefix}_{entity_id}_present", record is not None)
        check(result, f"{prefix}_{entity_id}_source", record["source_document"] == FIXTURE_SOURCE)
        check(result, f"{prefix}_{entity_id}_location", record["source_location"] == FIXTURE_LOCATION)
        check(result, f"{prefix}_{entity_id}_fixture_flag", record["metadata"].get("fixture") is True)
        check(result, f"{prefix}_{entity_id}_scope", record["metadata"].get("scope") == SCOPE)
        entries = manager.trace_lineage(entity_id)
        check(result, f"{prefix}_{entity_id}_lineage", len(entries) >= 1, len(entries))
        check(result, f"{prefix}_{entity_id}_checksum", all(verify_checksum(entry) for entry in entries))
        lineage = manager.get_lineage(entity_id)
        check(result, f"{prefix}_{entity_id}_lineage_dict", isinstance(lineage, dict))
        summaries.append({
            "entity_id": entity_id,
            "source_document": record["source_document"],
            "source_location": record["source_location"],
            "metadata": record["metadata"],
            "lineage_entries": len(entries),
        })
    result["provenance_records"] = summaries


def inspect_environment(result: dict) -> None:
    prefix = Path(sys.prefix).resolve()
    result["python"] = {
        "version": sys.version,
        "executable": sys.executable,
        "prefix": sys.prefix,
        "base_prefix": sys.base_prefix,
        "machine": platform.machine(),
        "platform": platform.platform(),
    }
    check(result, "isolated_virtual_environment", sys.prefix != sys.base_prefix)
    check(result, "project_virtual_environment", prefix == (PROJECT_ROOT / ".venv").resolve())
    check(result, "python_supported_by_semantica_0_7", (3, 10) <= sys.version_info[:2] < (3, 14))
    check(result, "native_arm64", platform.machine() == "arm64", platform.machine())
    pyvenv = prefix / "pyvenv.cfg"
    config = pyvenv.read_text(encoding="utf-8")
    check(result, "system_site_packages_disabled", "include-system-site-packages = false" in config.lower())
    distributions = (
        "semantica", "beautifulsoup4", "lxml", "httpx", "Pillow", "PyYAML", "pytest"
    )
    result["package_versions"] = {name: installed_version(name) for name in distributions}
    check(result, "semantica_version_0_7_0", result["package_versions"]["semantica"] == "0.7.0")
    check(result, "required_packages_installed", all(result["package_versions"].values()))
    result["optional_ml_packages"] = {
        name: installed_version(name) for name in OPTIONAL_ML_DISTRIBUTIONS
    }
    check(result, "optional_ml_packages_not_installed", not any(result["optional_ml_packages"].values()))
    result["imports"] = []
    for module_name in (
        "semantica", "semantica.kg", "semantica.provenance", "semantica.export",
        "bs4", "lxml.etree", "httpx", "PIL.Image", "yaml", "pytest",
    ):
        started = time.monotonic()
        module = importlib.import_module(module_name)
        result["imports"].append({
            "module": module_name,
            "file": getattr(module, "__file__", None),
            "elapsed_seconds": round(time.monotonic() - started, 6),
        })
    import semantica
    from semantica.kg import GraphBuilder
    from semantica.provenance import ProvenanceManager, SQLiteStorage
    from semantica.export import JSONExporter

    check(result, "semantica_imported_from_project_venv", Path(semantica.__file__).resolve().is_relative_to(prefix))
    result["api_signatures"] = {
        "GraphBuilder": str(inspect.signature(GraphBuilder)),
        "GraphBuilder.build": str(inspect.signature(GraphBuilder.build)),
        "JSONExporter.export_knowledge_graph": str(inspect.signature(JSONExporter.export_knowledge_graph)),
        "ProvenanceManager": str(inspect.signature(ProvenanceManager)),
        "ProvenanceManager.track_entity": str(inspect.signature(ProvenanceManager.track_entity)),
        "SQLiteStorage": str(inspect.signature(SQLiteStorage)),
    }


def write_fixture(result: dict, run_dir: Path) -> None:
    from semantica.kg import GraphBuilder
    from semantica.export import JSONExporter
    from semantica.provenance import ProvenanceManager

    fixture = fixture_data()
    write_json(run_dir / "fixture.json", {"scope": SCOPE, "fixture": True, "notice": NOTICE, "data": fixture})
    builder = GraphBuilder(
        merge_entities=False, resolve_conflicts=False,
        enable_temporal=False, graph_store=None,
    )
    graph = builder.build(sources=[fixture], extract=False)
    check_graph(result, graph, "built_graph")
    graph_path = run_dir / "graph.json"
    JSONExporter().export_knowledge_graph(graph, str(graph_path), format="json")
    check(result, "graph_export_created", graph_path.is_file())
    exported = json.loads(graph_path.read_text(encoding="utf-8"))
    check_graph(result, exported, "exported_graph")
    check(result, "export_preserves_entities", exported["entities"] == graph["entities"])
    check(result, "export_preserves_relationships", exported["relationships"] == graph["relationships"])

    db_path = run_dir / "provenance.sqlite3"
    manager = ProvenanceManager(storage_path=str(db_path))
    metadata = {"scope": SCOPE, "fixture": True}
    entity_entry = manager.track_entity(
        entity_id="fixture:item", source=FIXTURE_SOURCE,
        source_location=FIXTURE_LOCATION,
        source_quote="Synthetic environment fixture; not a game fact.",
        entity_type="environment_fixture", metadata=metadata,
    )
    check(result, "entity_tracking_returned_entry", entity_entry is not None)
    relationship_entry = manager.track_relationship(
        relationship_id="fixture:can_process", source=FIXTURE_SOURCE,
        source_location=FIXTURE_LOCATION, metadata=metadata,
    )
    check(result, "relationship_tracking_returned_entry", relationship_entry is not None)
    check(result, "provenance_database_created", db_path.is_file() and db_path.stat().st_size > 0)
    check_provenance(result, manager, "write_then_read")
    result["artifacts"] = {"graph": str(graph_path), "provenance": str(db_path), "fixture": str(run_dir / "fixture.json")}
    result["graph_summary"] = {"entities": len(graph["entities"]), "relationships": len(graph["relationships"])}


def read_fixture(result: dict, run_dir: Path) -> None:
    from semantica.kg import GraphBuilder
    from semantica.provenance import ProvenanceManager

    writer_result = json.loads((run_dir / "write.result.json").read_text(encoding="utf-8"))
    check(result, "writer_succeeded", writer_result["status"] == "PASS")
    check(result, "reader_is_new_process", writer_result["pid"] != os.getpid())
    exported = json.loads((run_dir / "graph.json").read_text(encoding="utf-8"))
    check_graph(result, exported, "reopened_json")
    rebuilt = GraphBuilder(
        merge_entities=False, resolve_conflicts=False,
        enable_temporal=False, graph_store=None,
    ).build(sources=[exported], extract=False)
    check_graph(result, rebuilt, "reloaded_graph")
    check(result, "reload_preserves_entities", rebuilt["entities"] == exported["entities"])
    check(result, "reload_preserves_relationships", rebuilt["relationships"] == exported["relationships"])
    result["graph_query"] = [
        {"id": edge["id"], "target": edge["target"], "batch_size": edge["metadata"]["batch_size"]}
        for edge in rebuilt["relationships"]
        if edge["source"] == "fixture:machine" and edge["type"] == "CAN_PROCESS"
    ]
    check(
        result, "query_uses_reloaded_graph",
        result["graph_query"] == [{"id": "fixture:can_process", "target": "fixture:item", "batch_size": 2}],
    )
    manager = ProvenanceManager(storage_path=str(run_dir / "provenance.sqlite3"))
    check_provenance(result, manager, "reopened_database")


def worker(phase: str, run_dir: Path) -> int:
    result = {
        "scope": SCOPE, "fixture": True, "notice": NOTICE, "v02_status": "NOT_RUN",
        "phase": phase, "pid": os.getpid(), "started_at": utc_now(), "assertions": [],
    }
    attempts: list[dict] = []
    deny_network(attempts)
    started = time.monotonic()
    try:
        if phase == "inspect":
            inspect_environment(result)
        elif phase == "write":
            write_fixture(result, run_dir)
        elif phase == "read":
            read_fixture(result, run_dir)
        loaded = [name for name in OPTIONAL_ML_MODULES if name in sys.modules]
        result["optional_ml_modules_loaded"] = loaded
        check(result, "no_optional_ml_modules_loaded", not loaded, loaded)
        check(result, "no_network_attempts", not attempts, attempts)
        result["status"] = "PASS"
        returncode = 0
    except Exception as exc:
        result["status"] = "FAIL"
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
        traceback.print_exc()
        returncode = 1
    result["network_attempts"] = attempts
    result["returncode"] = returncode
    result["finished_at"] = utc_now()
    result["elapsed_seconds"] = round(time.monotonic() - started, 6)
    write_json(run_dir / f"{phase}.result.json", result)
    print(json.dumps({"scope": SCOPE, "phase": phase, "status": result["status"], "assertions": len(result["assertions"])}, ensure_ascii=False))
    return returncode


def run_step(name: str, argv: list[str], run_dir: Path, run_id: str, env: dict) -> dict:
    stdout_path = LOG_ROOT / f"{run_id}.{name}.stdout.log"
    stderr_path = LOG_ROOT / f"{run_id}.{name}.stderr.log"
    step = {
        "name": name, "argv": argv, "command": shlex.join(argv), "cwd": str(PROJECT_ROOT),
        "started_at": utc_now(), "stdout": str(stdout_path), "stderr": str(stderr_path),
        "assertions": [],
    }
    started = time.monotonic()
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        try:
            completed = subprocess.run(
                argv, cwd=PROJECT_ROOT, env=env, stdin=subprocess.DEVNULL,
                stdout=stdout, stderr=stderr, timeout=120, check=False,
            )
            step["returncode"] = completed.returncode
        except subprocess.TimeoutExpired:
            step["returncode"] = None
            step["error"] = "TIMEOUT after 120 seconds; child process was killed"
        except OSError as exc:
            step["returncode"] = None
            step["error"] = f"{type(exc).__name__}: {exc}"
    step["elapsed_seconds"] = round(time.monotonic() - started, 6)
    step["finished_at"] = utc_now()
    step["status"] = "PASS" if step["returncode"] == 0 else "FAIL"
    phase_result = run_dir / f"{name}.result.json"
    if phase_result.is_file():
        step["result_file"] = str(phase_result)
        detail = json.loads(phase_result.read_text(encoding="utf-8"))
        step["assertions"] = detail["assertions"]
        if detail["status"] != "PASS":
            step["status"] = "FAIL"
    elif name == "pip-check":
        step["assertions"] = [{"name": "pip_dependency_consistency", "passed": step["returncode"] == 0}]
    else:
        step["status"] = "FAIL"
        step["assertions"] = [{"name": "worker_result_created", "passed": False}]
    return step


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("inspect", "write", "read"), help=argparse.SUPPRESS)
    parser.add_argument("--run-dir", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.phase:
        if args.run_dir is None:
            parser.error("--run-dir is required for a worker phase")
        return worker(args.phase, args.run_dir.resolve())

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid4().hex[:8]
    run_dir = RESULT_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({
        "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_NO_INDEX": "1", "PIP_NO_CACHE_DIR": "1",
        "SEMANTICA_DISABLE_PROGRESS": "1", "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
    })
    report = {
        "scope": SCOPE, "fixture": True, "notice": NOTICE, "v02_status": "NOT_RUN",
        "run_id": run_id, "started_at": utc_now(), "artifacts_directory": str(run_dir),
        "command": shlex.join([sys.executable, str(Path(__file__).resolve())]), "steps": [],
    }
    report["steps"].append(run_step("pip-check", [sys.executable, "-m", "pip", "check"], run_dir, run_id, env))
    for phase in ("inspect", "write", "read"):
        argv = [sys.executable, str(Path(__file__).resolve()), "--phase", phase, "--run-dir", str(run_dir)]
        if phase == "read" and report["steps"][-1]["status"] != "PASS":
            report["steps"].append({
                "name": phase, "argv": argv, "command": shlex.join(argv), "returncode": None,
                "status": "BLOCKED", "reason": "Writer did not pass; no reload claim is possible.",
                "assertions": [{"name": "writer_success_required", "passed": False}],
            })
            continue
        report["steps"].append(run_step(phase, argv, run_dir, run_id, env))
    report["finished_at"] = utc_now()
    report["status"] = "PASS" if all(step["status"] == "PASS" for step in report["steps"]) else "FAIL"
    report_path = run_dir / "result.json"
    write_json(report_path, report)
    print(json.dumps({"scope": SCOPE, "status": report["status"], "v02_status": "NOT_RUN", "report": str(report_path)}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
