# -*- coding: utf-8 -*-

import argparse
import importlib
import inspect
import re
import sys

import pytest

from pytest_wish import utils


OBJECT_BLACKLIST = (
    # pytest internals
    '_pytest.runner:exit',
    '_pytest.runner:skip',
    '_pytest.skipping:xfail',

    # unconditional exit
    'posix:_exit',
    '_signal:default_int_handler',
    'atexit.register',

    # low level crashes
    'numpy.fft.fftpack_lite:cffti',
    'numpy.fft.fftpack_lite:rffti',
    'appnope._nope:beginActivityWithOptions',
    'ctypes:string_at',
    'ctypes:wstring_at',
    'gc:_dump_rpy_heap',
    'gc:dump_rpy_heap',
    'matplotlib._image:Image',

    # hangs
    'Tkinter:mainloop',
    'astkit.compat.py3:execfile',
    'astroid.builder:open_source_file',
    'click.termui:getchar',
    'click.termui:edit',
    'click.termui:hidden_prompt_func',
    'eventlet.hubs:trampoline',
    'getpass:getpass',
    'getpass:unix_getpass',
    'matplotlib.font_manager:FontManager',
    'pty:_copy',
    'pydoc:serve',
    'pyexpat:ErrorString',
    'skimage:_test',
    'skimage:test',
)


def pytest_addoption(parser):
    group = parser.getgroup('wish')
    group.addoption('--wish-modules', default=(), nargs='+',
                    help="Space separated list of module names.")
    group.addoption('--wish-includes', nargs='+',
                    help="Space separated list of regexs matching full object names to include.")
    # enable support for '--wish-includes all'
    utils.ENABLE_IMPORT_ALL = True
    group.addoption('--wish-excludes', default=(), nargs='+',
                    help="Space separated list of regexs matching full object names to exclude.")
    group.addoption('--wish-objects', type=argparse.FileType('r'),
                    help="File of full object names to include.")
    group.addoption('--wish-fail', action='store_true', help="Show wish failures.")


def generate_module_objects(module):
    try:
        module_members = inspect.getmembers(module)
    except:  # pragma: no cover
        raise StopIteration
    for object_name, object_ in module_members:
        if inspect.getmodule(object_) is module:
            yield object_name, object_


def valid_name(name, include_res, exclude_res):
    include_name = any(include_re.match(name) for include_re in include_res)
    exclude_name = any(exclude_re.match(name) for exclude_re in exclude_res)
    return include_name and not exclude_name


def index_modules(modules, include_patterns, exclude_patterns, object_blacklist=OBJECT_BLACKLIST):
    exclude_patterns += tuple(name.strip() + '$' for name in object_blacklist)
    include_res = [re.compile(pattern) for pattern in include_patterns]
    exclude_res = [re.compile(pattern) for pattern in exclude_patterns]
    object_index = {}
    for module_name, module in modules.items():
        for object_name, object_ in generate_module_objects(module):
            full_object_name = '{}:{}'.format(module_name, object_name)
            if valid_name(full_object_name, include_res, exclude_res):
                object_index[full_object_name] = object_
    return object_index


def index_objects(stream):
    module_index = {}
    object_index = {}
    for line in stream:
        full_object_name = line.partition('#')[0].strip()
        if full_object_name:
            module_name, _, object_name = full_object_name.partition(':')
            try:
                module = module_index.setdefault(module_name, importlib.import_module(module_name))
                object_index[full_object_name] = getattr(module, object_name)
            except ImportError:
                pass
            except AttributeError:
                pass
    return object_index


def pytest_generate_tests(metafunc):
    if 'wish' not in metafunc.fixturenames:
        return

    wish_modules = metafunc.config.getoption('wish_modules')
    for module_name in wish_modules:
        importlib.import_module(module_name)

    wish_includes = metafunc.config.getoption('wish_includes') or wish_modules
    wish_excludes = metafunc.config.getoption('wish_excludes')

    # NOTE: 'copy' is needed here because index_modules may unexpectedly trigger a module load
    object_index = index_modules(sys.modules.copy(), wish_includes, wish_excludes)

    wish_objects = metafunc.config.getoption('wish_objects')
    if wish_objects is not None:
        object_index.update(index_objects(wish_objects))

    ids, params = list(zip(*sorted(object_index.items()))) or [(), ()]
    metafunc.parametrize('wish', params, ids=ids, scope='module')

    wish_fail = metafunc.config.getoption('wish_fail')
    if not wish_fail:
        metafunc.function = pytest.mark.xfail(metafunc.function)