"""Course template and AIM-PRO export directory of the API tests (S09a)."""

import json
from pathlib import Path


def write_course_template(directory, creators=('admin',), source_scopes=None):
    """A course template as an operator installs it: who may create courses, which source scopes a course gets."""
    path = Path(directory) / 'course-template.json'
    path.write_text(json.dumps({'format': 1, 'creators': list(creators),
                                'source_scopes': {'wp3': ['wp3']} if source_scopes is None else source_scopes}),
                    encoding='utf-8')
    return path


def new_export_directory(directory):
    """An empty directory for uploaded AIM-PRO exports, as the API and the worker share it."""
    exports = Path(directory) / 'uploads'
    exports.mkdir(exist_ok=True)
    return exports


def module_settings(directory):
    """The settings of the ``courses`` and ``exports`` modules, which every all-modules deployment needs."""
    return {'aimpro_exports': new_export_directory(directory), 'course_template': write_course_template(directory)}
