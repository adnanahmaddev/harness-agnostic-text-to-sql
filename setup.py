from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()
long_description = (here / "README.md").read_text(encoding="utf-8")

setup(
    name="harness-agnostic-text-to-sql",
    version="0.1.7",
    packages=find_packages(),
    install_requires=[
        "sqlalchemy>=2.0.0",
    ],
    extras_require={
        "test": [
            "pytest>=8.0.0",
        ],
        "azure": [
            "azure-identity>=1.12.0",
            "pyodbc>=5.0.0",
        ]
    },
    author="Adnan Ahmad",
    description="An IDE/harness-agnostic and database-agnostic Text-to-SQL Python library.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "text-to-sql-query=text_to_sql.cli:main",
        ],
    },
)
