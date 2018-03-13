#!/usr/bin/env python

from setuptools import setup

setup(
    name='libfaketimefs',
    version='0.0.1',
    description='Dynamic faketimerc file using a FUSE filesystem',
    author='Raymond Butcher',
    author_email='ray.butcher@claranet.uk',
    url='https://github.com/claranet/libfaketimefs',
    license='MIT License',
    packages=(
        'libfaketimefs',
        'libfaketimefs.vendored.fusepy',
    ),
    scripts=(
        'bin/libfaketimefs',
    ),
)
