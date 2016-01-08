# -*- coding: utf-8 -*-

import importlib
import inspect
import sys

import pytest


def pytest_addoption(parser):
    group = parser.getgroup('wish')
    group.addoption('--wish-modules', default=(), nargs='+',
                    help="Comma separated list of module names.")
    group.addoption('--wish-fail', action='store_true', help="Show wish failures.")


def generate_module_objects(module):
    for obj_name, obj in inspect.getmembers(module):
        if obj_name.startswith('__'):
            continue
        obj_module = inspect.getmodule(obj)
        if obj_module is not module:
            continue
        yield obj_name, obj


def index_modules(modules, prefixes):
    object_index = {}
    for module_name, module in modules.items():
        if module_name.startswith(prefixes):
            for obj_name, obj in generate_module_objects(module):
                object_index['{}:{}'.format(module_name, obj_name)] = obj
    return object_index


def pytest_generate_tests(metafunc):
    if 'wish' not in metafunc.fixturenames:
        return
    wish_modules = metafunc.config.getoption('wish_modules')
    for module_name in wish_modules:
        importlib.import_module(module_name)
    # NOTE: 'copy' is needed here because index_modules may unexpectedly trigger a module load
    object_index = index_modules(sys.modules.copy(), tuple(wish_modules))
    object_items = sorted(object_index.items())
    ids, params = list(zip(*object_items)) or [[], []]
    metafunc.parametrize('wish', params, ids=ids, scope='module')
    wish_fail = metafunc.config.getoption('wish_fail')
    if not wish_fail:
        metafunc.function = pytest.mark.xfail(metafunc.function)
