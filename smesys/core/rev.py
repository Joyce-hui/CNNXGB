#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

import os
import shlex
import shutil
import subprocess

from zhkui import util
from zhkui.util import Result
from zhkui import config

class RE(object):
    def __init__(self, app, apktool, outroot):
        """ Using apktool to decompile an android application

        - app zhkui.smesys.core.application.Application:
        - apktool str: The full path to apktool jar
        - outroot str: The The root of the output directory

        The decompiled stuffs will be packed into a folder named as the sha256 hash
        value of the application.
        """

        self.logger = util.Log()
        apktool_path = util.getabs([apktool])
        if not os.path.exists(apktool_path):
            raise Exception(f'Cannot find apktool: {apktool_path}')

        # max memory is limited to 2GB
        self.apktool = f'java -Xmx2G -Dfile.encoding=utf-8 -jar {apktool_path} '
        self.app = app
        self.outroot = outroot

    def disasm(self):
        """
        - return Result(status, outdir):
            `status` indicates if the decompile is done right. `outdir` is the
            path to the decompiled folder.
        """

        outapp = util.getabs([self.outroot, self.app.sha256])
        if not os.path.exists(outapp):
            os.makedirs(outapp, exist_ok=True)
        else:
            return Result(status=True, value=outapp)

        self.logger.d(f'Processing {self.app.path} ...')

        '''
        The apktool command:

            apktool d <path/to/apk> -o <outputdir>

        Using `-f` to force remove the `outputdir` if it exists.
        '''
        cmd = f'{self.apktool} -f d {shlex.quote(self.app.path)} -o {shlex.quote(outapp)}'
        self.logger.d(f'Decompile cmd: {cmd}')
        r = util.runcmd(cmd)
        self.logger.d(f'Decompile {self.app.path} is done!')
        if not r.status: return r
        return Result(status=True, value=outapp)
