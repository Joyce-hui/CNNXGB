#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

import importlib
import os
import sys

import zhkui

def run(plugname):
    ''' See `zhkui.plugins` for more details '''
    plugins = load_plugins()
    for k, v in plugins.items():
        if k == plugname or v['path'].stem == plugname:
            plugin = v['module'].Plugin()
            plugin.run()
            return
    print(f'Available plugins: {list(plugins.keys())}')

def get_plugins():
    from pathlib import Path
    plugins = []
    plugindirs = [
            Path(zhkui.config.ConfigurationManger().confdir, 'plugins'),
            Path(__file__).parent,
    ]
    for plugindir in plugindirs:
        for path in Path(plugindir).rglob('plugin_*.py'):
            plugins.append(path)
    return plugins

def load_plugins():
    plugins = {}
    for path in get_plugins():
        module_spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        if 'name' in module.CONFIG:
            if path.stem not in sys.modules:
                sys.modules[path.stem] = module
            plugins[module.CONFIG['name']] = {
                'module': module,
                'path': path,
                'desc': module.CONFIG.get('desc', ''),
                'version': module.CONFIG.get('version', ''),
                'author': module.CONFIG.get('author', '')
            }
    return plugins
