from setuptools import setup, find_packages

setup(
    name="test-setuppy-project",
    version="0.1.0",
    description="Test setup.py project for ml-nexus schematics testing",
    author="Test Author",
    author_email="test@example.com",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.20.0",
        "pandas>=1.3.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "flake8>=5.0.0",
        ]
    },
    python_requires=">=3.11",
)