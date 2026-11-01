"""`python -m dogfood.panel.openapi`: imprime el OpenAPI del panel sin levantar el servidor."""

import json
import tempfile
from pathlib import Path

from dogfood.panel.app import crear_app_panel


def main() -> None:
    with tempfile.TemporaryDirectory() as raiz:
        print(json.dumps(crear_app_panel(Path(raiz)).openapi(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
