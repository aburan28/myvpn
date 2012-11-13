from setuptools import setup, find_packages
import sys, os

version = "0.1"

setup(name='myvpn',
      version=version,
      description='',
      long_description="",
      classifiers=[], # Get strings from http://bit.ly/tYt3j
      keywords='',
      author="Qiangning Hong",
      author_email="hognqn@gmail.com",
      url="",
      license='',
      packages=find_packages(exclude=['ez_setup', 'examples*', 'tests*']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
      ],
      entry_points="""
      [console_scripts]
      myvpn = myvpn.vpn:main
      """,
      tests_require=['nose'],
      test_suite='nose.collector',
)
