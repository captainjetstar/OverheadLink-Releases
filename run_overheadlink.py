from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from overheadlink.bootstrap import prepare_profile
from overheadlink.runtime import EnhancedOverheadLinkApp
from overheadlink.v0310_fix import ensure_adirs_required


def main() -> None:
    prepare_profile()
    ensure_adirs_required()
    app = EnhancedOverheadLinkApp()
    app.mainloop()


if __name__ == "__main__":
    main()
