#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

''' Various misc methods to easy the life

This module define a universal return value `Result`, it is essentially a
`collections.namedtuple`.
'''
__pdoc__ = {}

import collections
import hashlib
import json
import gzip
import numpy as np
import os
import pathlib
from pathlib import Path
import subprocess
import uuid
import time

from . import libdetector
from .log import Log

Result = collections.namedtuple('Result', ['status', 'value'] )
__pdoc__['Result.status'] = 'Indicate the status, True, False or anything else'
__pdoc__['Result.value'] = 'Holds the error message if failed or the right values if success.'

def getabs(paths):
    ''' Get absolute path from a list of path components

    - paths list: A list containing path components(str or pathlib.Path)
    - return str: The resolved path

    Parse symbolic path and support `~`, `$HOME` or any else environment
    variables in the path. If you add a customized environment variable,
    please ensure using `export` keyword if you are in *nix system.
    Assume you define ANDROID_HOME as following, it will not work,
    because it is a variable, but not a environment variable.

        ANDROID_HOME=$HOME/Library/Android/sdk

    The right way is

        export ANDROID_HOME=$HOME/Library/Android/sdk

    Following are some examples to use this method

        # ok
        config_path = getabs(['$HOME', '.config', 'config.json'])
        # error, no path component is provided
        config_path = getabs([])
        # error, the first path component must not be empty
        config_path = getabs([" ", '.config'])

    '''

    if len(paths) <= 0:
        raise Exception('No path components are found!')

    paths = [str(path) for path in paths]

    if not paths[0].strip():
        raise Exception('The first component of a path cannot be empty!')

    path = os.path.join(*paths)
    path = os.path.expanduser(path)
    path = os.path.expandvars(path)
    path = os.path.realpath(path)
    return path

def runcmd(cmd, verbose=False):
    ''' Run a string as command, the output will be put as value into `zhkui.util.Result`

    - cmd str: The command to run
    - verbose bool(optional): If enabled, it will print the running command and output.
    '''
    completer = subprocess.run(cmd, shell=True, universal_newlines=True, capture_output=True)
    status = True if completer.returncode == 0 else False
    output = completer.stdout.strip() if completer.stdout else ''
    if verbose: print(f'CMD: {cmd}\nOUTPUT: {output}')
    if status is False:
        errmsg = completer.stderr.strip()
        if errmsg: output += f'\nError Info: {errmsg}'
    return Result(status, value=output)

def json_from_gzip_bytes(data):
    ''' Load gzipped `bytes` data into json object

    For example

        with open('test.json.gz', 'rb') as _:
            d = util.json_from_gzip_bytes(_.read())
    '''
    return json.loads(gzip.decompress(data).decode('utf-8'))

def json_to_gzip_bytes(obj):
    ''' Save json object into gzipped `bytes`

    For example

        d = { 'a': 2, 'b': 3}
        with open('test.json.gz', 'wb') as _:
            _.write(util.json_to_gzip_bytes(d))
    '''

    return gzip.compress(json.dumps(obj).encode('utf-8'))

def filehash(path, typ):
    '''Get specific hash of the file

    - typ str: md5, sha256 or sha1
    - return `Result(status, hashval)`
    '''
    path = getabs([path])
    if not os.path.exists(path):
        return Result(status=False, value=f'File {path} not found')
    else:
        with open(path, mode='rb') as _:
            binary = _.read()
            r = datahash(binary, typ)
            if not r.status: return r
            return Result(status=True, value=r.value)

def datahash(data, typ):
    '''
    - data bytes: Stream of byte.
    - typ str: md5, sha256 or sha1
    - return `Result(status, hashval)`
    '''
    suppported_hashes = ['md5', 'sha256', 'sha1']
    if typ not in suppported_hashes:
        return Result(status=False, value=f'Only support hashes: {suppported_hashes}')

    if typ == 'md5':
        hashval = hashlib.md5(data).hexdigest()
    elif typ == 'sha1':
        hashval = hashlib.sha1(data).hexdigest()
    else:
        hashval = hashlib.sha256(data).hexdigest()

    return Result(True, hashval)

def create_dir_hierarchy(root, hierarchy):
    ''' Create a directory structure

    - root str: The full path of the root directory
    - hierarchy str:The hierarchy representing the directory structure.

        The hierarchy is a string with specific format. An example is given as below:

            apps/{
                android/{black, white},
                ios/{black, white},
                linux/{black, white},
                mac/{white, black},
                windows/{black, white}
            },
            assets/{
                icons, imgs
            }

        You could also write them in one line

            apps/{android/{black, white}, ios/{black, white}, linux/{black, white}, mac/{white, black}, windows/{black, white} }, assets/{icons, imgs}

        Both the two style represent the following structure

            <rootdir>
                ├── apps/
                │   ├── android/
                │   │   ├── black/
                │   │   └── white/
                │   ├── ios/
                │   │   ├── black/
                │   │   └── white/
                │   ├── linux/
                │   │   ├── black/
                │   │   └── white/
                │   ├── mac/
                │   │   ├── black/
                │   │   └── white/
                │   └── windows/
                │       ├── black/
                │       └── white/
                └── assets/
                    ├── icons/
                    └── imgs/

        A directory is denoted as `<dirname>/` and it's subdirectories should be
        included immediately in a brace with comma as separator.

        Notice that all newline and spaces will be removed from the hierarchy string.
    '''

    if not hierarchy.strip():
        return
    else:
        hierarchy = hierarchy.replace(' ', '').replace('\n', '')
    dir_idx = hierarchy.find(",")
    hier_idx = hierarchy.find("/{")
    if dir_idx == -1: dir_idx = len(hierarchy)
    if hier_idx == -1: hier_idx = len(hierarchy)

    # A `,` is found and the first item is a single directory
    if dir_idx < hier_idx:
        dirname = hierarchy[:dir_idx].strip()
        os.makedirs(os.path.join(root, dirname), exist_ok=True)
        create_dir_hierarchy(root, hierarchy[dir_idx + 1:])

    # A `/{` is found and the first item is a directory hierarchy
    elif dir_idx > hier_idx:
        endidx = -1
        counter = 1
        for idxch in range(len(hierarchy[hier_idx + 2:])):
            ch = hierarchy[hier_idx + 2 + idxch]
            if ch == '{': counter += 1
            if ch == '}': counter -= 1
            if counter == 0:
                endidx = hier_idx + 2 + idxch
                break
        if counter != 0:
            print("Hierarchy format error!")
            sys.exit(1)
        new_hierarchy = hierarchy[hier_idx + 2:endidx]
        newroot = os.path.join(root, hierarchy[:hier_idx])
        create_dir_hierarchy(newroot, new_hierarchy)
        create_dir_hierarchy(root, hierarchy[endidx + 2:])

    # Neither `,` or `/{`  is found, hence a bare directory
    else:
        os.makedirs(os.path.join(root, hierarchy.strip()), exist_ok=True)

def remove_if_exist(filepath):
    if os.path.exists(filepath):
        os.remove(filepath)

def check_path(path):
    if not path.strip(): return False
    if not os.path.exists(getabs([path])): return False
    return True

class App(object):
    def __init__(self, path):
        """ A class that represents an application.

        - path str: The full path of the application
        """

        self.path = getabs([path])
        self.name = os.path.basename(self.path)
        self.sz = os.path.getsize(self.path)

        md5 = filehash(self.path, 'md5')
        sha256 = filehash(self.path, 'sha256')
        sha1 = filehash(self.path, 'sha1')
        if md5.status and sha256.status and sha1.status:
            self.md5 = md5.value
            self.sha256 = sha256.value
            self.sha1 = sha1.value
        else:
            err = md5.value if not md5.status else sha256.value
            raise Exception(f'Cannot get hash of {path}: {err}!')

    def __str__(self):
        info = (
            f'Information for application: {self.name}\n'
            f'path:    {self.path}\n'
            f'name:    {self.name}\n'
            f'size:    {self.sz}\n'
            f'md5:     {self.md5}\n'
            f'sha256:  {self.sha256}'
        )
        return info

def get_adjmat(adjlst):
    ''' Convert adjacent list to adjacent matrix for directed graph

    - adjlst dict: An example is showed as below

            {
                'A': {
                    'B': 1,
                    'C': 2,
                },
            }

        The top-level keys are the callers, the nested keys are the calles, the
        nested key's value is the weight between the caller and the callee.

        The example above will generate the following output:

            [[0. 1. 2.]
             [0. 0. 0.]
             [0. 0. 0.]]

        If you want to dump the 2d array into csv, you may use

            np.savetxt('mat.csv', matrix, delimiter=',', fmt='%d')

    - return numpy 2d array: The resulted matrix[i][j] represents node i calls node j
    '''

    fields = set()
    for caller in adjlst:
        fields.add(caller)
        for callee in adjlst[caller]:
            fields.add(callee)

    fields = sorted(list(fields))

    dim = len(fields)
    matrix = np.zeros((dim, dim))
    hashfields = dict(zip(range(dim), fields))

    for r in range(dim):
        if hashfields[r] in adjlst.keys():
            rowkeys = adjlst[hashfields[r]].keys()
            for c in range(dim):
                if hashfields[c] in rowkeys:
                    matrix[r, c] = adjlst[hashfields[r]][hashfields[c]]

    return matrix

def mktmpdir(parentdir, duration=30 * 60):
    ''' Make temporary directory in `parentdir` with meta info

    - return Result(status, value): value is a dict, an example is showed below

    {
        'dir': The temporary directory path
        'expire': Expires datetime in str
    }
    '''

    uuidval = str(uuid.uuid4())
    filedir = Path(parentdir, uuidval)
    os.makedirs(filedir, exist_ok=True)

    meta = { 'birth': int(time.time()), 'live': duration }
    with open(Path(filedir, '.meta'), 'w') as _:
        json.dump(meta, _)

    expire = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(meta['birth'] + meta['live']))
    return Result(True, value={ 'dir': filedir, 'expire': expire, 'id': uuidval })
