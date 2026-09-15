"""Release GUI settings must reach both execution paths without changing defaults."""
import os
from pathlib import Path
from uuid import uuid4
from concurrent.futures import Future

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np
import pytest
from PIL import Image
from PyQt5.QtWidgets import QApplication

import root_gui


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def workspace_temp():
    # Pytest's mode-0700 temp directories are inaccessible in the Windows sandbox.
    directory = Path(__file__).resolve().parents[1] / 'build' / ('gui-test-' + uuid4().hex)
    directory.mkdir(parents=True)
    return directory


def test_gui_model_controls_default_to_general_and_context(app):
    window = root_gui.MainWindow()
    assert window.an_root_model.currentData() == 'general'
    assert window.an_crossing_context.isChecked()
    window.an_root_model.setCurrentIndex(1)
    assert window.an_root_model.currentData() == 'shared_crown'
    assert any(window.pp_method.itemText(i).startswith('intensity')
               for i in range(window.pp_method.count()))
    window.close()


@pytest.mark.parametrize('count', [1, 2])
def test_model_and_context_reach_single_and_batch_worker(app, monkeypatch, workspace_temp, count):
    tmp_path = workspace_temp
    captured = []

    def analyze(**kwargs):
        captured.append(kwargs)
        return {'Sample_ID': kwargs['sample_id'], 'Num_Tips': 1}

    def execute(args):
        assert len(args) == 9
        return analyze(sample_id=args[3], root_direction=args[4],
                       root_model=args[7], crossing_context=args[8])

    class Pool:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def submit(self, function, args):
            future = Future()
            future.set_result(function(args))
            return future

    monkeypatch.setattr(root_gui.root_analysis, 'analyze_root_image', analyze)
    monkeypatch.setattr(root_gui.root_analysis, '_analysis_worker_task', execute)
    monkeypatch.setattr(root_gui, 'ProcessPoolExecutor', Pool)
    pairs = [dict(binary_path='binary.png', skeleton_path='skeleton.png',
                  sample_id=f'sample_{i}', year='') for i in range(count)]
    worker = root_gui.AnalysisWorker([], [], str(tmp_path), pairs_override=pairs,
                                    root_direction='left', root_model='shared_crown',
                                    crossing_context=False)
    errors = []
    worker.error.connect(errors.append)
    worker.run()
    assert not errors
    assert len(captured) == count
    assert all(r['root_model'] == 'shared_crown' and r['crossing_context'] is False
               and r['root_direction'] == 'left' for r in captured)
    assert (tmp_path / 'root_architecture_metrics.csv').exists()


def test_intensity_preview_matches_saved_segmentation(app, workspace_temp):
    tmp_path = workspace_temp
    array = np.zeros((100, 100), dtype=np.uint8)
    array[10:90, 48:53] = 220
    array[50:52, 52:75] = 170
    source = tmp_path / 'sample.png'
    Image.fromarray(array).save(source)
    binary, skeleton = root_gui.preprocess.process_single_image(
        str(source), str(tmp_path / 'saved'), method='intensity')
    worker = root_gui.SinglePreprocessWorker(str(source), str(tmp_path), method='intensity')
    outputs, errors = [], []
    worker.finished.connect(lambda raw, mask, skel, path: outputs.append((mask, skel)))
    worker.error.connect(errors.append)
    worker.run()
    assert not errors and len(outputs) == 1
    assert np.array_equal(outputs[0][0], np.asarray(Image.open(binary)))
    assert np.array_equal(outputs[0][1], np.asarray(Image.open(skeleton)))
