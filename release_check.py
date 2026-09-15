"""Noninteractive packaged-runtime checks for the activation-free distribution."""
from pathlib import Path
import json
import sys


def run(output_dir):
    from app_version import APP_VERSION
    import numpy as np
    from PIL import Image, ImageDraw
    from skimage.morphology import skeletonize
    from PyQt5.QtWidgets import QApplication
    from root_gui import MainWindow, AnalysisResultViewer, AboutDialog
    from root_analysis import analyze_root_image, _analysis_worker_task
    from concurrent.futures import ProcessPoolExecutor
    import multiprocessing

    out=Path(output_dir).resolve()
    out.mkdir(parents=True,exist_ok=True)
    image=Image.new('L',(260,260))
    pen=ImageDraw.Draw(image)
    for points in [[(100,20),(100,240)],[(100,60),(200,200)],[(100,130),(220,190)]]:
        pen.line(points,fill=255,width=3)
    binary=out/'binary.png'; skeleton=out/'skeleton.png'
    image.save(binary)
    Image.fromarray(skeletonize(np.asarray(image)>0).astype('uint8')*255).save(skeleton)
    result=analyze_root_image(binary,skeleton,sample_id='release-check')
    assert (result['Num_Tips'],result['Num_Forks'],result['Num_Crossings'])==(3,2,1)
    assert result['Scale_Source']=='unknown' and np.isnan(result['Root_Length_cm'])
    with ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context('spawn')) as pool:
        futures=[pool.submit(_analysis_worker_task,(str(binary),str(skeleton),None,'spawn-check','top')) for _ in range(2)]
        parallel=[f.result(timeout=180) for f in futures]
    assert all(r['Num_Crossings']==1 and r['Num_Tips']==3 for r in parallel)
    from preprocess import process_single_image
    porous = np.zeros((360, 220), dtype='uint8')
    porous[20:330, 90:130] = 255
    for r0, r1, c0, c1 in [(29, 35, 98, 104), (41, 48, 116, 121), (58, 66, 104, 111)]:
        porous[r0:r1, c0:c1] = 0
    stem_source = out / 'porous-stem.png'
    Image.fromarray(porous).save(stem_source)
    stem_binary, stem_skeleton = process_single_image(
        str(stem_source), str(out / 'stem'), method='intensity',
        foreground='light', repair_proximal_stem=True)
    stem = analyze_root_image(stem_binary, stem_skeleton)
    assert stem['Stem_Repair_Status'] == 'applied' and stem['Stem_Repair_Holes'] == 3
    assert stem['Num_Forks'] == 0 and stem['Num_Tips'] == 1
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    assert window.an_dpi.value()==0 and window.an_root_direction.currentData()=='top'
    assert not window.pp_stem_repair.isChecked()
    assert window.pp_stem_direction.currentData() == 'top'
    viewer=AnalysisResultViewer()
    viewer.show_result(str(binary),str(skeleton),result)
    app.processEvents()
    assert len(viewer.fig.axes)==3
    renderer=viewer.canvas.get_renderer()
    legend=viewer.fig.axes[1].get_legend()
    assert legend is not None
    legend_box=legend.get_window_extent(renderer)
    assert all(not legend_box.overlaps(t.get_window_extent(renderer))
               for t in viewer.fig.axes[2].texts)
    assert not any('Display error' in t.get_text() for a in viewer.fig.axes for t in a.texts)
    viewer.fig.savefig(out/'runtime-preview.png',dpi=110,bbox_inches='tight')
    about=AboutDialog(window)
    about.show();app.processEvents()
    assert about.grab().save(str(out/'about-preview.png'))
    about.close()
    resource=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
    assert (resource/'assets'/'icon.ico').is_file()
    assert (resource/'assets'/'xjn.png').is_file()
    report={'version':APP_VERSION,'frozen':bool(getattr(sys,'frozen',False)),
            'topology':'pass','unknown_scale':'pass','spawn_workers':'pass',
            'gui_render':'pass','assets':'pass','activation_required':False,
            'proximal_stem_repair':'pass', 'stem_repair_default':'off'}
    (out/'self-test.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    window.close();viewer.close()
    return 0
