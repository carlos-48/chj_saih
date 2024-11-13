from setuptools import setup, find_packages

setup(
    name="chj_saih",
    version="0.1.beta",
    packages=find_packages(),
    install_requires=["requests"],
    entry_points={
        "console_scripts": [
            "chj_saih-cli = cli:main"
        ],
    },
)
