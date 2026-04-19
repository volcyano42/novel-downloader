import os
from importlib import import_module
from pathlib import Path
from typing import Any

def register_export_options() -> dict[str, Any]:
    export_options = {}
    exporter_dir = Path(__file__).parent.parent / "exporters"

    for file in os.listdir(exporter_dir):
        if file.endswith('.py') and file not in ['__init__.py',"base.py"]:
            module_name = file[:-3]
            try:
                module = import_module(f'exporters.{module_name}', __name__)
                output_class = getattr(module, f'{module_name.upper()}ExportOptions')
                export_options[module_name] = output_class
            except (ImportError, AttributeError) as e:
                print(f"load exporter failed {module_name} reason: {e}")

    return export_options

def register_exporter() -> dict[str, Any]:
    exporter = {}
    exporter_dir = Path(__file__).parent.parent / "exporters"

    for file in os.listdir(exporter_dir):
        if file.endswith('.py') and file not in ['__init__.py',"base.py"]:
            module_name = file[:-3]
            try:
                module = import_module(f'exporters.{module_name}', __name__)
                output_class = getattr(module, f'{module_name.upper()}Exporter')
                exporter[module_name] = output_class
            except (ImportError, AttributeError) as e:
                print(f"load exporter failed {module_name} reason: {e}")

    return exporter

def register_parser() -> dict[str, Any]:
    parser = {}
    parser_dir = Path(__file__).parent.parent / "parsers"

    for file in os.listdir(parser_dir):
        if file.endswith('.py') and file not in ['__init__.py',"base.py"]:
            module_name = file[:-3]
            try:
                module = import_module(f'parsers.{module_name}', __name__)
                output_class = getattr(module, f'{module_name.capitalize()}Parser')
                parser[module_name] = output_class
            except (ImportError, AttributeError) as e:
                print(f"load parser failed {module_name} reason: {e}")

    return parser
