from distutils.core import setup
import py2exe

setup(name='measure_latency',
      version='1.0',
      author='Andrew Straw',
      packages=['measure_latency'],
      windows=['measure_latency/measure_latency.py'], # for py2exe
      )
