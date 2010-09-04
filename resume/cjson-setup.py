#!/usr/bin/python

from distutils.core import setup, Extension

setup(ext_modules  = [Extension(name='cjson', sources=['cjson.c'])])
