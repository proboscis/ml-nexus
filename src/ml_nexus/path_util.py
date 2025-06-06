from pathlib import Path
import uuid


def path_hash(p: Path):
    if isinstance(p, str):
        p = Path(p)
    path_str = str(p.resolve())
    path_uuid = uuid.uuid5(uuid.NAMESPACE_URL, path_str)
    return str(path_uuid)
