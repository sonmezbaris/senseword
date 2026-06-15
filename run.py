"""Start the SenseWord development server.

Always run from the ``senseword/`` project root (the folder that contains
``app/`` and ``requirements.txt``). This script sets up the Python path and
working directory for you, so it also works if invoked as
``python senseword/run.py`` from the parent folder.

    cd senseword
    python run.py

Equivalent:

    cd senseword
    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Make ``import app`` work regardless of where the command was launched.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# SQLite DB path and uvicorn reload both depend on the working directory.
os.chdir(ROOT)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
