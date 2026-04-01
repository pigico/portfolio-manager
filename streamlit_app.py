"""Entry point for Streamlit Cloud deployment.

This file sits at the repo root so Streamlit Cloud can find it.
"""

import sys
from pathlib import Path

# Add all skill script paths for imports
_root = Path(__file__).parent
for _skill in (_root / "skills").iterdir():
    _sp = _skill / "scripts"
    if _sp.exists() and str(_sp) not in sys.path:
        sys.path.insert(0, str(_sp))

# Now run the actual dashboard app
exec(open(_root / "skills" / "dashboard" / "scripts" / "app.py").read())
