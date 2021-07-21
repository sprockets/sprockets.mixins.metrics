#!/usr/bin/env python3
#

import pathlib

import setuptools

from sprockets.mixins import metrics


REPO = pathlib.Path(__file__).parent


setuptools.setup(
    name='sprockets.mixins.metrics',
    version=metrics.__version__,
    description='Record performance metrics about your application',
    long_description='\n'+open('README.rst').read(),
    author='AWeber Communications',
    author_email='api@aweber.com',
    license='BSD',
    url='https://github.com/sprockets/sprockets.mixins.metrics',
    install_requires=REPO.joinpath('requires/installation.txt').read_text(),
    tests_require=REPO.joinpath('requires/testing.txt').read_text(),
    packages=setuptools.find_packages(exclude=['examples.']),
    namespace_packages=['sprockets', 'sprockets.mixins'],
    classifiers=[
        'Development Status :: 7 - Inactive',
        'Environment :: No Input/Output (Daemon)',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules'],
    test_suite='nose.collector',
    python_requires='>=3.7',
    zip_safe=True,
)
