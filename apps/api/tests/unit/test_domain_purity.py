import json
import subprocess
import sys

import pytest

FRAMEWORKS = ("fastapi", "starlette", "sqlmodel", "sqlalchemy", "pydantic")
PURE_MODULES = [
    "droidesk_api.tickets.lifecycle",
    "droidesk_api.sla.status",
    "droidesk_api.sla.calendar",
    "droidesk_api.core.errors",
    "droidesk_api.identity.enums",
    "droidesk_api.tickets.enums",
    "droidesk_api.sla.enums",
    "droidesk_api.audit.enums",
]
REPORT_LOADED_FRAMEWORKS = """
import importlib, json, sys

module, *frameworks = sys.argv[1:]
importlib.import_module(module)
loaded = {name.partition(".")[0] for name in sys.modules}
print(json.dumps(sorted(loaded & set(frameworks))))
"""


def frameworks_loaded_by(module: str) -> list[str]:
    """Importa el módulo en un intérprete limpio: aquí otros tests ya cargaron el framework."""
    result = subprocess.run(  # noqa: S603  (el módulo sale de PURE_MODULES)
        [sys.executable, "-I", "-c", REPORT_LOADED_FRAMEWORKS, module, *FRAMEWORKS],
        capture_output=True,
        text=True,
        check=True,
    )
    return list(json.loads(result.stdout))


@pytest.mark.parametrize("module", PURE_MODULES)
def test_domain_module_imports_no_framework(module: str) -> None:
    assert frameworks_loaded_by(module) == []


def test_the_guard_detects_a_framework_import() -> None:
    assert frameworks_loaded_by("droidesk_api.core.http_errors") != []
