#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

import argparse
import collections
import json
import os
import pickle
import re
import sys

from zhkui import util
from zhkui.util import Result

class MtdCounter(object):
    """ Structure used in `Graph` class

    - whole: the number of methods in a smali file
    - key:   the number of key methods
    - norm:  the number of normal methods
    - exile: the number of exiled methods which have empty body or have less
             than FUNC_LOWER_BOUND called functions
    """

    def __init__(self, whole, key, norm, exile):
        # the number of methods in current smali file
        self.whole = whole
        # the number of key methods
        self.key = key
        # the number of normal methods
        self.norm = norm
        # the number of exiled methods which have empty body or have less than
        # FUNC_LOWER_BOUND called functions
        self.exile = exile

class Graph(object):
    """ Extract key functions from smali file.

    Extract key functions from a single smali file or extract recursively
    from a folder containing smali files.

    Whatever the smali file(s) is in a single file or a folder, all of the key
    functions are kept in a dict.
    """

    def __init__(self, asmali, mode="batch"):
        """Create structures and initialize memebers

        :param asmali: A string. The path to a single smali or a smali folder.
        :param mode: Two modes are allowed:

            - `single`: A single smali file.
            - `batch`: A smali folder.

        There are several collection namedtuple type structures:

            - `Method`
                - fullname (str): The full name of the method
                - name (str): The short name of the method
                - body (list of str): The body of the method

            -  `Invoke`
                - whole : A list contains all methods.
                - sys: A list contains only system level's invokes.

            - `Smali`
                - graph: A dict, the graph of the function callings looks like::

                    {
                        'A': [A1, A2, ..., An],
                        'B': [B1, B2, ..., Bn],
                        1
                    }

                - stat: A MtdCounter structure.
                - function (list): All functions of the smali will be
                    stored in this member.  it is a list of two elements.
                    - functions[0]: A dict. Key is the name of function, value is the function body.
                    - functions[1]: A list of function names. It is used to save the
                          function order when processing.
        """

        self.Method = collections.namedtuple("Method", ["fullname", "name", "body"])
        self.Invoke = collections.namedtuple("Invoke", ["whole", "sys"])
        self.Smali = collections.namedtuple("Smali", ["graph", "stat", "function"])

        self.asmali = asmali
        self.mode = mode
        self.logger = util.Log()

    def _next_method(self, fp, cls):
        """Get next method in current smali

        :param fp: A `TextIOWrapper` object returned from `open()` function which
            is essentially the current file position pointer.
        :param cls: A string. Class name of the smali file.
        :return: A tuple: (status, Method). If `status` is True, then return
            a `Method` structure.
        """

        mtdbdy = []
        mtdname = None
        line = fp.readline()
        while line:
            if(line.strip().startswith('.method')):
                mtdname = self._getname(line.strip())
            # we do not store blank line
            if(mtdname and line.strip() != ''):
                mtdbdy.append(line.strip())
            if(line.strip().startswith('.end')):
                break
            line = fp.readline()

        if mtdname:
            return True, self.Method(name = mtdname, fullname = cls + '.' + mtdname, body = mtdbdy)
        else:
            return False, None

    def _getargs(self, argsline):
        """Extract the parameters of a method"""

        argsline = argsline.strip()
        mat = re.search("\((.*?)\)", argsline)
        return mat.group(1).strip()

    def _getinvoke(self, mtdbdy):
        """get invoked functions from a method body

        Rare cases are ignored, a case is listed as below for your reference::

            invoke-virtual {v0}, [I->clone()Ljava/lang/Object;

        :param mtdby: A list. It stores the method body, each element of the list is
            corresponding to one line of the method body.
        :return: A `Invoke` structure.
        """

        sysinvoke = []
        invoke = []
        sysapi = ["android", "java", "javax", "dalvik"]
        for line in mtdbdy:
            if(line.startswith("invoke-")):
                # we skip other rare cases that do not include ";->" in a function
                # calling
                if(";->" not in line):continue
                thisinvoke = self._getname(line)
                # put system invoke into sysinvoke list
                if(thisinvoke.split('.')[0] in sysapi):
                    sysinvoke.append(thisinvoke)
                # put all invokes into invoke list
                invoke.append(thisinvoke)
        return self.Invoke(whole = invoke, sys = sysinvoke)


    def _getname(self, mtdline):
        """Get name from a specific line code

        :param mtdline: A string. A line code waiting to be extracted names from.
        :return: Full name for smali file(.class), method(.method) or invoke(invoke-*)
            according to the mtdline parameter. If no name is found, return None.
        """

        mtdline = mtdline.strip()
        # name for method
        if(mtdline.startswith('.method')):
            # Cases:
            #====================================================================================
            #.method public constructor <init>(ILjava/lang/String;)V
            #.method static synthetic access$0(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;)Lorg/apache/http/HttpResponse;
            # case 1:
            #.method static synthetic $SWITCH_TABLE$com$admogo$AdMogoTargeting$Gender()[I
            # case 2: return $$
            # .method protected static final $$()Ljava/lang/String;
            # case 3: I have nothing to say for this case ....
            # .method ==> .method public /SDCARD()Lcv;
            # case 4:
            # .method public Landroid/widget/TimePicker;(status)status
            # case 5:
            # .method public application/x-shar()status
            # case 6:
            # .method private static synthetic $get$$class$groovy$lang$MetaClass()Ljava/lang/Class;
            #====================================================================================
            # mat = re.search('\s{1}(<?\w*>?\$?\w*)\(',mtdline)
            # Update to match case 1:
            # mat = re.search('\s{1}(<?\w*(\$\w+)*>?\$?\w*)\(',mtdline)
            # Update to match case 2:
            # mat = re.search('\s{1}(<?\w*>?(?:\$\w+)*(?:\$)*\w*)\(',mtdline)
            # Update to match case 3:
            # mat = re.search('\s{1}((?:/\w+)*<?\w*>?(?:\$\w+)*(?:\$)*\w*)\(',mtdline)
            # Update to match case 4:
            # mat = re.search('\s{1}((?:L\w+)?(?:/\w+)*<?\w*>?(?:\$\w+)*(?:\$)*\w*;?)\(',mtdline)
            # Update to match case 5:
            mat = re.search('\s{1}((?:L\w+)?(?:/\w+)*<?\w*>?(?:\$\w+)*(?:\$)*\w*;?)\(', mtdline)
            # Extract by the regular expression way
            if mat:
                # return the method full name with parameters
                return mat.group(1).strip() + '(' + self._getargs(mtdline) + ')'
            # The trivial but effective way
            else:
                end = mtdline.find('(')
                start = mtdline.rfind(' ')
                return mtdline[start + 1:end] + '(' + self._getargs(mtdline) + ')'

        # name for invoke-* function
        elif(mtdline.startswith('.class')):
            # Examples for class which could be used to correct the regular expression:
            # .class Lcom/software/marketapp/Off$1;
            # .class public final La;
            mat = re.search('L((?:\w+/)*(?:\w+)?.*);', mtdline)
            return mat.group(1).replace('/', '.')

        # name for smali
        elif(mtdline.startswith('invoke-')):
            # Take the pattern "Ljava/lang/Object;-><init>()V" as an example
            # to demonstrate the regular details:
            #
            # Firstly,the pattern begins with a uppercase letter 'L'
            # and then is followed by "xx/xx/ ... xx ;->",this could
            # be expressed as "(\w+/)+" since "xx/" appears at least once.
            # We also notice that the last "xx" is not appeared with a slash
            # so we should rewrite the expression as "(\w+/)+\w+" then followed by a
            # ";->".The second part of the regular expression is "<?\w+>?\(" which
            # has nothing to say but an escaped left brace.
            #
            # You may notice that many braces are presented in the expression,
            # they are used to capture the matched result. As the forgoing
            # example,we just want the two parts:"Ljava/lang/Object" and "<init>"
            # so we brace both of them.
            #
            # One interesting snippet you may wonder what exactly "(?:)" does.
            # this regular syntax tells the regular parser not to capture the matched
            # group,more details about this,please refer to the regular syntax:
            # http://www.regular-expressions.info/reference.html
            # Now we get a regular looking like "L((?:\w+/)+\w+);->(<?\w+>?)\("
            #
            # Everything seems to be going well! But having a look at the following example:
            # mtdline = 'invoke-direct {v1, v2}, Landroid/app/AlertDialog$Builder;-><init>(Landroid/content/Context;)V'
            # we will fail to match it! But do not be panic,since this is an easy problem we could solve it in seconds!
            # Just add "\$?\w*" into the above mentioned expression,then we are done!
            # The final regular expression to extract java API from smali is here:
            #
            # ==================================================================================================================
            # General cases to match:
            # case1:
            # invoke-static {v0}, Lh;->c(Landroid/content/Context;)Ljava/lang/String;
            # case2:
            # invoke-direct {v1, v2}, # Landroid/app/AlertDialog$Builder;-><init>(Landroid/content/Context;)V'
            # case3:
            # invoke-static {v0}, Lh;->c(Landroid/content/Context;)Ljava/lang/String;
            # case4:
            # invoke-static {p1}, Lcom/google/mygson/internal/$Gson$Preconditions;->checkNotNull(Ljava/lang/Object;)Ljava/lang/Object;
            # case5:
            # invoke-interface {p1, v0, v1}, Landroid/content/SharedPreferences$Editor;->putInt(Ljava/lang/String;I)Landroid/content/SharedPreferences$Editor;
            # case6:
            # invoke-static {}, Lcom/admogo/adapters/GoogleAdMobAdsAdapter;->$SWITCH_TABLE$com$admogo$AdMogoTargeting$Gender()[I
            # case7:But What the fuck is this damned thing?????
            # invoke-virtual {v0}, Lcom/madhouse/android/ads/$$$;->_()V
            # case8:
            # invoke-virtual {v0}, Lcom/madhouse/android/ads/aq;->$$$$()I
            # case9: Rare cases that will be skipped,see comments of getinvoke() function for more information
            # invoke-virtual {v0}, [I->clone()Ljava/lang/Object;
            # case10:
            # 'invoke-virtual {v0}, Landroid/telephony/PhoneNumberUtils;->worker #()Landroid/app/Application;'
            # case11:
            # invoke-direct {p0}, L$$OOOOOOOOOOOO/$OOOOOOOOOOOOOOOO/$OOOOOOOOOOOOOOOO/$OOOOOOOOOOOOOOOO/$$OOOOOOOOOOO;-><init>()V
            # Original regexp:
            # mat = re.search('L((?:\w+/)+\w+\$?\w*);->(<?\w+>?)\(',mtdline)
            # Update to match case3,case4
            # mat = re.search('L((?:\w+/)*(?:\$\w+)*\w*);->(<?\w+>?)\(',mtdline)
            # Update to match case5
            # mat = re.search('L((?:\w+/)*\w*\$?(?:\$\w+)*\w*);->(<?\w+>?)\(',mtdline)
            # Update to match case6
            # Matching Result:com.admogo.adapters.GoogleAdMobAdsAdapter.$SWITCH_TABLE$com$admogo$AdMogoTargeting$Gender
            # mat = re.search('L((?:\w+/)*\w*\$?(?:\$\w+)*\w*);->(<?(?:\$?\w+)*>?)\(',mtdline)
            # Update to match case7
            # mat = re.search('L((?:\w+/)*\w*\$*(?:\$\w+)*\w*);->(<?(?:\$?\w+)*>?)_?\(',mtdline)
            # Update to match case8
            # mat = re.search('L((?:\w+/)*\w*\$*(?:\$\w+)*\w*;->)(<?(?:\$?\w+)*>?_?\$*)\(',mtdline)
            # Update to match case10
            # mat = re.search('L((?:\w+/)*\w*\$*(?:\$\w+)*\w*;->)(.*?)\(',mtdline)
            # Update to match case11
            regexp = '''
                L((?:.*?/)*? # To match # To match L$$OOOOOOOOOOOO/$OOOOOOOOOOOOOOOO/$OOOOOOOOOOOOOOOO/$OOOOOOOOOOOOOOOO/
                             # Notice that the last "?" is critical which makes the
                             # pattern non-greedy mode or else the regexp will stuck into
                             # function calling like this:
                             # Lcom/adchina/android/ads/XmlEngine;->readXmlInfo(Ljava/lang/StringBuffer;Ljava/lang/StringBuffer;Ljava/lang/StringBuffer;) V
                (?:.*?))     # To match the last "$$OOOOOOOOOOO"
                ;->          # A delimeter which should not be catched
                (.*?)        # To match <init>
                \(           # To match the boundary flag and does not catch
            '''
            mat = re.search(regexp, mtdline, re.VERBOSE)

            # mat.groups() returns a tuple looking like ('java/lang/Object','<init>')
            # we join all of the elements with a dot and then replace all the slashes with
            # dots which results in 'java.lang.Object.<init>'
            matched = '.'.join(mat.groups()).replace('/', '.')
            return matched.strip() + '(' + self._getargs(mtdline) + ')'
        else:
            return None


    def _extract_func_from_a_smali(self, fsmali, smali=None):
        """Extract key functions from a single smali file

        :param fsmali: A string. The path to the smali file.
        :param smali: (optional) A collection type of `Smali`.
            If it is not None, process the smali file in
            an append mode. That is to say we will update information from current
            smali file into the `Smali` object.
        :return: A `Smali` structure.
        """

        # The lower bound for the number of system api calls
        # The percent of key functions when set up different lower bound values::
        # 1: 58.32% 2:33.40% 3:27.60% 4:23.74% 5:21.59%
        # To examine the trend in a intuitive way,see below codes used by gunplot:
        # plot 'gnudata' with points pt 7 ps 5,\
        #      'gnudata' lt 1 lw 2 smooth bezier
        KEYFUNC_LOWER_BOUND = 2

        # Functions should contain at least FUNC_LOWER_BOUND invoke(s) or else we will
        # exclude them from a normal function since they are worthless for us
        # notice that FUNC_LOWER_BOUND <= KEYFUNC_LOWER_BOUND
        FUNC_LOWER_BOUND = 1

        # If `Smali` is None, then we new one
        if not smali:
            graph = dict()
            smali = self.Smali(graph = graph, stat = MtdCounter(0, 0, 0, 0), function = [dict(), list()])
        graph = smali.graph
        mtdcounter = smali.stat
        function = smali.function

        psmali = open(fsmali, 'r')

        # get current smali class name
        cls = self._getname(psmali.readline())

        has_next_method, method = self._next_method(psmali, cls)
        while has_next_method:
            mtdcounter.whole += 1
            # Get what methods called by the current fuction
            function[0][method.fullname] = method.body
            function[1].append(method.fullname)
            invoke = self._getinvoke(method.body)

            # Check if the current function is key
            # If a function is regarded as key function, then
            # it should contain at least KEYFUNC_LOWER_BOUND system invoke(s)
            if(len(invoke.sys) >= KEYFUNC_LOWER_BOUND):
                # Add 1 flag to indicate the current function is key
                invoke.whole.append(1)
                mtdcounter.key += 1
            # otherwise, 0 flag is appened
            else:
                invoke.whole.append(0)

            # Save all satisfied functions into dict
            # - The function should call at least FUNC_LOWER_BOUND function
            # - Functions that have no invokes should been excluded
            # - [!] Notice that function calling list has been appended with a flag
            if(len(invoke.whole) - 1 >= FUNC_LOWER_BOUND):
                graph[method.fullname] = invoke.whole
                # Count non-key functions
                if(invoke.whole[-1] == 0):
                    mtdcounter.norm += 1
                # Count key functions
                else:
                    mtdcounter.key += 1
            else:
                # Count the exiled functions
                mtdcounter.exile += 1
            has_next_method, method = self._next_method(psmali, cls)
        psmali.close()
        return smali

    def _extract_func_from_smalidir(self, smalidir):
        """Extract all smali files in a folder recursively
        :param smalidir: The smali directory
        :return: A `Smali` structure.
        """

        firstmeet = True
        # The `Smali` object
        smali = None
        for root,dnames,fnames in os.walk(smalidir):
            for fname in fnames:
                if(os.path.splitext(fname)[1] == ".smali"):
                    fpath = os.path.join(root,fname)
                    if(firstmeet):
                        firstmeet = False
                        smali = self._extract_func_from_a_smali(fpath)
                    else:
                        smali = self._extract_func_from_a_smali(fpath, smali)
        return smali

    def graph(self):
        """Build graph from smali file(s)

        :return: Result(status, Smali)
        """

        if self.mode == "single":
            do_func = self._extract_func_from_a_smali
        elif self.mode == "batch":
            do_func = self._extract_func_from_smalidir
        else:
            return Result(status=False, value=f'{self.mode} is not valid mode!')

        try:
            smali = do_func(self.asmali)
            return Result(status=True, value=smali)
        except Exception as e:
            return Result(status=False, value=f'Exception {e}')
