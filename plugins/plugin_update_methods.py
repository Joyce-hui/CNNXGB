#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

import os
import math
import multiprocessing as mp

import zhkui
from zhkui import util

CONFIG = {
    'name': 'update-metas',
    'desc': 'Redesign method structure',
}

class Plugin(object):
    def __init__(self):
        self.confmgr = zhkui.config.ConfigurationManger()
        self.logger = util.Log()
        self.tmpdir = self.confmgr.config['tmpdir']

    def run(self):
        models = zhkui.datasys.DatasetManager().get_models()
        table_app = models.TblApp
        apps = table_app.select(table_app.hash).order_by(table_app.hash)

        appcnt = len(apps)
        step = mp.cpu_count() * 2
        for i in range(math.ceil(appcnt / step)):
            beg, end = i * step, min((i + 1) * step, appcnt)
            sha256s = [j.hash for j in apps[beg:end]]

            self.logger.i(f'Process [{beg}, {end}) ...')
            pool = mp.Pool()
            results = pool.map(self.update_methods, sha256s)
            pool.close()

            self.logger.i(f'Save [{beg}, {end}) ...')
            methods = []
            for r in results:
                if r.status >= 0:
                    if r.status == 0:
                        methods.append(r.value)
                else:
                    self.logger.e(r.value)

            if len(methods) > 0:
                table_methods_android = models.TblMethodsAndroid
                table_methods_android.insert_many(methods).execute()
        self.logger.i('All methods are updated!')

    def update_methods(self, sha256):
        util = zhkui.util
        datamgr = zhkui.datasys.DatasetManager()

        models = datamgr.get_models()
        table_methods_android = models.TblMethodsAndroid
        exist = table_methods_android.select().where(table_methods_android.sha256==sha256).exists()
        if exist: return util.Result(status=2, value=f'{sha256} exists')

        dstpath = util.getabs([self.tmpdir, sha256 + '.apk'])
        r = datamgr.fetch_app(sha256, dstpath)
        if r.status:
            try:
                droid = zhkui.parser.android.Android(dstpath)
                methods = droid.get_tbl_methods_android()
                util.remove_if_exist(dstpath)
                return util.Result(status=0, value=methods)
            except Exception as e:
                return util.Result(status=-1, value=f'Failed to parse {dstpath}: {e}!')
        else:
            return util.Result(status=-1, value=f'Cannot fetch {sha256}: {r.value}')
