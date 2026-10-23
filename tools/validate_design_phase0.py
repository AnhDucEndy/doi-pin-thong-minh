"""Read-only Phase 0 checks, using Python's standard library only.

Does not run the application, parse general YAML/SQL, or replace official
OpenAPI/JSON Schema validators. Prints evidence to stdout; writes no files.
"""

from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import json
import re
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "doi-pin-giai-doan-2"
CHECKS = []


def read(name):
    return (BUNDLE / name).read_text(encoding="utf-8-sig")


def load(name):
    return json.loads(read(name))


def check(name, condition, detail):
    CHECKS.append({"name": name, "status": "Passed" if condition else "Failed", "detail": detail})


def csv_rows(name):
    with (BUNDLE / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def docx_paragraphs(name):
    with ZipFile(BUNDLE / name) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    return ["".join(p.itertext()) for p in document.findall(".//w:body//w:p", ns)]


def flat_config(text):
    """Accept only the existing flat scalar YAML layout; reject other syntax."""
    values = {}
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        match = re.fullmatch(r"([a-z][a-z0-9_]*): ([A-Za-z0-9_.'-]+)", line)
        if not match:
            raise ValueError("Unsupported config syntax: " + line)
        key, value = match.groups()
        if key in values:
            raise ValueError("Duplicate config key: " + key)
        if value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        elif re.fullmatch(r"-?\d+", value):
            value = int(value)
        elif value == "null":
            value = None
        values[key] = value
    return values


def validate_current_flat_schema(config, schema):
    """Check every keyword used in the current config schema, and fail on new ones."""
    allowed_root = {"$schema", "title", "type", "additionalProperties", "required", "properties"}
    allowed_property = {"type", "const", "minimum", "maximum"}
    errors = []
    if set(schema) - allowed_root or schema["type"] != "object":
        errors.append("Unsupported root schema")
    errors.extend("Missing: " + key for key in schema["required"] if key not in config)
    if schema["additionalProperties"] is not False:
        errors.append("Unsupported additionalProperties")
    errors.extend("Extra: " + key for key in config if key not in schema["properties"])
    for key, value in config.items():
        if key not in schema["properties"]:
            continue
        rule = schema["properties"][key]
        if set(rule) - allowed_property:
            errors.append("Unsupported keyword: " + key)
        types = rule["type"] if isinstance(rule["type"], list) else [rule["type"]]
        matches = {"string": isinstance(value, str), "integer": type(value) is int,
                   "number": type(value) in (int, float), "null": value is None}
        if any(t not in matches for t in types) or not any(matches.get(t, False) for t in types):
            errors.append("Type: " + key)
        if "const" in rule and value != rule["const"]:
            errors.append("Const: " + key)
        if type(value) in (int, float):
            if "minimum" in rule and value < rule["minimum"]:
                errors.append("Minimum: " + key)
            if "maximum" in rule and value > rule["maximum"]:
                errors.append("Maximum: " + key)
    return errors


def main():
    fr = {f"FR{i:02}" for i in range(1, 20)}
    uc = {f"UC{i:02}" for i in range(1, 18)}
    br = {f"BR{i:02}" for i in range(1, 13)}
    tc = {f"TC{i:02}" for i in range(1, 20)}
    for manifest, base in [("baseline/SHA256.json", BUNDLE / "baseline"),
                           ("validation/delivery-sha256.json", BUNDLE)]:
        hashes = load(manifest)
        mismatches = [name for name, digest in hashes.items()
                      if not (base / name).is_file()
                      or hashlib.sha256((base / name).read_bytes()).hexdigest() != digest]
        check(manifest, not mismatches, {"files": len(hashes), "mismatches": mismatches})

    decisions = load("handoff/decisions.approved.json")
    approved = "APPROVED_FOR_SIMULATION_BY_USER"
    check("QD01-QD09", len(decisions) == 9
          and {d["id"] for d in decisions} == {f"QD{i:02}" for i in range(1, 10)}
          and all(d["status"] == approved for d in decisions),
          {d["id"]: d["status"] for d in decisions})
    config = flat_config(read("contracts/demo-config.approved.yaml"))
    errors = validate_current_flat_schema(config, load("contracts/demo-config.schema.json"))
    check("approved_config_current_schema_constraints", not errors,
          {"fields": len(config), "errors": errors, "official_validator": "Not Run"})
    expected = {"decision_status": approved, "environment": "simulation_only", "station_count": 2,
                "compartments_per_station": 6, "battery_family": "DEMO_FAMILY_A", "ownership_mode": "NETWORK",
                "payment_mode": "MOCK", "charge_timing": "BEFORE_RETURN", "refund_mode": "FULL_ADMIN_REVIEWED",
                "accounts_mode": "PRECREATED", "rfid_mode": "SIMULATED", "roles_mode": "SEPARATE",
                "fee_minor": 9000, "currency": "VND", "soc_min_pct": 80, "soh_min_pct": 80,
                "temperature_max_c": 40, "qr_ttl_seconds": 120, "login_max_failures": 5,
                "login_window_seconds": 900, "telemetry_interval_seconds": 5, "telemetry_stale_seconds": 15,
                "reservation_ttl_seconds": 120, "physical_step_timeout_seconds": 60, "command_ttl_seconds": 15,
                "payment_timeout_seconds": 30, "web_session_ttl_seconds": 3600, "verification_ttl_seconds": 120,
                "dashboard_poll_seconds": 3, "idempotency_retention_hours": 72,
                "staff_count": 5, "weeks": 10, "hours_per_person_week": 8}
    check("approved_policy_values", all(config.get(k) == v for k, v in expected.items()), expected)

    baseline = csv_rows("baseline/Truy-vet-yeu-cau.csv")
    trace = csv_rows("contracts/traceability.csv")
    check("FR_UC_TC_baseline_coverage", {r["FR"] for r in baseline} == fr
          and {x for r in baseline for x in r["Use Case"].split(",")} == uc
          and {r["Test"] for r in baseline} == tc, {"FR": len(fr), "UC": len(uc), "TC": len(tc)})
    base_map = {r["FR"]: r for r in baseline}
    differences = [r["FR"] for r in trace if r["FR"] not in base_map or any(
        r[new] != base_map[r["FR"]][old] for new, old in
        [("Module", "Module"), ("UC baseline", "Use Case"), ("TC baseline", "Test")])]
    check("GD2_trace_matches_GD1", len(trace) == 19 and {r["FR"] for r in trace} == fr
          and not differences, {"differences": differences})
    paragraphs = docx_paragraphs("baseline/Phan-tich-thiet-ke-doi-pin-GD1.docx")
    extracted_br = {p: paragraphs[i + 1] for i, p in enumerate(paragraphs[:-1]) if p in br}
    check("BR01-BR12_in_baseline", set(extracted_br) == br, extracted_br)
    tests = csv_rows("baseline/Test-case-du-kien.csv")
    check("TC01-TC19_definition_coverage", {r["Test ID"] for r in tests} == tc
          and all(r["FR"] == r["Test ID"].replace("TC", "FR") for r in tests),
          {"defined": len(tests), "executed": False})

    spec = read("contracts/openapi.yaml")
    catalog = load("contracts/api-catalog.json")
    # These are narrow structural checks of this file's layout, not YAML validation.
    ops = re.findall(r"^      operationId: (\w+)$", spec, re.M)
    blocks = re.split(r"^    (?:get|post|put|patch|delete):\s*$", spec.split("\ncomponents:")[0], flags=re.M)[1:]
    spec_fr, spec_uc, op_map = set(), set(), {}
    for block in blocks:
        op = re.search(r"^      operationId: (\w+)$", block, re.M)
        values = {}
        for key, prefix in [("x-fr", "FR"), ("x-uc", "UC")]:
            match = re.search(r"^      " + key + r":\n((?:      - " + prefix + r"\d{2}\n)+)", block, re.M)
            values[key] = re.findall(prefix + r"\d{2}", match[1]) if match else []
        if op:
            op_map[op[1]] = values
        spec_fr.update(values["x-fr"])
        spec_uc.update(values["x-uc"])
    check("openapi_operation_metadata", len(ops) == len(set(ops)) == len(op_map) == 50
          and spec_fr == fr and spec_uc == uc
          and all(v["x-fr"] and v["x-uc"] for v in op_map.values()),
          {"operations": len(ops), "FR": len(spec_fr), "UC": len(spec_uc), "scope": "text structure only"})
    check("catalog_matches_openapi_metadata", len(catalog) == len(ops)
          and {r[2] for r in catalog} == set(ops)
          and all(set(r[4].split(",")) == set(op_map[r[2]]["x-fr"])
                  and set(r[5].split(",")) == set(op_map[r[2]]["x-uc"]) for r in catalog),
          {"catalog_operations": len(catalog)})
    check("trace_operations_and_diagrams", all(
        set(r["Operation IDs"].split(";")) == {op for op, tags in op_map.items() if r["FR"] in tags["x-fr"]}
        and all((BUNDLE / "diagrams" / (d + ".puml")).is_file() for d in r["Diagrams"].split(";"))
        for r in trace), {"rows": len(trace)})

    sql = read("database/schema.sql")
    tables = re.findall(r"^CREATE TABLE (\w+) \(", sql, re.M)
    dictionary = load("database/data-dictionary.json")
    check("DDL_dictionary_tables", len(tables) == len(dictionary) == 24 and set(tables) == set(dictionary),
          {"DDL_tables": len(tables), "dictionary_tables": len(dictionary), "SQL_parser": "Not Run"})
    enums = load("contracts/state-enums.json")
    ddl_enums = {name: re.findall(r"'([^']+)'", values) for name, values in
                 re.findall(r"CREATE TYPE (\w+) AS ENUM \(([^;]+)\);", sql)}
    check("state_enums_match_DDL", enums == ddl_enums, {"enum_types": len(enums)})
    diagrams = list((BUNDLE / "diagrams").glob("*.puml"))
    diagram_errors = []
    for source in diagrams:
        text = source.read_text(encoding="utf-8-sig")
        if not text.startswith("@startuml") or not text.rstrip().endswith("@enduml"):
            diagram_errors.append(source.name)
        svg = source.with_suffix(".svg")
        ET.parse(svg)
        if "Syntax Error" in svg.read_text(encoding="utf-8-sig"):
            diagram_errors.append(svg.name)
        if not source.with_suffix(".png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            diagram_errors.append(source.with_suffix(".png").name)
    check("diagram_source_and_artifact_structure", len(diagrams) == 16 and not diagram_errors,
          {"sources": len(diagrams), "errors": diagram_errors, "rerendered": False, "visual_review": "Not Run"})

    sources = ["CODEX_START_HERE.md", "handoff/DECISIONS_APPROVED_2026-10-23.md",
               "handoff/decisions.approved.json", "contracts/demo-config.approved.yaml"]
    result = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
              "python_executable": sys.executable, "scope": "Phase 0 static checks; no business modules executed",
              "sources_sha256": {f: hashlib.sha256((BUNDLE / f).read_bytes()).hexdigest() for f in sources},
              "checks": CHECKS,
              "open_items": [
                  "P0-01: demo_policies.review_status cannot represent APPROVED_FOR_SIMULATION_BY_USER; migration decision required.",
                  "P0-02: official validators not installed; original validate_design.py checks proposed config and overwrites original evidence.",
                  "P0-03: missing-config HTTP status descriptions differ between DOCX and OpenAPI; align before contract tests."],
              "not_run": ["official JSON Schema validator", "OpenAPI validator", "PostgreSQL SQL parser",
                          "PostgreSQL migration", "API/UI/simulators", "TC01-TC19", "CT01-CT14", "NFR runtime checks"],
              "summary": {status: sum(c["status"] == status for c in CHECKS) for status in ("Passed", "Failed")}}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 1 if result["summary"]["Failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
