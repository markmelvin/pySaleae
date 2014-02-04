import os
import numpy
from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext

DEPS_FOLDER = 'dependencies'

ext_modules=[ 
    Extension("SaleaeDevice",
			  
              sources = ["SaleaeDevice.pyx"],
              language="c++",                # this causes Pyrex/Cython to create C++ source
              include_dirs = [os.path.join(os.getcwd(), DEPS_FOLDER), numpy.get_include()],  # path to .h file(s)
              library_dirs = [os.path.join(os.getcwd(), DEPS_FOLDER)],  # path to library
              extra_compile_args = ["/D", "WIN32", "/EHsc"],
              libraries = ['SaleaeDevice'],
              ),
    Extension("analyzer",
              sources = ["analyzer.pyx"],
              language="c++",                # this causes Pyrex/Cython to create C++ source
              include_dirs = [os.path.join(os.getcwd(), DEPS_FOLDER), numpy.get_include()],  # path to .h file(s)
              library_dirs = [os.path.join(os.getcwd(), DEPS_FOLDER)],  # path to library
              extra_compile_args = ["/D", "WIN32", "/EHsc"],
              ),
]

setup(
  name = 'pySaleae',
  cmdclass = {'build_ext': build_ext},
  ext_modules = ext_modules,
)
