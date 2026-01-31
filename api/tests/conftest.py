import sys
from pathlib import Path


# ensure "api/app" importable as top-level package "app"
api_root = Path(__file__).resolve().parents[1]
api_root_str = str(api_root)
if api_root_str not in sys.path:
    sys.path.insert(0, api_root_str)
