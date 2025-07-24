# Package Installation Guide

This guide explains how to install the Confluence Q&A System as a proper Python package to avoid manual `sys.path` juggling.

## Quick Installation

### Option 1: Install in Development Mode (Recommended)

```bash
# From the project root directory
pip install -e .
```

This installs the package in "editable" mode, so changes to the code are immediately available without reinstalling.

### Option 2: Install in Production Mode

```bash
# From the project root directory
pip install .
```

## Benefits of Package Installation

After installing the package, you can:

1. **Remove manual sys.path manipulation** from all scripts
2. **Use clean imports** like `from common.config import GraphConfig`
3. **Run scripts from any directory** without path issues
4. **Use proper Python packaging** with dependencies management

## Updated Import Examples

### Before (with sys.path manipulation):
```python
import sys
import os
func_app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'func-app'))
if func_app_path not in sys.path:
    sys.path.insert(0, func_app_path)

from common.config import GraphConfig
```

### After (with package installation):
```python
from common.config import GraphConfig
```

## Files That Need Updates

After installing the package, you can remove the sys.path manipulation from:

- `notebooks/populate_graph.py` (lines 15-18)
- `notebooks/cleanup_graph.py` (lines 15-18)
- `notebooks/run_graph_recreation.sh` (Python inline snippet)

## Development Workflow

1. **Install in development mode**: `pip install -e .`
2. **Make code changes** in `func-app/common/` or `notebooks/`
3. **Changes are immediately available** (no reinstall needed)
4. **Run scripts normally**: `python notebooks/populate_graph.py`

## Package Structure

```
confluence_QandA/
├── setup.py              # Package configuration
├── pyproject.toml        # Modern Python packaging
├── func-app/
│   └── common/           # Main package
│       ├── __init__.py   # Package initialization
│       ├── config.py     # Configuration management
│       ├── graph_models.py
│       ├── graph_operations.py
│       └── graph_metrics.py
└── notebooks/            # Scripts using the package
```

## Troubleshooting

### ImportError: No module named 'common'
- Make sure you've installed the package: `pip install -e .`
- Check that you're in the correct Python environment
- Verify the package is installed: `pip list | grep confluence-qa-common`

### ModuleNotFoundError after installation
- Try reinstalling: `pip uninstall confluence-qa-common && pip install -e .`
- Check that the `func-app/common/__init__.py` file exists
- Verify the package structure with `python -c "import common; print(common.__file__)"` 