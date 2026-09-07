import sys
from pathlib import Path

from app_data_common import APP_DATA_FILES, repository_root, sha256


def add_api_source(root: Path) -> None:
    sys.path.insert(0, str(root / "apps" / "api" / "src"))


def main() -> None:
    root = repository_root()
    add_api_source(root)
    from bedashing_api.repositories import AppDataRepository

    repository = AppDataRepository(root / "app_data")
    manifest = repository.manifest()
    expected_names = set(APP_DATA_FILES)
    listed_names = {entry.file for entry in manifest.files}
    if listed_names != expected_names:
        raise ValueError(f"Manifest files differ: expected={expected_names}, found={listed_names}")

    for entry in manifest.files:
        path = root / "app_data" / entry.file
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.stat().st_size != entry.bytes:
            raise ValueError(f"Byte-size mismatch for {entry.file}")
        if sha256(path) != entry.sha256:
            raise ValueError(f"Checksum mismatch for {entry.file}")

    counts = repository.validate_relationships()
    if counts != manifest.validation.model_dump():
        expected = manifest.validation.model_dump()
        raise ValueError(f"Manifest validation counts differ: expected={expected}, found={counts}")
    print(f"Validated canonical app data: {manifest.validation.model_dump()}")


if __name__ == "__main__":
    main()
