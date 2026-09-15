# -*- coding: utf-8 -*-
import importlib.util
import os


def _load_lib():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'rename_models_lib.py')
    spec = importlib.util.spec_from_file_location('cs_tax_cert_rename_lib', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def migrate(cr, version):
    _load_lib().run_pre(cr)
