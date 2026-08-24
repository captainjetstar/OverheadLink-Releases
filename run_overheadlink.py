from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from overheadlink.bootstrap import install_app_extensions, prepare_profile

prepare_profile()

from overheadlink import app as app_module

install_app_extensions(app_module.OverheadLinkApp)


if __name__ == "__main__":
    app_module.main()
