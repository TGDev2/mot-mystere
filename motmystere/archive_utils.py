from pathlib import Path, PurePosixPath
import shutil
import zipfile


class ArchiveInspectionError(ValueError):
    pass


def normalize_archive_name(filename):
    raw_name = str(filename or "").replace("\\", "/").strip()
    if not raw_name:
        raise ArchiveInspectionError("L'archive contient une entree vide.")
    if raw_name.startswith("/"):
        raise ArchiveInspectionError("L'archive contient un chemin absolu interdit.")

    normalized = PurePosixPath(raw_name)
    parts = normalized.parts
    if not parts:
        raise ArchiveInspectionError("L'archive contient une entree vide.")
    if any(part in {"", ".", ".."} for part in parts):
        raise ArchiveInspectionError("L'archive contient un chemin relatif interdit.")
    if ":" in parts[0]:
        raise ArchiveInspectionError("L'archive contient un chemin Windows interdit.")
    return normalized


def extract_archive_to_staging(archive_path, staging_root):
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            if not members:
                raise ArchiveInspectionError("L'archive est vide.")

            normalized_names = {}
            seen_names = set()
            for member in members:
                normalized_name = normalize_archive_name(member.filename)
                if normalized_name in seen_names:
                    raise ArchiveInspectionError("L'archive contient deux entrees en conflit.")
                seen_names.add(normalized_name)
                normalized_names[member.filename] = normalized_name

            for member in members:
                normalized_name = normalized_names[member.filename]
                destination = Path(staging_root).joinpath(*normalized_name.parts)
                if member.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue

                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member, "r") as source, destination.open("wb") as target:
                    shutil.copyfileobj(source, target)
    except ArchiveInspectionError:
        raise
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        raise ArchiveInspectionError(f"Archive invalide: {exc}") from exc

    return tuple(normalized_names.values())
