"""Setup script for PyChronicle Time-Travel Debugger."""

from setuptools import setup, find_packages

setup(
    name="pychronicle",
    version="1.0.0",
    description="AST-Powered Time-Travel Debugger for Python",
    long_description=open("README.md", encoding="utf-8").read() if open("README.md", "r") else "",
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "click>=8.0.0",
        "rich>=12.0.0",
        "textual>=0.40.0",
    ],
    extras_require={
        "dev": ["pytest>=7.0.0", "anyio>=3.7.0"],
    },
    entry_points={
        "console_scripts": [
            "pychronicle=pychronicle.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Debuggers",
        "Topic :: Software Development :: Quality Assurance",
    ],
)
