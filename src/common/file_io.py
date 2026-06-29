from pathlib import Path


def read_source_file(
    file_path: str | Path,
    encoding: str = "utf-8",
) -> str:
    """Read and return the contents of a source file."""

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(
            f"Source file was not found: {path}"
        )

    return path.read_text(encoding=encoding)