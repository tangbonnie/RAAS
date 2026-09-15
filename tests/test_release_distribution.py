"""Release integration: CLI/worker options and activation-free entry point."""
import ast
from pathlib import Path
from unittest.mock import patch
import root_analysis

ROOT = Path(__file__).resolve().parents[1]


def test_worker_forwards_model_and_crossing_context():
    with patch.object(root_analysis, 'analyze_root_image', return_value={}) as call:
        root_analysis._analysis_worker_task(('b', 's', None, 'sample', 'top',
                                            None, None, 'shared_crown', False))
    assert call.call_args.kwargs['root_model'] == 'shared_crown'
    assert call.call_args.kwargs['crossing_context'] is False


def test_source_launch_has_no_activation_code():
    assert not (ROOT / 'license_manager.py').exists()
    assert not (ROOT / 'keys').exists()
    tree = ast.parse((ROOT / 'launcher.py').read_text(encoding='utf-8'))
    imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    functions = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert 'license_manager' not in imports
    assert '_check_license' not in functions
    assert '_show_activate_dialog' not in functions
