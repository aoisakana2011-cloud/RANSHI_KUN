import os
import json
import tempfile
import shutil
import pytest
from pathlib import Path

@pytest.fixture(scope="session")
def tmp_project_dir():
    d = tempfile.mkdtemp(prefix="proj_test_")
    yield Path(d)
    try:
        shutil.rmtree(d)
    except Exception:
        pass

@pytest.fixture(autouse=True)
def set_cwd(tmp_project_dir, monkeypatch):
    monkeypatch.chdir(tmp_project_dir)
    (tmp_project_dir / "individual_data").mkdir(exist_ok=True)
    (tmp_project_dir / "models").mkdir(exist_ok=True)
    # create minimal meds_list.json if not present
    meds_file = tmp_project_dir / "individual_data" / "meds_list.json"
    if not meds_file.exists():
        meds_file.write_text(json.dumps({}, ensure_ascii=False))
    yield