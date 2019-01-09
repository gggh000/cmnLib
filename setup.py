from setuptools import setup

def readme():
    with open('README.rst') as f:
        return f.read()

setup(name='cmnLib',
      version='1.0.5',
      description='The cmnLib - is all of my personal python shell libraries for pypi later for dissection',
      url='https://bitbucket.org/guengn/cmnLib/src',
      author='Guyen Gankhuyag',
      author_email='guyen800@protonmail.com',
      license='MIT',
      packages=['cmnLib'],
      install_requires=['pexpect', 'pycrypto'],
      zip_safe=False)

