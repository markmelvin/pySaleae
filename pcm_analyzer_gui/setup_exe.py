##!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""
Build an executable for the PCM streaming test app.
"""
#
#
# Copyright (c) 2011 Semiconductor Components Industries, LLC
# (d/b/a ON Semiconductor). All Rights Reserved.
#
# This code is the property of ON Semiconductor and may not be redistributed
# in any form without prior written permission from ON Semiconductor. The
# terms of use and warranty for this code are covered by contractual
# agreements between ON Semiconductor and the licensee.
# ----------------------------------------------------------------------------
# $Revision: 1.4 $
# $Date: 2012/01/23 22:14:24 $
# ----------------------------------------------------------------------------
#

import sys
import os
from resources import *
import matplotlib

from distutils.core import setup
from glob import glob
import py2exe

################################################################

# If run without args, build executables, in quiet mode.
if len(sys.argv) == 1:
    sys.argv.append("py2exe")
    sys.argv.append("-q")

class Target:
    def __init__(self, **kw):
        self.__dict__.update(kw)
        # for the versioninfo resources
        self.version = APP_VERSION
        self.company_name = COMPANY_NAME
        self.copyright = COPYRIGHT
        self.name = APP_NAME


app = Target(
    # used for the versioninfo resource
    description = APP_DESCRIPTION,

    # what to build
    script = "pcm2wav.py",
    dest_base = "pcm2wav",
    )

# Certain GUI things don't work if the Qt .dlls
# are bundled into the executable.  Thus, they must be included
# as data files.
# We exclude them later in 'dll_excludes' because we still want
# all the other junk bundled into the executable.
_PYSIDEDIR = r'C:\Python27\Lib\site-packages\PySide'
data_files = [('.', glob(r'.\dlls\*.*') + ['SaleaeDevice.dll', 'SaleaeDevice.pyd',
                     'analyzer.pyd', 'pcm_analyzer.pyd',
                     os.path.join(_PYSIDEDIR,'shiboken-python2.7.dll'),
                     os.path.join(_PYSIDEDIR,'QtCore4.dll'),
                     os.path.join(_PYSIDEDIR,'QtGui4.dll')]),
             ]
data_files.extend(matplotlib.get_py2exe_datafiles())   # This returns a list of tuples

sys.path.append(".\dlls")

setup(
        data_files = data_files,
        options = {"py2exe": {"compressed": 1,
                   "excludes"     : ['SaleaeDevice', 'analyzer', 'pcm_analyzer', 'Tkconstants', 'Tkinter', 'tcl', '_gtkagg', '_tkagg'],
                   "packages" : ["numpy", "wave"],
                   "dll_excludes" : ['SaleaeDevice.dll', 'shiboken-python2.7.dll','QtCore4.dll','QtGui4.dll'],
                   "optimize": 2,
                   "bundle_files": 2,
                   }},
        zipfile = None,
        windows = [app]
    )
