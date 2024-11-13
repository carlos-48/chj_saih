from setuptools import setup, find_packages

setup(
    name="chj_saih",
    version="beta-0.1",
    packages=find_packages(),
    install_requires=["requests"],
    entry_points={
        "console_scripts": [
            "chj_saih-cli = cli:main"
        ],
    },
)
