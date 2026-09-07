import shutil
import subprocess
import sys

from app_data_common import APP_DATA_FILES, repository_root, sha256


def main() -> None:
    root = repository_root()
    subprocess.run([sys.executable, str(root / "scripts" / "validate_app_data.py")], check=True)

    source = root / "app_data"
    destination = root / "apps" / "web" / "public" / "app_data"
    destination.mkdir(parents=True, exist_ok=True)
    for name in (*APP_DATA_FILES, "app_manifest.json"):
        shutil.copy2(source / name, destination / name)
        if sha256(source / name) != sha256(destination / name):
            raise RuntimeError(f"Copied app-data checksum mismatch for {name}")
    print(f"Synchronized {len(APP_DATA_FILES) + 1} validated files to {destination}.")


if __name__ == "__main__":
    main()
