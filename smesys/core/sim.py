#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

"""
Simliairty comparison kernel module.
"""

import copy
import collections
import hashlib
import numpy as np

from zhkui.util import Result
from zhkui import util

class SIM(object):
    def __init__(self, alpha, beta):
        """ Simliairty comparison kernel module

        :param alpha: The hashed matrix of alpah side.
        :param beta: The hashed matrix of beta side.
        """

        self.alpha = alpha
        self.beta = beta
        # Default system apis prefix
        self.sysapis = ["android","java","javax","dalvik"]
        self.logger = util.Log()

    def sim(self):
        """Get the similar information between two applications.

        :return: A `Sim` collection object:
            - level: A number indicating how the two application are similar.
            - commkey: A list containing the common keys of the two
              applications.
        """
        Sim = collections.namedtuple("Sim", ["level", "commkey"])
        siminfo = self.__getsiminfo()
        return Result(status=True, value=Sim(level = siminfo["level"], commkey = siminfo["commkey"]))

    def __getsiminfo(self):
        """To examine the similarity of the two samples.

        :return: A dict containing similar information.
        """

        siminfo = {'level':0, 'commkey':None}

        alphafields = self.__get_matrix_fields(self.alpha)
        betafields = self.__get_matrix_fields(self.beta)

        common_keys = alphafields & betafields
        siminfo['commkey'] = list(common_keys.copy())

        if(len(common_keys) == 0):
            siminfo['level'] = 0
            return siminfo

        alpah_submat = self.__submatrix(self.alpha, common_keys)
        beta_submat = self.__submatrix(self.beta, common_keys)

        # Well,let us convert the sparse matrix to dense matrix
        # although I do not wannt to do this,but for making the
        # life easy,I make this decision.
        realalpha = self.__fill_matrix(alpah_submat, common_keys)
        realbeta = self.__fill_matrix(beta_submat, common_keys)

        # np.any(MATRX):return true if there exists an element is not zero
        # Here if a zeros matrix appears,then return 0
        if((not np.any(realalpha)) or (not np.any(realbeta))):
            siminfo['level'] = 0
            return siminfo

        # Now we have got the similar submatrix of the two sides' matrix
        # it's time to calculate their similarity
        nr,nc = realalpha.shape

        numerator,denominator = 0.0,0.0
        try:
            for r in range(nr):
                for c in range(nc):
                    if(realalpha[r,c] == realbeta[r,c] and realalpha[r,c] != 0):
                        numerator += 1
                    elif(realalpha[r,c] == 0 or realbeta[r,c] == 0):
                        numerator += 0
                    else:
                        mincellval = min(realalpha[r,c],realbeta[r,c])
                        maxcellval = max(realalpha[r,c],realbeta[r,c])
                        numerator += mincellval / maxcellval

                    if(realalpha[r,c] == 0 and realbeta[r,c] == 0):
                        denominator += 0
                    else:
                        denominator += 1
            siminfo['level'] = numerator / denominator;
            return siminfo
        except Exception as e:
            self.logger.e(f"Comparison Failed {xmd5} vs {ymd5}: {e}")
            siminfo['level'] = -1
            return siminfo

    def __fill_matrix(self, matrix, common_keys):
        """ Convert dict-shape matrix to rect-shape matrix

        :param matrix: The matrix hold in a dictionary
        :param common_keys: See the example showed below::

            Common keys: B,C,E
            ------------------------
             alpha    |  beta
            ------------------------
            B         |  B
                E:2   |      E:2
            C         |  E
                B:1   |      C:1
            E         |
                C:3   |
            ------------------------

        :return: Return a numpy matrix.
        """

        dim = len(common_keys)
        realmatrix = np.zeros((dim,dim))
        hashfields = dict(zip(range(dim),sorted(common_keys)))

        for r in range(dim):
            if hashfields[r] in sorted(matrix.keys()):
                rowkeys = sorted(matrix[hashfields[r]].keys())
                for c in range(dim):
                    if hashfields[c] in rowkeys:
                        realmatrix[r,c] = matrix[hashfields[r]][hashfields[c]]
        return realmatrix

    def __submatrix(self, matrix, common_keys):
        """Reduce matrix to only contain common keys

        This function is used to extract common matrix

        :return: The common matrix.
        """

        dup = copy.deepcopy(matrix)
        for r in list(dup.keys()):
            if r not in common_keys:
                dup.pop(r)
            else:
                for c in list(dup[r].keys()):
                    if c not in common_keys:
                        dup[r].pop(c)
        return dup

    @staticmethod
    def __get_matrix_fields(matrix):
        """Get fields from dict-like matrix
        :return: A set containing all fields of the corresponding matrix.
        """
        fields = set(matrix.keys())
        for r in matrix.keys():
            fields = fields | set(matrix[r].keys())
        return fields
