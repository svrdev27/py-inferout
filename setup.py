from distutils.core import setup
from setuptools import find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
  name = 'inferout',
  packages = find_packages(),
  version = '0.0.0a0',
  license='GPLv3',
  description = 'Distributed Scale Out Framework for ML models serving/inference',
  long_description=long_description,
  long_description_content_type="text/markdown",
  url = 'https://github.com/svrdev27/py-inferout',
  download_url = 'https://github.com/svrdev27/py-inferout/archive/v0.0.0-alpha.0.tar.gz',
  keywords = ['distributed', 'scale', 'ML', 'models', 'serving', 'inference', 'framework'],
  install_requires=[
          'aioredis',
          'aiohttp',
          'ConfigArgParse'
      ],
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
