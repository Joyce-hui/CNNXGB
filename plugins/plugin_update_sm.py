#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

import os
import tempfile
from tqdm import tqdm

import zhkui
from zhkui.datasys.orm.models import *

CONFIG = {
    'name': 'sm',
    'desc': 'Update similar module',
}

class Plugin(object):
    def __inti__(self):
        pass

    def run(self):
        logger = zhkui.util.Log()
        datamgr = zhkui.datasys.DatasetManager()
        models = datamgr.get_models()
        tmpdir = tempfile.TemporaryDirectory()

        for rec in tqdm(TblApp.select().where(TblApp.isblack==True)):

            # Skip if the record is existed in TblSm
            if len(TblSm.select().where(TblSm.sha256==rec.hash)) > 0: continue

            r = datamgr.fetch_app(rec.hash, os.path.join(tmpdir.name, rec.hash))
            if not r.status:
                logger.e(r.value)
                continue
            app = zhkui.util.App(r.value)
            r = zhkui.smesys.get_hashed_kfcm(app, datamgr.config['apktool'])
            if not r.status:
                logger.e(r.value)
                continue
            kfcm = r.value
            data = zhkui.util.json_to_gzip_bytes(kfcm['hashed'])
            TblSm.insert({TblSm.sha256: rec.hash, TblSm.sm: data}).on_conflict('ignore').execute()
            for f in kfcm['fields']:
                query = TblSmFunc.insert({TblSmFunc.usrfn: f, TblSmFunc.sha256: rec.hash}).on_conflict('ignore')
                query.execute()
