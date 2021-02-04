#! /usr/bin/env python3
#! -*- coding:utf-8 -*-


import random
import requests
import time

from zhkui import util
from zhkui.util import Result

"""
TODO(bugnofree):
    - The function name `_checkif_scanned` is not good, may be renamed for better recongnizing.
"""

class VT(object):
    """Query from VirusTotal"""

    def __init__(self, app, vtkeys):
        """
        :param app: An apllication object.
        :param vtkeys: A list. The authorized keys to look up results from virus total.
        """

        self.app = app
        self.keys = vtkeys
        # VT response codes
        self._VT_NOT_EXIST = 0
        self._VT_QUEUE = -2
        self._VT_OK = 1
        self._VT_UNKNOW = -1
        # Four requests in one minute for each API key
        self._VT_LOOKUP_GAP = 60 / 4 / len(self.keys)
        self._VT_RETRY_LIMIT = 5
        self.logger = util.Log()

    def _checkif_scanned(self, key):
        """Check if the application has been scanned.

        We do this through submitting the sample's hash(here is sha256) to vt
        with the private key.

        :param key: An API key to virus total.
        :return: A tuple:(status, json).
            * `status`: If the check is successful, this value is set to True.
            * `json`: It contains the responsed json data if successful, or else
                None.
        """

        report_url = 'https://www.virustotal.com/vtapi/v2/file/report'
        params = {'apikey' : key, 'resource': self.app.sha256}
        headers = {
          "Accept-Encoding": "gzip, deflate",
          "User-Agent" : "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.96 Safari/537.36"
        }
        succ = False
        curtry = 0
        while not succ:
            curtry += 1
            try:
                # Setting the value of timeout to 5 seconds is a good practice
                response = requests.get(report_url, params = params, headers = headers, timeout = 5)
                succ = True
            except Exception as e:
                self.logger.d("[!] Connecting to VT server is failed!")
                succ = False

            if not succ:
                if curtry <= self._VT_RETRY_LIMIT:
                    time.sleep(20)
                    self.logger.d("[+] The %d times to try ..." % (curtry))
                else:
                    break
        if succ:
            try:
                respjson = response.json()
            except Exception as e:
                # Sometimes,response.json() will raise json.decoder.JSONDecodeError
                # exception,we should return None if this exception happens
                respjson = None
                succ = False
        else:
            respjson = None

        return succ, respjson


    def _upload2scan(self, key):
        """ Upload sample to vt to scan

        :param key: An API key to virus total.

        :return: A tuple: (status, json).

            * `status`: If the upload is successful, then status is True.
            * `json`: If staus is True, then this value is the responsed json
                data returned from vt, None if otherwise. Note that `json`
                is not used currently which may be removed in future.
        """

        scanurl = 'https://www.virustotal.com/vtapi/v2/file/scan'
        params = {'apikey': key}
        files = {'file':(self.app.name, open(self.app.path, 'rb'))}
        self.logger.d("[^] Uploading to Virus Total server ...")
        curtry = 0
        uploaded = False
        while not uploaded:
            curtry += 1
            try:
                resp = requests.post(scanurl, files = files, params = params)
                if resp.status_code == 200:
                    self.logger.d("[$] Uploading {p_name} is done !".format(
                        p_name = self.app.name))
                    uploaded = True
                else:
                    self.logger.d("[!] Oops,Uploading {:s} is failed!".format(
                        self.app.name))
                    self.logger.d("[!]      Response Code: {:d}".format(resp.status_code))
                    uploaded = False
            except Exception as e:
                uploaded = False
                self.logger.d("[!] Oops,Uploading {:s} is failed when posting to the VT ...!".format(
                    self.app.name))

            if uploaded:
                retjson = resp.json()
                break
            else:
                if curtry <= self._VT_RETRY_LIMIT:
                    time.sleep(20)
                    self.logger.d("[+] The %d times try ..." % (curtry))
                else:
                    retjson = None
                    break
        return uploaded, retjson


    def _loopcheck(self, respcode):
        """Check if vt has finished the analysis for the submitted application

        :param respcode: The response code from VT.
        :return: A tuple: (status, json). `status`: If the query is finally successful, the
            value is True. `json`: The json format data returned from vt.

        """

        retjson = None
        retrycnt = 0
        while respcode != self._VT_OK:
            self.logger.d("[...] Sleep %f seconds for scanning ..." % (self._VT_LOOKUP_GAP))
            time.sleep(self._VT_LOOKUP_GAP)
            ok, result = self._checkif_scanned(self.keys[random.randint(0, len(self.keys) - 1)])
            if not ok:
                retjson = result
                if retjson:
                    respcode = retjson['response_code']
                    self.logger.d("\t[+] Current response code : %d" % (respcode))
            else:
                if retrycnt > self._VT_RETRY_LIMIT:
                    self.logger.d("[!] Too many failed tries .. Stop loop check...")
                    retjson = None
                    break
            retrycnt += 1

        if retjson:
            return True, retjson
        else:
            self.logger.d("[!] Loop check failed!")
            return False, None

    def lookup(self):
        """Lookup from virus total

        :return: Result(status, response)
        """

        ikey = 0
        succ = False
        print("[^] Lookup {p_name}({p_md5}) ...".format(
            p_name = self.app.name, p_md5 = self.app.md5))
        succ, resp = self._checkif_scanned(self.keys[random.randint(0, len(self.keys) - 1)])
        if succ:
            retjson = resp
            respcode = retjson['response_code']
            if respcode == self._VT_UNKNOW:
                return Result(status=False, value=f'Unknown errors: {self.app.name} ({self.app.md5})')
            elif respcode == self._VT_QUEUE:
                err = f'[...] The file {self.app.name} ({self.app.md5}) is still in analysis queue ...'
                self.logger.d(err)
                succ, result = self._loopcheck(respcode)
                if succ:
                    return Result(status=True, value=result)
                else:
                    return Result(status=False, value='Analysis is failed!')
            elif respcode == self._VT_NOT_EXIST:
                time.sleep(self._VT_LOOKUP_GAP)
                msg = "[!] The file {p_name}({p_md5}) is not analyzed by VT, now submit the app to VT ...".format(p_name = self.app.name, p_md5 = self.app.md5)
                self.logger.d(msg)
                succ, result = self._upload2scan(self.keys[random.randint(0, len(self.keys) - 1)])
                if succ:
                    succ, result = self._loopcheck(respcode)
                    return Result(status=True, value=result)
                else:
                    return Result(status=False, value='')
            elif respcode == self._VT_OK:
                self.logger.d("[+] Already scanned in VirusTotal ...")
                return Result(status=True, value=retjson)
            else:
                return Result(status=False, value='Peculiar Error Happened!')
        else:
            return Result(status=False, value='Checking the status of VT is failed!')
