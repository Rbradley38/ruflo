from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable

import click

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _read_package_json(root: Path) -> dict:
    package_file = root / "package.json"
    if not package_file.exists():
        raise click.ClickException(f"Package metadata not found at {package_file}")
    return json.loads(package_file.read_text(encoding="utf-8"))


def _iter_top_level(root: Path) -> Iterable[Path]:
    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if child.name.startswith("."):
            continue
        yield child


def _is_project_dir(path: Path) -> bool:
    return path.is_dir() and not path.name.startswith(".")


def _summarize_tree(root: Path, max_depth: int) -> dict:
    stats = {"dirs": 0, "files": 0, "top_level": []}
    for child in _iter_top_level(root):
        stats["top_level"].append(child.name)
        if child.is_dir():
            stats["dirs"] += 1
    total_dirs = 0
    total_files = 0
    ext_counter: Counter[str] = Counter()

    def walk(directory: Path, depth: int = 0) -> None:
        nonlocal total_dirs, total_files
        if depth > max_depth:
            return
        for child in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
            if child.name.startswith("."):
                continue
            if child.is_dir():
                total_dirs += 1
                walk(child, depth + 1)
            else:
                total_files += 1
                ext_counter[child.suffix.lower() or "<no-extension>"] += 1

    walk(root)
    stats["dirs_total"] = total_dirs
    stats["files_total"] = total_files
    stats["extensions"] = dict(sorted(ext_counter.items()))
    return stats


@click.group()
@click.version_option(version="0.1.0", prog_name="project-cli")
def cli() -> None:
    """Inspect the Ruflo project structure and workspace metadata."""


@cli.command("status")
@click.option(
    "--root",
    "root_path",
    type=click.Path(path_type=Path, exists=True, file_okay=False, dir_okay=True),
    default=PROJECT_ROOT,
    show_default=True,
    help="Project root to inspect.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def status(root_path: Path, as_json: bool) -> None:
    """Print an overview of the project."""
    package_data = _read_package_json(root_path)
    top_level = [child.name for child in _iter_top_level(root_path)]
    summary = {
        "project": package_data.get("name", "unknown"),
        "version": package_data.get("version", "unknown"),
        "root": str(root_path),
        "top_level": top_level[:12],
        "count": len(top_level),
    }
    if as_json:
        click.echo(json.dumps(summary, indent=2))
        return
    click.echo(f"Project: {summary['project']}")
    click.echo(f"Version: {summary['version']}")
    click.echo(f"Root: {summary['root']}")
    click.echo(f"Top-level items: {', '.join(summary['top_level']) if summary['top_level'] else 'none'}")


@cli.command("scan")
@click.option(
    "--root",
    "root_path",
    type=click.Path(path_type=Path, exists=True, file_okay=False, dir_okay=True),
    default=PROJECT_ROOT,
    show_default=True,
    help="Project root to scan.",
)
@click.option("--depth", default=2, show_default=True, type=click.IntRange(1, 5), help="Maximum directory depth to list.")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def scan(root_path: Path, depth: int, as_json: bool) -> None:
    """List key project areas and directories."""
    roots = [child for child in _iter_top_level(root_path) if _is_project_dir(child)]
    entries = [{"name": child.name, "kind": "dir" if child.is_dir() else "file"} for child in roots]
    if as_json:
        click.echo(json.dumps({"root": str(root_path), "depth": depth, "entries": entries[: depth * 10]}, indent=2))
        return
    click.echo(f"Project structure (depth {depth}):")
    for entry in entries[: depth * 10]:
        click.echo(f"  - {entry['name']}")


@cli.command("tree")
@click.option(
    "--root",
    "root_path",
    type=click.Path(path_type=Path, exists=True, file_okay=False, dir_okay=True),
    default=PROJECT_ROOT,
    show_default=True,
    help="Project root to render.",
)
@click.option("--max-depth", default=2, show_default=True, type=click.IntRange(1, 5), help="Maximum depth to render.")
def tree(root_path: Path, max_depth: int) -> None:
    """Render a concise directory tree for the workspace."""

    def walk(directory: Path, prefix: str = "", depth: int = 0) -> None:
        if depth > max_depth:
            return
        children = sorted(
            [p for p in directory.iterdir() if not p.name.startswith(".")],
            key=lambda p: (not p.is_dir(), p.name.lower()),
        )
        for index, child in enumerate(children):
            connector = "\\-- " if index == len(children) - 1 else "|-- "
            click.echo(f"{prefix}{connector}{child.name}")
            if child.is_dir() and depth < max_depth:
                next_prefix = prefix + ("    " if index == len(children) - 1 else "|   ")
                walk(child, next_prefix, depth + 1)

    click.echo(root_path.name)
    walk(root_path)


@cli.command("summary")
@click.option(
    "--root",
    "root_path",
    type=click.Path(path_type=Path, exists=True, file_okay=False, dir_okay=True),
    default=PROJECT_ROOT,
    show_default=True,
    help="Project root to summarize.",
)
@click.option("--max-depth", default=2, show_default=True, type=click.IntRange(1, 5), help="Maximum traversal depth for summary stats.")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def summary(root_path: Path, max_depth: int, as_json: bool) -> None:
    """Summarize the project layout and file types."""
    summary_data = _summarize_tree(root_path, max_depth)
    if as_json:
        click.echo(json.dumps(summary_data, indent=2))
        return
    click.echo(f"Root: {root_path}")
    click.echo(f"Top-level entries: {len(summary_data['top_level'])}")
    click.echo(f"Directories visited: {summary_data['dirs_total']}")
    click.echo(f"Files visited: {summary_data['files_total']}")
    if summary_data["extensions"]:
        click.echo("Extensions:")
        for ext, count in list(summary_data["extensions"].items())[:10]:
            click.echo(f"  - {ext}: {count}")


if __name__ == "__main__":
    cli()
