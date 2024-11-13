from setuptools import setup, find_packages

setup(
    name="chj_saih",
    version="0.1.beta",
    author="carlos-48",
    author_email="karloselmaster@gmail.com",
    description="Interface to Confederación Hidrográfica del Júcar to get data from the Automatic Hydrologic Information Sistem (SAIH)",
    long_description="file: README.md",
    long_description_content_type="text/markdown",
    url="https://github.com/carlos-48/chj_saih",
    project_urls={
        "Bug Reports": "https://github.com/carlos-48/chj_saih/issues"
    },
    classifiers=[
        "Programming Language :: Python :: 3"
    ],
    packages=find_packages(),
    install_requires=["requests","geopy"],
    entry_points={
        "console_scripts": [
            "chj_saih-cli = cli:main"
        ],
    },
)
