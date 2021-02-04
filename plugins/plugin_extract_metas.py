#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

import os
import math
from multiprocessing import Pool

import zhkui
from zhkui import util

CONFIG = {
    'name': 'metas',
    'desc': 'Extract features into tbl_info_android and tbl_methods_android using multiprocessing',
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
        step = 100
        for i in range(math.ceil(appcnt / step)):
            beg, end = i * step, min((i + 1) * step, appcnt)
            sha256s = [j.hash for j in apps[beg:end]]

            self.logger.i(f'Process [{beg}, {end}) ...')
            pool = Pool()
            results = pool.map(self.extract_metas, sha256s)
            pool.close()

            self.logger.i(f'Save [{beg}, {end}) ...')
            infos, methods = [], []
            for r in results:
                if r.status >= 0:
                    if r.status == 0:
                        infos.append(r.value['info'])
                        methods.append(r.value['methods'])
                else:
                    self.logger.e(r.value)

            if len(infos) > 0 and len(methods) > 0:
                table_info_android = models.TblInfoAndroid
                table_info_android.insert_many(infos).execute()
                table_methods_android = models.TblMethodsAndroid
                table_methods_android.insert_many(methods).execute()
        self.logger.i('All metas are extracted!')

    def extract_metas(self, sha256):

        util = zhkui.util
        datamgr = zhkui.datasys.DatasetManager()
        models = datamgr.get_models()

        table_info_android = models.TblInfoAndroid
        table_methods_android = models.TblMethodsAndroid

        exist = table_info_android.select().where(table_info_android.sha256==sha256).exists()
        if exist: return util.Result(status=2, value=f'{sha256} exists')

        exist = table_methods_android.select().where(table_methods_android.sha256==sha256).exists()
        if exist: return util.Result(status=2, value=f'{sha256} exists')

        dstpath = util.getabs([self.tmpdir, sha256 + '.apk'])
        r = datamgr.fetch_app(sha256, dstpath)
        if r.status:
            try:
                droid = zhkui.parser.android.Android(dstpath)
                info = droid.get_tbl_info_android()
                methods = droid.get_tbl_methods_android()
                util.remove_if_exist(dstpath)
                return util.Result(status=0, value={'info': info, 'methods': methods})
            except Exception as e:
                return util.Result(status=-1, value=f'Failed to parse {dstpath}: {e}!')
        else:
            return util.Result(status=-1, value=f'Cannot fetch {sha256}: {r.value}')
