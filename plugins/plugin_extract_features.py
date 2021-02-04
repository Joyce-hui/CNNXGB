#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

'''
List of dalvik instrucitons to call an API

    invoke-virtual
    invoke-super
    invoke-direct
    invoke-static
    invoke-interface

A method calling looks like

    invoke-direct v4, v5, v6, La/a/a/a$a$1;-><init>(La/a/a/a$a; Landroid/widget/ImageView;)V

Generally, the method name could be found at the last argument

    La/a/a/a$a$1;-><init>(La/a/a/a$a; Landroid/widget/ImageView;)V

and the class and the method name is separated by `->`, but the `->` is not a
must however really a rare case. If we could not find `->` we will ignore the
API calling.

We only consiser packages listed here [Android Pakcages](https://developer.android.com/reference/packages.html) as system packages.
Only calling to system pkackage will be count in the statistics.

    # https://github.com/androguard/androguard/blob/22849b6965835b611f5fd6615de9301f5f47318e/androguard/core/analysis/analysis.py#L606
    Landroid/
    Lcom/android/internal/util
    Ldalvik/
    Ljava/
    Ljavax/
    Lorg/apache/
    Lorg/json/
    Lorg/w3c/dom/
    Lorg/xml/sax
    Lorg/xmlpull/v1/
    Ljunit/

Besides, we will ignore any third-party library detected by libscout tool.

'''

import time
import json
import os
import datetime

import simhash
from PIL import Image, ImageDraw

import zhkui
from zhkui import util

CONFIG = {
    'name': 'features',
    'desc': 'Generate features',
}

class Plugin(object):
    def __init__(self):
        self.confmgr = zhkui.config.ConfigurationManger()
        self.logger = util.Log()

    def run(self):
        feature_dir = os.path.join(self.confmgr.confdir, 'features')
        os.makedirs(feature_dir, exist_ok=True)

        feature_raw_dir = os.path.join(feature_dir, 'raw')
        os.makedirs(feature_raw_dir, exist_ok=True)

        feature_imgs_dir = os.path.join(feature_dir, 'imgs')
        os.makedirs(feature_imgs_dir, exist_ok=True)

        sha256s = self.get_sha256s()

        if len(sha256s) <= 0:
            self.logger('Invalid sha256s!')
            return

        fails = []

        for idx, sha256 in enumerate(sha256s):
            self.logger.i(f'[{idx + 1}/{len(sha256s)}] Process {sha256} ...')

            feature_path = os.path.join(feature_raw_dir, f'{sha256}.json')

            if os.path.exists(feature_path): continue

            r = self.features_one(sha256)
            if r.status is True:
                feature, colorseq = r.value

                imgr = self.get_image(colorseq)
                if imgr.status is True:
                    image = imgr.value
                    image.save(os.path.join(feature_imgs_dir, f'{sha256}.png'))
                    feature['image'] = True
                else:
                    image = None
                    feature['image'] = False
                    err = f'Cannot generate image for {sha256}: {imgr.value}'
                    fails.append({'sha256': sha256, 'err': err})
                    self.logger.e(err)
                with open(feature_path, 'w') as _:
                    json.dump(feature, _,)
            else:
                err = f'Cannot get feature for {sha256}: {r.value}'
                fails.append({'sha256': sha256, 'err': err})
                self.logger.e(err)

        logname = 'features.' + datetime.datetime.today().strftime('%Y-%m-%d.%H:%M:%S') + '.json'
        logfile = os.path.join(self.confmgr.config['logs'], logname)
        with open(logfile, 'w') as _:
            json.dump(fails, _, ensure_ascii=False, indent=2)

        self.logger.i(f'All features are saved into {feature_dir}, and log is in {logfile}!')

    def get_sha256s(self):
        '''
        format: sha256, isblack
        '''

        util = zhkui.util
        sha256path = os.path.join(self.confmgr.confdir, 'sha256s.json')
        if not os.path.exists(sha256path):
            self.logger.e(f'Cannot find: {sha256path}!')
            return []

        with open(sha256path, 'r') as _:
            csvs = json.load(_)

        sha256s = []
        for csv in csvs:
            csv = util.getabs([csv])
            with open(csv, 'r') as _:
                _.readline()
                for line in _:
                    if not line: continue
                    sha256 = line.split(',')[0].strip()
                    if sha256 in sha256s: continue
                    sha256s.append(sha256)
        return sha256s

    def save_features_to_csv(self, features, outdir):
        PERMS = 'ACCESS_WIFI_STATE READ_LOGS CAMERA READ_PHONE_STATE CHANGE_NETWORK_STATE READ_SMS CHANGE_WIFI_STATE RECEIVE_BOOT_COMPLETED DISABLE_KEYGUARD RESTART_PACKAGES GET_TASKS SEND_SMS INSTALL_PACKAGES SET_WALLPAPER READ_CALL_LOG SYSTEM_ALERT_WINDOW READ_CONTACTS WRITE_APN_SETTINGS READ_EXTERNAL_STORAGE WRITE_CONTACTS READ_HISTORY_BOOKMARKS WRITE_SETTINGS'
        PERMS = [f'android.permission.{p}' for p in PERMS.split()]
        PERMS_MAP = { PERMS[i]: i for i in range(len(PERMS)) }

        util = zhkui.util
        outdir = util.getabs([outdir])
        imgdir = os.path.join(outdir, 'imgs')
        os.makedirs(imgdir, exist_ok=True)
        feature_path = os.path.join(outdir, 'features.csv')
        with open(feature_path, 'w') as _:
            header = f'sha256,{",".join(PERMS)},hasimg,label'
            _.write(header + '\n')
            for feature in features:
                sha256 = feature['sha256']
                permbits = [0 for i in range(len(PERMS))]
                for perm in feature['perms']:
                    if perm in PERMS:
                        permbits[PERMS_MAP[perm]] = 1
                hasimg = 1
                if feature['image']:
                    feature['image'].save(os.path.join(imgdir, f'{sha256}.png'))
                else:
                    hasimg = 0
                permbits = ','.join(map(str, permbits))
                line = f'{sha256},{permbits},{hasimg},{feature["label"]}'
                _.write(line + '\n')

    def features_one(self, sha256):
        ''' Generate features for one appliation by its sha256 value

        - return util.Result:

            if success, return (True, (features, colorseq)), or else (False, errmsg).

            The `features` structure

                {
                    'perms': list,
                    'apifreq': {
                        '<api1>': int,
                        '<api2>': int,
                    },
                    'bbcnt': int,
                }

        `colorseq` are list of five-element tuple: (x, y, r, g, b).
        '''

        util = zhkui.util

        SYSPKGS = ("Landroid/", "Lcom/android/internal/util", "Ldalvik/", "Ljava/",
        "Ljavax/", "Lorg/apache/", "Lorg/json/", "Lorg/w3c/dom/",
        "Lorg/xml/sax", "Lorg/xmlpull/v1/", "Ljunit/")

        datamgr = zhkui.datasys.DatasetManager()
        fields = ['isblack', 'perms', 'extpkgs', 'methods']
        values = datamgr.get_app_info(sha256, fields)
        if not values:
            return util.Result(status=False, value=f'Cannot find {sha256} in database!')

        for field in fields:
            if field not in values:
                return util.Result(status=False, value=f'{sha256} may not be processed properly!')

        features = {'perms': values['perms'], 'isblack': values['isblack']}

        apifreq = {}
        extpkgs = tuple(f'L{pkg.replace(".", "/")}/' for pkg in values['extpkgs'].keys())
        methods = util.json_from_gzip_bytes(values['methods'])
        xyrgb = []
        bbcnt = 0
        for item in methods:
            mid = list(item.keys())[0]
            method = item[mid]
            # skip third-party packages
            if mid.startswith(extpkgs):
                continue
            # external method, no codes at all, skipped
            if method['ext']:
                continue

            mnemonic = ''
            for bb in method['bb']:
                for instruct in bb['i']:
                    mnemonic += instruct['m']
                    if instruct['m'].startswith('invoke-'):
                        if '->' in instruct['o']:
                            #  v0, Ljava/lang/Object;-><init>()V
                            mid = instruct['o'].find('->')
                            end = instruct['o'].find('(', mid)
                            api = instruct['o'][:end].split(',')[0].strip()
                            if api.startswith(SYSPKGS):
                                if api not in apifreq:
                                    apifreq[api] = 1
                                else:
                                    apifreq[api] += 1
            bbcnt += len(method['bb'])
            if len(mnemonic) > 0:
                xyrgb.append(self.get_xyrgb(mnemonic))
        features['apifreq'] = apifreq
        features['bbcnt'] = bbcnt
        return util.Result(status=True, value=(features, xyrgb))

    def get_xyrgb(self, s):
        ''' Simhash string s and get its color representation

        - s str: A string
        - return five-element tuple: (x, y, r, g, b)
        '''
        bitsz = 48
        bits = bin(simhash.Simhash(s, f=bitsz).value)[2:]
        if len(bits) != bitsz:
            padsz = bitsz - len(bits)
            bits = '0' * padsz + bits
        bits = bits[:44]
        x, y = int(bits[:10], 2), int(bits[10:20], 2)
        r, g, b = tuple(int(bits[20 + i * 8: 20 + (i + 1) * 8], 2) for i in range(3))
        return (x, y, r, g, b)

    def get_image(self, pxseq):
        ''' Get a 1024*1024 image from pixel sequences

        - pxseq list of five-element tuple: Each element has the style (x, y, r, g, b)
        - return util.Result:

            If success, the Result.value will be the generated PIL.Image instance
        '''

        util = zhkui.util

        w, h = 1024, 1024

        if len(pxseq) > w * h:
            return util.Result(status=False, value='Sequence is too long!')

        stats = {}
        img = Image.new(mode='RGBA', size=(w, h), color=(0, 0, 0, 255))
        for px in pxseq:
            x, y, r, g, b = px

            # Skip default pixel value
            if r == 0 and g == 0 and b == 0: continue

            rr, gg, bb, _ = img.getpixel((x, y))


            # Current location is empty, fill it
            if rr == 0 and gg == 0 and bb == 0:
                img.putpixel((x, y), (r, g, b, 255))
                continue

            # Same location same color
            if rr == r and gg == g and bb == b:
                k = f'{x}:{y}:{r}:{g}:{b}'
                if k not in stats:
                    stats[k] = 1
                else:
                    stats[k] += 1
            # Same location but different color, color conflict! We should find
            # the next empty location
            else:
                has_next_pos = False
                deltas = range(1, max(w, h) - min(x, y) + 1)
                for delta in deltas:
                    neighbours = self.get_neighbours(w, h, x, y, delta)
                    for neighbour in neighbours:
                        newr, newg, newb, _ = img.getpixel(neighbour)
                        if newr == 0 and newg == 0 and newb == 0:
                            x, y = neighbour
                            has_next_pos = True
                            break
                    if has_next_pos:
                        break
                if not has_next_pos:
                    return util.Result(status=False, value='Exhausted searching, but no empty cell!')
                else:
                    img.putpixel((x, y), (r, g, b, 255))

        # Adjust alpha value for the pixel of same color same location
        # the number of conflict and its corresponding alpha value
        #   < 10          => 0
        #   [10, 20)      => 1
        #   [20, 30)      => 2
        #   [30, 40)      => 3
        #   ...
        #   [2530, 2540)  => 253
        #   >= 2540       => 254

        freqseg = [i * 10 for i in range(1, 254)]
        for stat in stats:
            x, y, r, g, b = [int(i) for i in stat.split(':')]
            freq = stats[stat]
            if freq < 10:
                alpha = 0
            elif freq >= 2540:
                alpha = 254
            else:
                if freq in freqseg:
                    alpha = freq // 10
                else:
                    alpha = (freq - freq % 10) // 10
            img.putpixel((x, y), (r, g, b, alpha))


        return util.Result(status=True, value=img)

    def get_neighbours(self, w, h, x, y, r):
        ''' Get neighbours around (x, y) with distance r in flat (0, 0, w-1, h-1)

        The walk illustration

                            1
                (x-1, y-1) --> (x+1, y-1)

                    | 3  (x, y)    | 4
                    v              v
                            2
                (x-1, y+1) --> (x+1, y+1)

        '''
        pos = []

        for i in range(x - r, x + r + 1):
            safex = 0 <= i and i < w
            if safex and y - r >= 0: pos.append((i, y - r))
            if safex and y + r < h: pos.append((i, y + r))

        for j in range(y - r + 1, y + r):
            safey = 0 <= j and j < h
            if safey and x - r >= 0: pos.append((x - r, j))
            if safey and x + r < w: pos.append((x + r, j))

        return pos
