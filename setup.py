from distutils.core import setup
from setuptools import find_packages
try: # for pip >= 10
    from pip._internal.req import parse_requirements
except ImportError: # for pip <= 9.0.3
    from pip.req import parse_requirements

with open("README.md", "r") as fh:
    long_description = fh.read()

#install_reqs = parse_requirements('requirements.txt', session='hack')
#reqs = [str(ir.req) for ir in install_reqs]

with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(
  name = 'inferout',
  packages = find_packages(),
  version = '0.0.0a3',
  license='GPLv3',
  description = 'Distributed Scale Out Framework for ML models serving/inference',
  long_description=long_description,
  long_description_content_type="text/markdown",
  url = 'https://github.com/svrdev27/py-inferout',
  download_url = 'https://github.com/svrdev27/py-inferout/archive/v0.0.0-alpha.0.tar.gz',
  keywords = ['distributed', 'scale', 'ML', 'models', 'serving', 'inference', 'framework'],
  #install_requires=[
  #        'aioredis>=2.0.0b1',
  #        'aiohttp>=3.7.4',
  #        'ConfigArgParse>=1.5.1'
  #    ],
  install_requires=required,
  classifiers=[
    'Development Status :: 3 - Alpha',
    'Intended Audience :: Developers',
    'Topic :: Software Development',
    'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7'
  ],
  entry_points = {
        'console_scripts': ['inferout=inferout:execute_from_command_line']
    }
)
