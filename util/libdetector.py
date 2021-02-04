#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

import json
import os
import pathlib
import tempfile

from zhkui import util

class LibDetector(object):
    def __init__(self, apkpath):
        ''' Detect third-party java libraries

        - apkpath str: The app name must end with '.apk', required by libscout.
        '''

        self.logger = util.Log()
        self.apkpath = util.getabs([apkpath])

    def detect_by_libscout(self, scoutjar, droidjar, profdir):
        ''' Detect third-party libraries by [libscout](https://github.com/reddr/LibScout)

        - scoutjar str: The path to libscout.jar
        - droidjar str: The path to android.jar
        - prodir str: The path to libscout profiles directory

        - return `zhkui.util.Result`:

            The Result.value is a dict contaning all the third-party libraries,
            see the following example

                {
                    'rx.android': {'name': 'RxAndroid', 'version': '1.2.0'},
                    'okhttp3': {'name': 'OkHttp', 'version': '3.3.1'},
                    'cn.bmob.v3': {'name': 'Facebook', 'version': '5.1.1'}

                }

            The key of the dict are the package showed the application, the `name` is for human.

        '''

        LOGBACK_CONFIG_TPL = '''
            <configuration>
                    <!-- WALA dex frontend -->
                    <logger name="com.ibm.wala.dalvik" level="off"/>

                    <!-- LibScout log config -->
                    <logger name="de.infsec.tpl.LibraryHandler" level="info"/>
                    <logger name="de.infsec.tpl.modules.libmatch.LibraryIdentifier" level="info"/>
                    <logger name="de.infsec.tpl.profile.ProfileMatch" level="info"/>
                    <logger name="de.infsec.tpl.hash.HashTreeOLD" level="debug"/>
                    <logger name="de.infsec.tpl.hashtree.HashTree" level="debug"/>
                    <logger name="de.infsec.tpl.utils.WalaUtils" level="info"/>
                    <logger name="de.infsec.tpl.TplCLI" level="info"/>

                    <logger name="de.infsec.tpl.modules.libmatch.LibCodeUsage" level="info"/>
                    <logger name="de.infsec.tpl.modules.updatability.LibraryUpdatability" level="debug"/>
                    <logger name="de.infsec.tpl.eval.LibraryApiAnalysis" level="info"/>

                    <logger name="de.infsec.tpl.modules.libapi" level="info"/>


                    <appender name="CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
                            <encoder>
                                    <pattern>%d{HH:mm:ss} %-5level %-25logger{0} : %msg%n</pattern>
                            </encoder>
                    </appender>

                    <appender name="FILE" class="ch.qos.logback.classic.sift.SiftingAppender">
                            <discriminator>
                                    <key>appPath</key>
                                    <defaultValue>./defaultApp</defaultValue>
                            </discriminator>
                            <sift>
                                    <appender name="${appPath}" class="ch.qos.logback.core.FileAppender">
                                            <file>${appPath}.log</file>
                                            <append>false</append>
                                            <layout class="ch.qos.logback.classic.PatternLayout">
                                                    <pattern>%d{HH:mm:ss} %-5level %-25logger{0} : %msg%n</pattern>
                                            </layout>
                                    </appender>
                            </sift>
                    </appender>


                    <root level="info">
                            <appender-ref ref="CONSOLE" />
                            <appender-ref ref="FILE" />
                    </root>
            </configuration>
        '''

        LIBSCOUT_CONFIG_TPL = '''
            #
            # This is the LibScout configuration file in TOML format
            #

            [ reporting ]

            # if true, shows comment from library.xml in logs/json
            # upon lib detection
            show_comments = false

            [ sdk ]

            # path to Android SDK jar file
            # (recommended to use an absolute path)
            ## android_sdk_jar = "/path/to/sdk/android.jar"


            [ logging ]

            # path to log4j config file
            # (recommended to use an absolute path)
            log4j_config_file = "{log4j}"


            [ packageTree ]

            # if set to true, the packageTree rendering uses ASCII characters
            # instead of box-drawing unicode characters (e.g. if the console
            # cannot correctly render unicode chars)
            ascii_rendering = false
        '''


        jar = util.getabs([scoutjar])
        profiles = util.getabs([profdir])
        if (not os.path.exists(jar)) or (not os.path.exists(profiles)):
            return util.Result(False, f'Could not find libscout jar or libscout profiles!')

        android_jar = util.getabs([droidjar])
        if not os.path.exists(android_jar):
            return util.Result(False, f'Could not find android jar at {android_jar}!')

        libscoutdir = os.path.dirname(jar)
        libscout_confdir = util.getabs([libscoutdir, 'config'])
        os.makedirs(libscout_confdir, exist_ok=True)

        log4j = os.path.join(libscout_confdir, 'logback.xml')
        if not os.path.exists(log4j):
            with open(log4j, 'w') as _:
                _.write(LOGBACK_CONFIG_TPL)

        libscout_config = os.path.join(libscout_confdir, 'config.xml')
        if not os.path.exists(libscout_config):
            with open(libscout_config, 'w') as _:
                _.write(LIBSCOUT_CONFIG_TPL.format(log4j = log4j))

        outdir = tempfile.TemporaryDirectory()

        '''
        -m: Disable console output
        -o match -p <profiles>: Match provided profiles
        -j <outdir>: Put result into <outputdir>
        -a <android jar>: For example, $ANDROID_HOME/platforms/android-29/android.jar
        -c,--libscout-conf <file>
        '''
        libscout_cmd = f'java -Xmx2g -jar {jar} -c {libscout_config} -m -o match -p {profiles} -j {outdir.name} -a {android_jar} {self.apkpath}'
        self.logger.v(f'LIBSCOUT CMD: {libscout_cmd}')
        r = util.runcmd(libscout_cmd)
        if r.status is not True:
            return util.Result(False, r.value)
        else:
            thirdlibs = {}
            for path in pathlib.Path(outdir.name).rglob('*.json'):
                with open(path, 'r') as _:
                    # The example output of libscout could be found at `docs/examples/libscout.json`
                    info = json.load(_)
                    for lib in info.get('lib_matches', {}):
                        pkgname = lib.get('libRootPackage', '')
                        if not pkgname: continue
                        thirdlibs[pkgname] = {'name': lib['libName'], 'version': lib['libVersion']}
            return util.Result(True, thirdlibs)
