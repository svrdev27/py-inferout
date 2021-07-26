from distutils.core import setup
from setuptools import find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
  name = 'inferout',
  packages = find_packages(),
  version = '0.0.0a2',
  license='GPLv3',
  description = 'Distributed Scale Out Framework for ML models serving/inference',
  long_description=long_description,
  long_description_content_type="text/markdown",
  url = 'https://github.com/svrdev27/py-inferout',
  download_url = 'https://github.com/svrdev27/py-inferout/archive/v0.0.0-alpha.0.tar.gz',
  keywords = ['distributed', 'scale', 'ML', 'models', 'serving', 'inference', 'framework'],
  install_requires=[
          'aioredis>=2.0.0b1',
          'aiohttp>=3.7.4',
          'ConfigArgParse>=1.5.1'
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
