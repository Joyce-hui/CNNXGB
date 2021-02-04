#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

import os
import tempfile

from zhkui import config
from zhkui import util
from zhkui.util import Result

def query_vt(app, vtkeys):
    """ Query from VirusTotal

    - app zhkui.util.App:
    - vtkeys list of str: The authorized keys to look up results from virus total
    - return Result(status: bool, response: dict)
    """
    from zhkui.smesys.core.vt import VT
    return VT(app, vtkeys).lookup()

def get_hashed_kfcm(app, apktool):
    ''' Get hashed KFCM
    - app zhkui.util.App:
    - apktool str: The path to apktool.jar
    - return Result(status: bool, value: dict{'hashed': dict, 'plain': dict, 'fields': list })
    '''

    from .core.graph import Graph
    from .core.kfcm import KFCM
    from .core.rev import RE

    apktool = util.getabs([apktool])
    if not os.path.exists(apktool):
        err = f'Cannot find apktool at {apktool}'
        return Result(status=False, value=err)

    tmpdir = tempfile.TemporaryDirectory()
    r = RE(app, apktool, tmpdir.name).disasm()
    if not r.status: return r

    smalidir = r.value
    r = Graph(smalidir, "batch").graph()
    if not r.status: return r

    graph = r.value.graph
    r = KFCM(graph).kfcm()
    if not r.status: return r

    mat = r.value.hashmat
    fields = set()
    for m in mat:
        fields.add(m)
        for n in mat[m]:
            fields.add(n)
    val = {
        'hashed': r.value.hashmat,
        'plain': r.value.plainmat,
        'fields': list(fields)
    }

    return Result(status=True, value=val)

def calcsim(alpha, beta):
    """ Similarity comparison between two applications

    - alpha dict: The hashed matrix of the first application
    - beta dict: The hashed matrix of the second application

    - return Result(status, level: float):
    """

    from zhkui.smesys.core.sim import SIM
    r = SIM(alpha, beta).sim()
    if not r: return r
    return Result(status=True, value=r.value.level)
