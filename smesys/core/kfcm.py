#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

'''
Requirement:
    Python 3.5 or a more recent version
'''

import collections
import hashlib
import numpy as np
import time

from zhkui.util import Result
from zhkui import util

Matrix = collections.namedtuple("Matrix", ["hashtbl", "plainmat", "hashmat"])
'''
A `Matrix` structure contains the follwoing members:
    - hashtbl dict: The map table from `plainmat` to `hashmat`
    - plainmat dict: The original matrix
    - hashmat dict: The hashed matrix
'''

class KFCM():
    def __init__(self, graph):
        """Create function calling matrix

        :param graph: A dict. It contains the function graph of an application.
        """

        self._callmatrix = dict()
        self._keyfunc, self._normfunc = list(), list()
        self._funcjar = graph
        self._allfunc = set(list(self._funcjar.keys()))
        self.sysapis = ["android","java","javax","dalvik"]
        self.logger = util.Log()

        for func in self._allfunc:
            # function calling row of 'func'
            funcrow = dict()
            # Remove the flag from called function lists
            calledfunc = set(self._funcjar[func][:-1])
            # If current function calls any function in allfunc
            # we save the callee(s) into target_calledfunc
            target_calledfunc = calledfunc & self._allfunc
            # Tuck funcrow into matrix if not empty
            for f in target_calledfunc:
                funcrow[f] = 1
            if(funcrow):
                self._callmatrix[func] = funcrow
                # We only save the function which have been saved into callmatrix
                if(self._funcjar[func][-1]):
                    # key function
                    self._keyfunc.append(func)
                else:
                    # normal function
                    self._normfunc.append(func)
        # Generate KFCM
        self._remove_normfunc()

    def _remove_normfunc(self):
        """Remove all normal functions from initialized matrix"""
        beg = time.time()

        rows = list(sorted(self._callmatrix.keys()))
        removedfunc = list()
        self.logger.d(f'Matrix Size: {len(rows)}x{len(rows)} Normal Function number: {len(self._normfunc)}')
        # Iterate every normal function and remove them
        # marked as i
        i = 0
        for normfunc in self._normfunc:
            self.logger.v(f'Remove normal function {i}/{len(self._normfunc)} ...')
            i += 1
            # Skip those functions that are not in self._callmatrix
            if normfunc not in rows: continue
            # Iterate every other functions except current normal function
            # marked as j
            for func in rows:
                # skip self and removed functions
                if func == normfunc or func in removedfunc:
                    continue
                # Extract all functions called by current function
                curcalled = set(self._callmatrix[func].keys())
                # If current normal function is called by current row function
                if normfunc in curcalled:
                    # =====================================================================
                    # Mark the common function called by i and j as k
                    # Situation One: if i.k and j.k and j.k > i.k  then update j.k to i.k
                    # =====================================================================

                    # Find the common normal functions that current row function has called
                    crossed = curcalled & set(self._callmatrix[normfunc])
                    for crossedfunc in crossed:
                        if self._callmatrix[func][crossedfunc] > self._callmatrix[normfunc][crossedfunc]:
                            self._callmatrix[func][crossedfunc] = self._callmatrix[normfunc][crossedfunc]

                    # =====================================================================
                    # Mark another function called by i as k
                    # Situation Two: if i.k but not j.k then update j.k to i.k + 1
                    # In this situation,minus the crossed functions from all
                    # functions called by current normal function and we get the
                    # fucntions which are not called by current row function
                    # =====================================================================

                    diffed = set(self._callmatrix[normfunc]) - crossed
                    for diffedfunc in diffed:
                        self._callmatrix[func][diffedfunc] = self._callmatrix[normfunc][diffedfunc] + 1

            # Remove the normfunc column when we have them done
            for keyfunc in self._callmatrix.keys():
                if normfunc in list(self._callmatrix[keyfunc].keys()):
                    self._callmatrix[keyfunc].pop(normfunc)
            self._callmatrix.pop(normfunc)
            removedfunc.append(normfunc)
            # continue to remove the next normal function
        end = time.time()
        self.logger.d(f'Removing normal function costs {(end - beg)/60} minutes')

    def _hash_sysapis_serial(self, serial):
        """ Hash a sequence of function callings to a md5 value

        :param serial: A list. The function sequence called by a function
        :return: A md5 value string. .
        """
        calledapi_list = list()
        for func in serial:
            if func.split('.')[0] in self.sysapis:
                calledapi_list.append(func)
        # DO NOT SORT THE APILIST
        # Calculate md5 hash of the api list,notice that each api is seperated by a colon
        apistr = ':'.join(calledapi_list)
        hashstr = hashlib.md5(apistr.encode('utf-8')).hexdigest()
        return hashstr


    def printkfcm(self):
        """ Print matrix stored in dict """
        for key in list(self._callmatrix.keys()):
            print("%s ==>\t" % (key),end = '')
            funcrow = self._callmatrix[key]
            print(funcrow)

    def _get_plainmat(self):
        """Get KFCM"""
        return self._callmatrix


    def _get_hashedmat(self):
        """Convert a unhashed matrix(returned from KFCM class) to hashed matrix

        :return: Return a dict containing the hash table and hased matrix
            - map : The hash table from hashed matrix from unhashed matrix.
            - matrix: The hashed matrix.
        """

        unhash_matrix, caller_callee = self._get_plainmat(), self._funcjar
        # Iterate the whole matrix to generate a hash table
        hash_table = dict()
        for row in sorted(unhash_matrix.keys()):
            row_callees = caller_callee[row]
            hash_table[row] = self._hash_sysapis_serial(row_callees[:-1])
            for col in sorted(unhash_matrix[row].keys()):
                col_callees = caller_callee[col]
                hash_table[col] = self._hash_sysapis_serial(col_callees[:-1])

        # Generate the hashed matrix
        hashed_matrix = dict()
        for row in sorted(unhash_matrix.keys()):
            tmp = {}
            for col in sorted(unhash_matrix[row].keys()):
                tmp[hash_table[col]] = unhash_matrix[row][col]
            hashed_matrix[hash_table[row]] = tmp

        # `hashtbl` and `hashmat`
        return hash_table, hashed_matrix

    def kfcm(self):
        hashtbl, hashmat = self._get_hashedmat()
        plainmat = self._get_plainmat()
        matrix = Matrix(hashtbl=hashtbl, plainmat=plainmat, hashmat=hashmat)
        return Result(status=True, value=matrix)
