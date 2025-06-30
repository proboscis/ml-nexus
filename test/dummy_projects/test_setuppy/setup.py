from setuptools import setup, find_packages

setup(
    name="test-setuppy",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.28.0",
        "numpy>=1.20.0",
    ],
)