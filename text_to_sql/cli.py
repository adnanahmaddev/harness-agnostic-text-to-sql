import sys
import os
import argparse
import json
import datetime
import decimal
import uuid

from text_to_sql.core import TextToSQL
from text_to_sql.safety import SafetyValidator

class DatabaseJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
            return obj.isoformat()
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)

def load_env():
    """Load environment variables from a local .env file in the current directory if present."""
    env_file = os.path.join(os.getcwd(), ".env")
    if os.path.isfile(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    val = val.strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    os.environ[key.strip()] = val

def main():
    load_env()
    # Define a parent parser for arguments shared by subcommands that need DB access
    db_parser = argparse.ArgumentParser(add_help=False)
    db_parser.add_argument(
        "--db-uri", "-d",
        help="Database connection URI. Can also be set via DATABASE_URL environment variable."
    )
    db_parser.add_argument(
        "--schema", "-s",
        help="Optional database schema to reflect (e.g. for SQLAlchemyAdapter)."
    )

    parser = argparse.ArgumentParser(description="Text-to-SQL DB interface.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # get-schema command
    subparsers.add_parser("get-schema", parents=[db_parser], help="Reflect database schema.")
    
    # validate command
    val_parser = subparsers.add_parser("validate", help="Validate safety rules on SQL query.")
    val_parser.add_argument("sql", help="The raw SQL query to validate.")
    
    # execute command
    exec_parser = subparsers.add_parser("execute", parents=[db_parser], help="Sanitize, validate, and run SQL query.")
    exec_parser.add_argument("sql", help="The raw SQL query to run.")
    exec_parser.add_argument("--json", action="store_true", help="Output results in raw JSON format.")
    
    args = parser.parse_args()
    
    if args.command == "get-schema":
        try:
            db_uri = args.db_uri or os.environ.get("DATABASE_URL")
            if not db_uri:
                raise ValueError("Database connection string must be provided via --db-uri or the DATABASE_URL environment variable.")
            translator = TextToSQL(db_uri=db_uri, schema=args.schema)
            schema = translator.adapter.get_schema()
            print(schema)
        except Exception as e:
            print(f"Error fetching schema: {e}", file=sys.stderr)
            sys.exit(1)
            
    elif args.command == "validate":
        validator = SafetyValidator(read_only=True)
        try:
            clean_sql = validator.validate_and_sanitize(args.sql)
            print("Validation Passed. Clean SQL:")
            print(clean_sql)
        except Exception as e:
            print(f"Validation Failed: {e}", file=sys.stderr)
            sys.exit(1)
            
    elif args.command == "execute":
        validator = SafetyValidator(read_only=True)
        try:
            # 1. Sanitize & Validate
            clean_sql = validator.validate_and_sanitize(args.sql)
        except Exception as e:
            print(f"Validation Failed: {e}", file=sys.stderr)
            sys.exit(1)
            
        try:
            # 2. Connect & Execute
            db_uri = args.db_uri or os.environ.get("DATABASE_URL")
            if not db_uri:
                raise ValueError("Database connection string must be provided via --db-uri or the DATABASE_URL environment variable.")
            translator = TextToSQL(db_uri=db_uri, schema=args.schema)
            result = translator.adapter.execute_query(clean_sql)
            
            if not result["success"]:
                print(f"Query execution failed: {result.get('error')}", file=sys.stderr)
                sys.exit(1)
                
            if args.json:
                print(json.dumps(result, indent=2, cls=DatabaseJSONEncoder))
            else:
                # Pretty print as a Markdown table
                columns = result["columns"]
                data = result["data"]
                
                if not columns:
                    print("Query executed successfully. No rows returned.")
                    return
                    
                # Header row
                header = "| " + " | ".join(columns) + " |"
                divider = "| " + " | ".join(["---"] * len(columns)) + " |"
                print(header)
                print(divider)
                
                # Data rows
                for row in data:
                    row_str = "| " + " | ".join(str(row.get(col, "")) for col in columns) + " |"
                    print(row_str)
        except Exception as e:
            print(f"Query execution error: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
