from setuptools import setup, find_packages

setup(
    name="log-tail-aggregator",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click>=8.0.0",
        "pytest>=7.0.0",
        "pyyaml>=6.0",
        "python-dateutil>=2.8.0",
    ],
    entry_points="""
        [console_scripts]
        logtail=logtail.cli:main
    """,
    python_requires=">=3.7",
)
