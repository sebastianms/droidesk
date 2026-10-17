import json
from pathlib import Path

from droidesk_api.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[3]  # apps/api/scripts/ -> repo root
CONTRACT_PATH = REPO_ROOT / "contracts" / "openapi.json"


def main() -> None:
    schema = create_app().openapi()
    document = json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False)
    CONTRACT_PATH.write_text(f"{document}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
