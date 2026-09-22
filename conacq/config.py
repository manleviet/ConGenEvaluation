"""
Shared pipeline configuration utilities.

Provides ModelConfig dataclass and config loading functions used by
all pipeline scripts (run_congen, run_cv, run_compare, etc.).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib


@dataclass
class ModelConfig:
    """Configuration for a single model in pipeline scripts.

    Attributes:
        name: Display name for the model
        oracle: Path to feature model (.uvl)
        bias: Path to bias JSON file
        examples: Path to examples JSON file (optional)
        folds_path: Path to pre-generated folds JSON (optional)
    """
    name: str
    oracle: str
    bias: str
    examples: Optional[str] = None
    folds_path: Optional[str] = None
    kb_dir: Optional[str] = None


def load_pipeline_config(config_path: str) -> Dict[str, Any]:
    """Load TOML pipeline configuration file.

    Args:
        config_path: Path to TOML config file

    Returns:
        Parsed config dictionary
    """
    with open(config_path, 'rb') as f:
        return tomllib.load(f)


def parse_models(config: Dict) -> List[ModelConfig]:
    """Parse [[models]] section from pipeline config.

    Handles both named models (eval configs) and path-only models
    (run_congen config) by deriving name from oracle path if missing.

    Args:
        config: Parsed TOML config dict

    Returns:
        List of ModelConfig instances

    Raises:
        ValueError: If a model entry is missing both 'oracle' and 'path'
    """
    models_data = config.get('models', [])
    result = []
    for i, m in enumerate(models_data):
        oracle = m.get('oracle', m.get('path', ''))
        if not oracle:
            raise ValueError(
                f"Model entry {i} missing 'oracle' (or 'path') field"
            )
        name = m.get('name', Path(oracle).stem)
        result.append(ModelConfig(
            name=name,
            oracle=oracle,
            bias=m['bias'],
            examples=m.get('examples'),
            folds_path=m.get('folds_path'),
            kb_dir=m.get('kb_dir'),
        ))
    return result


def find_cv_files(cv_path: Path) -> List[Path]:
    """Find unified CV JSON files from path.

    Matches *_cv_*.json pattern (unified CV output files).

    Args:
        cv_path: Path to a single CV file or directory containing CV files

    Returns:
        List of matching Path objects, sorted alphabetically
    """
    if cv_path.is_file() and cv_path.name.endswith('.json'):
        return [cv_path]
    if cv_path.is_dir():
        return sorted(cv_path.glob('*_cv_*.json'))
    return []


def find_kb_files(kb_path: Path) -> List[Path]:
    """Find KB JSON files from path (single file or directory).

    Matches *_kb.json and *_intersected_kb.json patterns.

    Args:
        kb_path: Path to a single KB file or directory containing KB files

    Returns:
        List of matching Path objects, sorted alphabetically
    """
    if kb_path.is_file():
        return [kb_path]
    if kb_path.is_dir():
        files = []
        for f in sorted(kb_path.glob('*_kb.json')):
            files.append(f)
        for f in sorted(kb_path.glob('*_intersected_kb.json')):
            if f not in files:
                files.append(f)
        return files
    return []
