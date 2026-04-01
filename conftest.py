"""Root conftest — makes the project importable for tests."""

import sys
from pathlib import Path

# Add skills directories to path so we can import despite hyphens in dir names
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Map hyphenated skill dirs to importable names
risk_guard_path = project_root / "skills" / "risk-guard" / "scripts"
sys.path.insert(0, str(risk_guard_path.parent))
sys.path.insert(0, str(risk_guard_path))
