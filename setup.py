"""Package setup for cf-migrator."""

from setuptools import setup, find_packages

from cf_migrator import __version__

setup(
    name="cf-migrator",
    version=__version__,
    description="Cloudflare Migration Tool — export and import zone configurations across accounts.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="dgilmore",
    python_requires=">=3.10",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "rich>=13.7.0",
        "click>=8.1.7",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "cf-migrator=cf_migrator.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
