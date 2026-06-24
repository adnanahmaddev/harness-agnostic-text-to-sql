# Harness-Agnostic Text-to-SQL

Developed as part of my portfolio at [adnanahmad.dev](https://adnanahmad.dev).

A production-grade, IDE/agent-harness agnostic, and database-agnostic Python library that translates natural language queries into safe SQL statements and executes them against a database.

## Features

- **Database/IDE-Agnostic**: Works out of the box with standard SQLite databases and any major database supported by SQLAlchemy (including MS SQL Server, PostgreSQL, MySQL, Oracle, etc.) by simply providing a connection string. No hardcoded credentials or specific IDE environment setup required.
- **Model-Agnostic**: Decouples prompt formulation from specific LLM vendors (OpenAI, Gemini, Anthropic, etc.). You simply pass a callback function that handles the model text completion.
- **Strict Safety Layer**: Enforces query rules (such as read-only SELECT constraints), sanitizes markdown blocks, scrubs comments, and protects against DDL/DML injection keywords (e.g. `DROP`, `DELETE`, `UPDATE`, `ALTER`).

---

## Installation

You can install the stable release directly from [PyPI](https://pypi.org/project/harness-agnostic-text-to-sql/):

```bash
# Standard install (SQLite, standard SQLAlchemy, etc.)
pip install harness-agnostic-text-to-sql

# Install with Azure Active Directory and pyodbc dependencies
pip install harness-agnostic-text-to-sql[azure]
```

For local development or installing from source:

```bash
# Clone the repository
git clone https://github.com/adnanahmaddev/model-agnostic-text-to-sql.git
cd model-agnostic-text-to-sql

# Install in editable mode
pip install -e .
```

---

## Getting Started

### 1. Basic SQLite Example (Direct DB Connection String)

```python
import sqlite3
from text_to_sql import TextToSQL

# Initialize a demo database
conn = sqlite3.connect("demo.db")
conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, role TEXT);")
conn.execute("INSERT INTO users VALUES (1, 'Alice', 'Admin'), (2, 'Bob', 'User');")
conn.commit()
conn.close()

# 1. Define your custom LLM callback
def gemini_or_openai_callback(prompt: str) -> str:
    # Connect to your preferred model SDK here (e.g. Gemini, OpenAI, Claude)
    # response = client.generate_content(prompt)
    # return response.text
    return "SELECT name FROM users WHERE role = 'Admin';"

# 2. Instantiate TextToSQL with connection string and query
translator = TextToSQL(db_uri="sqlite:///demo.db", llm_callback=gemini_or_openai_callback)

result = translator.query("Get the names of all admin users")
print(result)
# Output:
# {
#     'success': True,
#     'sql': 'SELECT name FROM users WHERE role = \'Admin\';',
#     'columns': ['name'],
#     'data': [{'name': 'Alice'}]
# }
```

### 2. Live Database Connection Example (SQLAlchemy URI)

You can pass any SQLAlchemy database connection string (e.g., PostgreSQL, MS SQL, MySQL):

```python
from text_to_sql import TextToSQL

# 1. Define LLM callback
def llm_callback(prompt: str) -> str:
    return "SELECT TOP 3 * FROM awo.Asset;"

# 2. Connect directly via DB URI (e.g. MS SQL Server)
# Specify target schema using the 'schema' parameter
translator = TextToSQL(
    db_uri="mssql+pyodbc:///?odbc_connect=DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=testdb;UID=sa;PWD=password;",
    schema="awo",
    llm_callback=llm_callback
)

result = translator.query("Get first 3 assets")
result = translator.query("Get first 3 assets")
print(result)
```

### 3. Database connection string configuration via CLI or `.env`

For command-line interface (CLI) execution, the connection string can be provided in three ways:
1. **Explicit command argument**: `--db-uri "your_connection_string"`
2. **Environment Variable**: `DATABASE_URL` set in your shell environment.
3. **Local `.env` File**: A `DATABASE_URL` variable set inside a `.env` file in the current working directory. The tool will automatically look for and load a `.env` file when executed.

---

## Security & Safety

The `SafetyValidator` intercepts query executions and validates safety constraints:

- By default, it operates in `read_only=True` mode, blocking any modification queries (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `REPLACE`, `GRANT`, `REVOKE`, `SCHEMA`, `RENAME`).
- Regular expression keyword validation uses word boundaries (`\b`) to ensure column names containing keywords (e.g. `created_at` or `update_flag`) are not false-positives.
- Comments (single-line `--` and multi-line `/* */`) are cleaned from the returned statement, and searched for keywords to prevent injection bypasses.

---

## Running Tests

Tests are written using `pytest`. To run the test suite:

```bash
# Install test requirements
pip install -e ".[test]"

# Execute tests
PYTHONPATH=. pytest -v
```

---

## Antigravity Agent Plugin Integration

This repository includes a custom **Plugin & Skill** wrapper for Antigravity-supported IDE environments.

### 1. Global Installation (IDE-wide)
To expose this skill to all local workspace agents globally:
1. Clone this repository:
   ```bash
   git clone https://github.com/adnanahmaddev/model-agnostic-text-to-sql.git
   ```
2. Copy or symlink the `plugins/text-to-sql-plugin` directory to your local configuration folder:
   ```bash
   ln -s "$(pwd)/plugins/text-to-sql-plugin" ~/.gemini/config/plugins/text-to-sql-plugin
   ```

### 2. Repository-level Installation (Recommended for Teams)
If you want to commit the skill configuration directly into your project repository:
1. Create a directory `.agents/skills/text-to-sql/` inside your target project repository.
2. Download or copy the [SKILL.md](plugins/text-to-sql-plugin/skills/text-to-sql/SKILL.md) file directly into that directory:
   ```bash
   mkdir -p .agents/skills/text-to-sql
   curl -o .agents/skills/text-to-sql/SKILL.md https://raw.githubusercontent.com/adnanahmaddev/harness-agnostic-text-to-sql/main/plugins/text-to-sql-plugin/skills/text-to-sql/SKILL.md
   ```
3. Register it in your repository's local `AGENTS.md` file:
   ```markdown
   | Skill | Path | When To Use |
   |---|---|---|
   | `text-to-sql` | `.agents/skills/text-to-sql/` | Translate natural language queries into SQL and query the database |
   ```
