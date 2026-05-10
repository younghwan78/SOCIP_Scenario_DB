"""Unit test conftest — dashboard/ 패키지 경로를 sys.path에 추가."""
import sys
from pathlib import Path

# dashboard/ 패키지는 project root에 위치 (src/ 아님) — 명시적으로 경로 추가
_ROOT = Path(__file__).parent.parent.parent  # 02_ScenarioDB/
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
