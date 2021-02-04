#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

import json
import gzip
import os
import zipfile

from androguard.misc import AnalyzeAPK
import magic
from pathlib import Path

from zhkui import util
from zhkui import config

class Android(object):

    def __init__(self, apkpath):

        apkpath = util.getabs([apkpath])
        if not os.path.exists(apkpath):
            raise Exception(f'Cannont find android application: {apkpath}')
        self.apkpath = apkpath

        apk, dvms, anly  = AnalyzeAPK(apkpath)
        self.apk = apk
        self.dvms = dvms
        self.anly = anly
        self.config = config.ConfigurationManger().config
        self.logger = util.Log()

    def get_app_name(self):
        appname = self.apk.get_app_name()
        if not appname: appname = ''
        return appname

    def get_package_name(self):
        pkgname = self.apk.get_package()
        if not pkgname: pkgname = ''
        return pkgname

    def get_version(self):
        return self.apk.androidversion.get('Name', '')

    def get_file(self, path):
        return self.apk.get_file(path)

    def get_icon_bytes(self):
        iconpath = self.apk.get_app_icon()
        if iconpath and iconpath.endswith('.png'):
            return self.get_file(iconpath)
        return None

    def is_valid_apk(self):
        ''' Check if the application is valid

        An apk is valid only when it contains AndroidManifest.xml, resources.arsc,
        classes.dex and the AndroidManifest.xml could be parsed successfully.

        - return `zhkui.util.Result`:

            Result.status indicates if the apk is valid, Result.value contains error
            message if the application is not valid.
        '''

        errmsg = ':'
        mime = magic.from_file(self.apkpath, mime=True)
        isapk = False
        if mime == 'application/zip' or mime == 'application/java-archive':
            try:
                with zipfile.ZipFile(self.apkpath) as zip:
                    isapk = True
                    for meta in ['AndroidManifest.xml', 'resources.arsc', 'classes.dex']:
                        isapk = isapk and (meta in zip.namelist())
                        if not isapk: errmsg += f'Not contain {meta}:'
            except Exception as e:
                errmsg += f'{e}:'
                isapk = False
        is_manifest_valid = self.apk.is_valid_APK()
        if not is_manifest_valid:
            errmsg = 'Cannot parse AndroidManifest.xml:'
        return util.Result(status=isapk and is_manifest_valid, value=errmsg)

    def get_app_components(self):
        ''' Get acitivities, services, broadcast receivers and content providers '''

        return {
            'act': self.get_activities(),
            'srv': self.get_services(),
            'recv': self.get_receivers(),
            'prvd': self.get_providers(),
        }

    def get_activities(self):
        return self.apk.get_activities()

    def get_services(self):
        return self.apk.get_services()

    def get_receivers(self):
        return self.apk.get_receivers()

    def get_providers(self):
        return self.apk.get_providers()

    def get_files(self):
        return self.apk.get_files()

    def get_native_names(self):
        ''' Get native so library names

        - return list: The names of the native so libraries.
        '''
        sonames = set()
        app_files = self.get_files()
        for app_file in app_files:
            if app_file.endswith('.so'):
                sonames.add(os.path.basename(app_file))
        return list(sonames)

    def get_permissions(self):
        return self.apk.get_permissions()

    def get_permissions_details(self, name):
        ''' Get permission details by permission name
        - name str: The name of the permission, such as android.permission.ACCESS_NETWORK_STATE
        - return Result(status: bool, details: dict)

        The structure of details

            {
                'meaning': The meaning of the permission,
                'level': normal, dangerous, signature or unknown,
            }
        '''

        # The permission table is from https://developer.android.com/reference/android/Manifest.permission
        permissions_table = None
        with open(Path(Path(__file__).parent, 'permissions.json'), 'r') as _:
            permissions_table = json.load(_)
        if name in permissions_table:
            return util.Result(True, permissions_table[name])
        else:
            return util.Result(False, 'Unknwon permission!')

    def get_extpkgs(self):
        ''' Get external packages

        See `zhkui.util.libdetector.LibDetector.detect_by_libscout` for returned values.
        '''

        detector = util.libdetector.LibDetector(self.apkpath)
        r = detector.detect_by_libscout(
            scoutjar=self.config['libscout']['jar'],
            droidjar=self.config['libscout']['android-jar'],
            profdir=self.config['libscout']['profiles'],
        )
        return r

    def get_methods(self):
        ''' Get all methods in the application

        - return dict:

            The dict structure is showed as below

                [
                    '<mid>': {
                        # if the method is external method, then there are no
                        # meta and basic block
                        'ext': <bool>,
                        # meta
                        'm': {
                            # offset
                            'off': <int>,
                            # method size in 16-bit unit
                            'sz': <int>,
                        }
                        # basic block
                        'bb': [
                            # bb 1
                            {
                                # basic block meta: start and end of the basic
                                # block, end minus start equals the lenth of this
                                # basic block
                                'm': { 's': <int>, 'e': <int> },
                                'i' : [
                                    # instruction 1
                                    {
                                        # hex
                                        'h': list of hex str,
                                        # mnemonic
                                        'm': <str>,
                                        # output
                                        'o': <str>
                                    },
                                    # instruction 2
                                    {
                                        # hex
                                        'h': list of hex str,
                                        # mnemonic
                                        'm': <str>,
                                        # output
                                        'o': <str>
                                    },
                                ]
                            },
                        ]
                    }
                ]

            Every element represents a method, the method name <mid> are
            the joind by class name, method name, method descriptor with `:` as
            separator.

        '''
        methods = []
        method_analysis_iter = self.anly.get_methods()
        for method_analysis in method_analysis_iter:
            mid = f'{method_analysis.class_name}:{method_analysis.name}:{method_analysis.descriptor}'
            if not method_analysis.is_external():
                method = {'ext': False}
                # method mea information
                encoded_method = method_analysis.get_method()
                method['m'] = {'off': encoded_method.get_address(), 'sz': encoded_method.get_length()}

                # method basic blocks
                method['bb'] = []
                for dvmbb in method_analysis.get_basic_blocks().gets():
                    bb = {
                        'm': {'s': dvmbb.get_start(), 'e': dvmbb.get_end()},
                        'i': [],
                    }
                    for instruct in dvmbb.get_instructions():
                        bb['i'].append({
                            # hex code
                            'h': instruct.get_hex().split(),
                            # mnemonic
                            'm': instruct.get_name(),
                            # output
                            'o': instruct.get_output(),
                        })
                    method['bb'].append(bb)
                methods.append({mid: method})
            else:
                method = {'ext': True}
                methods.append({mid: method})
        return methods

    def get_md5(self):
        r = util.filehash(self.apkpath, 'md5')
        if not r.status:
            raise Exception(f'Cannot get md5: {r.value}')
        return r.value

    def get_sha1(self):
        r = util.filehash(self.apkpath, 'sha1')
        if not r.status:
            raise Exception(f'Cannot get sha1: {r.value}')
        return r.value

    def get_sha256(self):
        r = util.filehash(self.apkpath, 'sha256')
        if not r.status:
            raise Exception(f'Cannot get sha256: {r.value}')
        return r.value

    def get_size(self):
        ''' Return file size in bytes '''
        return os.path.getsize(self.apkpath)

    def get_tbl_info_android(self):
        return {
            'activities': self.get_activities(),
            'services': self.get_services(),
            'receivers': self.get_receivers(),
            'providers': self.get_providers(),
            'extpkgs': self.get_extpkgs(),
            'perms': self.get_permissions(),
            'sha256': self.get_sha256(),
            'sonames': self.get_native_names(),
        }

    def get_tbl_methods_android(self):
        return {
            'sha256': self.get_sha256(),
            'methods': util.json_to_gzip_bytes(self.get_methods())
        }

    def get_tbl_hash(self):
        return {
            'md5': self.get_md5(),
            'sha1': self.get_sha1(),
            'sha256': self.get_sha256(),
        }
