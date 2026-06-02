"""HTML template loading."""

import os
from importlib import resources
from pathlib import Path
from typing import Optional

from now_playing.logging_config import LOGGER


def bundled_template(name: str) -> Optional[str]:
    try:
        template_path = resources.files("now_playing").joinpath("templates", name)
        return template_path.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        return None


def template_has_placeholders(template: str, required: tuple[str, ...]) -> tuple[bool, tuple[str, ...]]:
    missing = tuple(token for token in required if token not in template)
    return (len(missing) == 0, missing)


def load_html_template(name: str, override_env: str, fallback: str, required_placeholders: tuple[str, ...]) -> str:
    def read_candidate(path: Path, source_name: str) -> Optional[str]:
        try:
            template = path.read_text(encoding="utf-8")
        except OSError as exc:
            LOGGER.warning("Failed to read %s template %s: %s", source_name, path, exc)
            return None
        valid, missing = template_has_placeholders(template, required_placeholders)
        if valid:
            return template
        LOGGER.warning(
            "Ignoring %s template %s; missing placeholders: %s",
            source_name,
            path,
            ", ".join(missing),
        )
        return None

    override_path = os.environ.get(override_env, "").strip()
    if override_path:
        custom = read_candidate(Path(override_path), override_env)
        if custom is not None:
            return custom

    directory_override = os.environ.get("NOW_PLAYING_TEMPLATE_DIR", "").strip()
    if directory_override:
        candidate = Path(directory_override) / name
        directory_template = read_candidate(candidate, "NOW_PLAYING_TEMPLATE_DIR")
        if directory_template is not None:
            return directory_template

    bundled = bundled_template(name)
    if bundled is not None:
        valid, missing = template_has_placeholders(bundled, required_placeholders)
        if not valid:
            LOGGER.warning("Bundled template %s is missing placeholders: %s", name, ", ".join(missing))
            return fallback
        return bundled

    valid, missing = template_has_placeholders(fallback, required_placeholders)
    if not valid:
        LOGGER.warning("Fallback template %s is missing placeholders: %s", name, ", ".join(missing))
    return fallback
