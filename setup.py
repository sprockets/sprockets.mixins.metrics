#!/usr/bin/env python
#

import os.path

import setuptools

from sprockets.mixins import metrics


def read_requirements(name):
    requirements = []
    try:
        with open(os.path.join('requires', name)) as req_file:
            for line in req_file:
                if '#' in line:
                    line = line[:line.index('#')]
                line = line.strip()
                if line.startswith('-r'):
                    requirements.extend(read_requirements(line[2:].strip()))
                elif line and not line.startswith('-'):
                    requirements.append(line)
    except IOError:
        pass
    return requirements


setuptools.setup(
    name='sprockets.mixins.metrics',
    version=metrics.__version__,
    description='Record performance metrics about your application',
    long_description='\n'+open('README.rst').read(),
    author='AWeber Communications',
    author_email='api@aweber.com',
    license='BSD',
    url='https://github.com/sprockets/sprockets.mixins.metrics',
    install_requires=read_requirements('installation.txt'),
    tests_require=read_requirements('testing.txt'),
    packages=setuptools.find_packages(exclude=['examples.']),
    namespace_packages=['sprockets', 'sprockets.mixins'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: No Input/Output (Daemon)',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules'],
    test_suite='nose.collector',
    zip_safe=True,
)
