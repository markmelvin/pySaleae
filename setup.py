import os
import numpy
from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext

ext_modules=[ 
    Extension("SaleaeDevice",
              sources = ["SaleaeDevice.pyx"],
              language="c++",                # this causes Pyrex/Cython to create C++ source
              include_dirs = [os.getcwd(), numpy.get_include()],  # path to .h file(s)
              library_dirs = [os.getcwd()],  # path to library
              extra_compile_args = ["/D", "WIN32", "/EHsc"],
              #extra_link_args = ["/MANIFESTUAC:level='asInvoker' uiAccess='false'"],
              #extra_link_args = ["/MANIFEST:NO"],
              libraries = ['SaleaeDevice'],
              ),
    Extension("analyzer",
              sources = ["analyzer.pyx"],
              language="c++",                # this causes Pyrex/Cython to create C++ source
              include_dirs = [os.getcwd(), numpy.get_include()],  # path to .h file(s)
              library_dirs = [os.getcwd()],  # path to library
              extra_compile_args = ["/D", "WIN32", "/EHsc"],
              ),
    Extension("pcm_analyzer",
              sources = ["pcm_analyzer.pyx"],
              language="c++",                # this causes Pyrex/Cython to create C++ source
              include_dirs = [os.getcwd(), numpy.get_include()],  # path to .h file(s)
              library_dirs = [os.getcwd()],  # path to library
              extra_compile_args = ["/D", "WIN32", "/EHsc"],
              )
]

setup(
  name = 'pyLogic',
  cmdclass = {'build_ext': build_ext},
  ext_modules = ext_modules,
)
