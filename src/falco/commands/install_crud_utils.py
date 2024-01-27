from pathlib import Path
from typing import Annotated

import cappa
from falco.utils import FalcoConfig
from falco.utils import get_project_name
from falco.utils import read_falco_config
from falco.utils import simple_progress
from falco.utils import write_falco_config
from rich import print as rich_print

from .model_crud import extract_python_file_templates
from .model_crud import get_crud_blueprints_path
from .model_crud import render_to_string
from .model_crud import run_python_formatters


@cappa.command(help="Install utils necessary for CRUD views.", name="install-crud-utils")
class InstallCrudUtils:
    output_dir: Annotated[
        Path | None,
        cappa.Arg(default=None, help="The folder in which to install the crud utils."),
    ] = None

    def __call__(self, project_name: Annotated[str, cappa.Dep(get_project_name)]):
        pyproject_path = Path("pyproject.toml")
        falco_config = read_falco_config(pyproject_path) if pyproject_path.exists() else {}
        output_dir = self.output_dir or self.get_install_path(project_name=project_name, falco_config=falco_config)[0]

        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "__init__.py").touch(exist_ok=True)

        generated_files = []

        context = {"project_name": project_name}
        with simple_progress("Installing crud utils"):
            for file_path in (get_crud_blueprints_path() / "utils").iterdir():
                imports_template, code_template = extract_python_file_templates(file_path.read_text())
                filename = ".".join(file_path.name.split(".")[:-1])
                output_file = output_dir / filename
                output_file.touch(exist_ok=True)
                output_file.write_text(
                    render_to_string(imports_template, context)
                    + render_to_string(code_template, context)
                    + output_file.read_text()
                )
                generated_files.append(output_file)

        for file in generated_files:
            run_python_formatters(str(file))

        if pyproject_path.exists():
            write_falco_config(pyproject_path=pyproject_path, crud_utils=str(output_dir))

        rich_print(f"[green]CRUD Utils installed successfully to {output_dir}.")

    @classmethod
    def get_install_path(cls, project_name: str, falco_config: FalcoConfig) -> tuple[Path, bool]:
        if _import_path := falco_config.get("crud_utils"):
            return Path(_import_path), True
        return Path(f"{project_name}/core"), False
