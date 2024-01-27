import ast
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import cast
from typing import TypedDict
from typing import Unpack

import cappa
import httpx
import tomlkit
from falco import falco_version
from rich.progress import Progress
from rich.progress import SpinnerColumn
from rich.progress import TextColumn

RICH_SUCCESS_MARKER = "[green]SUCCESS:"
RICH_ERROR_MARKER = "[red]ERROR:"
RICH_INFO_MARKER = "[blue]INFO:"
RICH_COMMAND_MARKER = "[yellow]"
RICH_COMMAND_MARKER_END = "[/yellow]"


class FalcoConfig(TypedDict, total=False):
    revision: str
    blueprint: str
    skip: list[str]
    work: dict[str, str]
    htmx: str
    crud_utils: str


def write_falco_config(pyproject_path: Path, **kwargs: Unpack[TypedDict]) -> FalcoConfig:
    pyproject = tomlkit.parse(pyproject_path.read_text())
    existing_config = pyproject.get("tool", {}).get("falco", {})
    existing_config.update(**kwargs)
    pyproject["tool"] = {"falco": existing_config}
    pyproject_path.write_text(tomlkit.dumps(pyproject))
    return pyproject


def read_falco_config(pyproject_path: Path) -> FalcoConfig:
    pyproject = tomlkit.parse(pyproject_path.read_text())
    return cast(FalcoConfig, pyproject.get("tool", {}).get("falco", {}))


def clean_project_name(val: str) -> str:
    return val.strip().replace(" ", "_").replace("-", "_")


def get_pyproject_file() -> Path:
    pyproject_path = Path("pyproject.toml")
    if pyproject_path.exists():
        return pyproject_path
    raise cappa.Exit("Could not find a pyproject.toml file in the current directory.", code=1)


def get_project_name() -> str:
    pyproject = tomlkit.parse(get_pyproject_file().read_text())
    return pyproject["project"]["name"]


def get_author_info():
    pyproject = tomlkit.parse(get_pyproject_file().read_text())
    return pyproject["project"]["authors"][0]


@contextmanager
def simple_progress(description: str, display_text="[progress.description]{task.description}"):
    progress = Progress(SpinnerColumn(), TextColumn(display_text), transient=True)
    progress.add_task(description=description, total=None)
    try:
        yield progress.start()
    finally:
        progress.stop()


@contextmanager
def network_request_with_progress(url: str, description: str):
    try:
        with simple_progress(description):
            yield httpx.get(url)
    except httpx.ConnectError as e:
        msg = f"Connection error, {url} is not reachable."
        raise cappa.Exit(msg, code=1) from e


class ShellCodeError(Exception):
    pass


def run_in_shell(command: str, *, eval_result: bool = True):
    result = subprocess.run(
        ["python", "manage.py", "shell", "-c", command],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ShellCodeError(result.stderr)
    return ast.literal_eval(result.stdout) if eval_result else result.stdout.strip()


def is_new_falco_cli_available(*, fail_on_error: bool = False) -> bool:
    try:
        with network_request_with_progress(
            "https://pypi.org/pypi/falco-cli/json",
            "Checking for new falco version...",
        ) as response:
            latest_version = response.json()["info"]["version"]
            current_version = falco_version
            return latest_version != current_version
    except cappa.Exit:
        if fail_on_error:
            raise
        return False
