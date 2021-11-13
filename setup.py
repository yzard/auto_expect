from setuptools import setup

from auto_expect.about import __version__

setup(
    name="auto_expect",
    version=__version__,
    packages=["auto_expect"],
    url="",
    install_requies=["pexpect"],
    console_scripts=["autoexpect = auto_expect.entry_point.py:main"],
    license="MIT",
    author="Zhuo Yin",
    author_email="zhuoyin@gmail.com",
    description="Script Language To Automate Expect",
)
