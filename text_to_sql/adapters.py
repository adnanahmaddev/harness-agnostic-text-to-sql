from abc import ABC, abstractmethod
from typing import List, Dict, Any, Union
import sqlite3

class DatabaseAdapter(ABC):
    @abstractmethod
    def get_schema(self) -> str:
        """
        Extracts database schema (tables, columns, types).
        Returns a formatted schema representation suitable for the prompt.
        """
        pass

    @abstractmethod
    def execute_query(self, sql: str) -> dict:
        """
        Executes the SQL query against the database and returns a dictionary with execution results.
        Format:
        {
            "success": bool,
            "sql": str,
            "columns": List[str],      # column names (on success)
            "data": List[Dict[str, Any]], # rows as dictionary mapping column name -> value (on success)
            "error": str               # error message (on failure)
        }
        """
        pass

class SQLiteAdapter(DatabaseAdapter):
    def __init__(self, db_path: str):
        """
        Initialize SQLiteAdapter.
        
        :param db_path: Path to the SQLite database file.
        """
        self.db_path = db_path

    def get_schema(self) -> str:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            schema_lines = []
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table});")
                columns = cursor.fetchall()
                col_strings = [f"{col[1]} ({col[2]})" for col in columns]
                schema_lines.append(f"Table: {table}\nColumns: {', '.join(col_strings)}")
            return "\n\n".join(schema_lines)
        finally:
            conn.close()

    def execute_query(self, sql: str) -> dict:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            description = cursor.description
            columns = [col[0] for col in description] if description else []
            rows = [dict(row) for row in cursor.fetchall()] if description else []
            return {
                "success": True,
                "sql": sql,
                "columns": columns,
                "data": rows
            }
        except Exception as e:
            return {
                "success": False,
                "sql": sql,
                "error": str(e)
            }
        finally:
            conn.close()

try:
    from sqlalchemy import create_engine, MetaData, text
    from sqlalchemy.engine import Engine
    import re
    import urllib.parse
    import struct
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False

if HAS_SQLALCHEMY:
    def create_sql_engine(engine_or_uri: Union[Engine, str]) -> Engine:
        if not isinstance(engine_or_uri, str):
            return engine_or_uri
            
        db_uri = engine_or_uri
        connect_args = {}
        
        # 1. Check if it's a URI or a raw connection string
        if "://" not in db_uri:
            # It's a raw connection string. We will parse it and construct the mssql+pyodbc connection.
            conn_str = db_uri
            
            # Standardize parameters for pyodbc
            conn_str = re.sub(r"\bEncrypt\s*=\s*True\b", "Encrypt=yes", conn_str, flags=re.IGNORECASE)
            conn_str = re.sub(r"\bEncrypt\s*=\s*False\b", "Encrypt=no", conn_str, flags=re.IGNORECASE)
            conn_str = re.sub(r"\bTrustServerCertificate\s*=\s*True\b", "TrustServerCertificate=yes", conn_str, flags=re.IGNORECASE)
            conn_str = re.sub(r"\bTrustServerCertificate\s*=\s*False\b", "TrustServerCertificate=no", conn_str, flags=re.IGNORECASE)
            conn_str = re.sub(r"\bInitial\s+Catalog\b", "Database", conn_str, flags=re.IGNORECASE)
            
            # Detect active directory default authentication
            has_ad_default = False
            ad_pattern = r"\bAuthentication\s*=\s*(?:Active\s*Directory\s*Default|ActiveDirectoryDefault)\b;?"
            if re.search(ad_pattern, conn_str, re.IGNORECASE):
                has_ad_default = True
                conn_str = re.sub(ad_pattern, "", conn_str, flags=re.IGNORECASE)
                
            # Ensure Driver parameter is set for pyodbc
            if "driver=" not in conn_str.lower():
                driver = "ODBC Driver 17 for SQL Server"
                conn_str = f"Driver={{{driver}}};{conn_str.strip(';')}"
                
            # URL encode and build SQLAlchemy URI
            params = urllib.parse.quote_plus(conn_str.strip(';'))
            db_uri = f"mssql+pyodbc:///?odbc_connect={params}"
            
            if has_ad_default:
                try:
                    from azure.identity import DefaultAzureCredential
                    credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
                    token_obj = credential.get_token("https://database.windows.net/.default")
                    token_bytes = token_obj.token.encode("utf-16-le")
                    
                    SQL_COPT_SS_ACCESS_TOKEN = 1256
                    packed_token = struct.pack("=i", len(token_bytes)) + token_bytes
                    connect_args["attrs_before"] = {SQL_COPT_SS_ACCESS_TOKEN: packed_token}
                except ImportError:
                    raise ImportError("azure-identity package is required for Active Directory Default authentication. Please install it with 'pip install harness-agnostic-text-to-sql[azure]'.")
                    
        else:
            # It's a URI. Let's see if it has odbc_connect parameter with Authentication=Active Directory Default
            parsed_url = urllib.parse.urlparse(db_uri)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            if "odbc_connect" in query_params:
                odbc_conn_str = query_params["odbc_connect"][0]
                # Standardize parameters
                odbc_conn_str = re.sub(r"\bEncrypt\s*=\s*True\b", "Encrypt=yes", odbc_conn_str, flags=re.IGNORECASE)
                odbc_conn_str = re.sub(r"\bEncrypt\s*=\s*False\b", "Encrypt=no", odbc_conn_str, flags=re.IGNORECASE)
                odbc_conn_str = re.sub(r"\bTrustServerCertificate\s*=\s*True\b", "TrustServerCertificate=yes", odbc_conn_str, flags=re.IGNORECASE)
                odbc_conn_str = re.sub(r"\bTrustServerCertificate\s*=\s*False\b", "TrustServerCertificate=no", odbc_conn_str, flags=re.IGNORECASE)
                odbc_conn_str = re.sub(r"\bInitial\s+Catalog\b", "Database", odbc_conn_str, flags=re.IGNORECASE)
                
                has_ad_default = False
                ad_pattern = r"\bAuthentication\s*=\s*(?:Active\s*Directory\s*Default|ActiveDirectoryDefault)\b;?"
                if re.search(ad_pattern, odbc_conn_str, re.IGNORECASE):
                    has_ad_default = True
                    odbc_conn_str = re.sub(ad_pattern, "", odbc_conn_str, flags=re.IGNORECASE)
                    
                if has_ad_default:
                    try:
                        from azure.identity import DefaultAzureCredential
                        credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
                        token_obj = credential.get_token("https://database.windows.net/.default")
                        token_bytes = token_obj.token.encode("utf-16-le")
                        
                        SQL_COPT_SS_ACCESS_TOKEN = 1256
                        packed_token = struct.pack("=i", len(token_bytes)) + token_bytes
                        connect_args["attrs_before"] = {SQL_COPT_SS_ACCESS_TOKEN: packed_token}
                    except ImportError:
                        raise ImportError("azure-identity package is required for Active Directory Default authentication. Please install it with 'pip install harness-agnostic-text-to-sql[azure]'.")
                    
                    # Reconstruct query params and URL
                    query_params["odbc_connect"] = [odbc_conn_str.strip(';')]
                    new_query = urllib.parse.urlencode({k: v[0] for k, v in query_params.items()}, doseq=False)
                    parsed_url = parsed_url._replace(query=new_query)
                    db_uri = urllib.parse.urlunparse(parsed_url)
                    
        return create_engine(db_uri, connect_args=connect_args)

    class SQLAlchemyAdapter(DatabaseAdapter):
        def __init__(self, engine_or_uri: Union[Engine, str], schema: str = None):
            """
            Initialize SQLAlchemyAdapter.
            
            :param engine_or_uri: Either an active SQLAlchemy Engine instance or a connection URI string.
            :param schema: Optional database schema name to reflect.
            """
            self.engine = create_sql_engine(engine_or_uri)
            self.schema = schema

        def get_schema(self) -> str:
            metadata = MetaData()
            if self.schema:
                metadata.reflect(bind=self.engine, schema=self.schema)
            else:
                metadata.reflect(bind=self.engine)
            schema_lines = []
            for table_name, table in metadata.tables.items():
                col_strings = [f"{col.name} ({col.type})" for col in table.columns]
                schema_lines.append(f"Table: {table_name}\nColumns: {', '.join(col_strings)}")
            return "\n\n".join(schema_lines)

        def execute_query(self, sql: str) -> dict:
            try:
                with self.engine.connect() as conn:
                    result = conn.execute(text(sql))
                    if result.returns_rows:
                        columns = list(result.keys())
                        rows = [dict(row._mapping) for row in result.fetchall()]
                        return {
                            "success": True,
                            "sql": sql,
                            "columns": columns,
                            "data": rows
                        }
                    else:
                        # DDL or modification queries (if read_only = False was specified)
                        conn.commit()
                        return {
                            "success": True,
                            "sql": sql,
                            "columns": [],
                            "data": [],
                            "rowcount": result.rowcount
                        }
            except Exception as e:
                return {
                    "success": False,
                    "sql": sql,
                    "error": str(e)
                }
else:
    class SQLAlchemyAdapter(DatabaseAdapter):
        def __init__(self, engine_or_uri: Any):
            raise ImportError("SQLAlchemy is not installed. Please install it to use SQLAlchemyAdapter.")

        def get_schema(self) -> str:
            pass

        def execute_query(self, sql: str) -> dict:
            pass
