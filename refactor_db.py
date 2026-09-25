import os
import glob
import re

def main():
    base_dir = "/Users/tonic/Lavori/LeadPilotPro"
    # Find all python files
    py_files = glob.glob(os.path.join(base_dir, "**/*.py"), recursive=True)
    
    for file_path in py_files:
        if "db_connector.py" in file_path or "refactor_db.py" in file_path:
            continue
            
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        original_content = content
        
        # We look for "sqlite3.connect(" and "import sqlite3"
        if "sqlite3.connect(" in content:
            # Check if db_connector is already imported
            if "import db_connector" not in content:
                # Add import right after import sqlite3 or at the top
                if "import sqlite3" in content:
                    content = content.replace("import sqlite3", "import sqlite3\nimport db_connector")
                else:
                    content = "import db_connector\n" + content
            
            # Replace sqlite3.connect(...) with db_connector.get_connection(...)
            content = content.replace("sqlite3.connect(", "db_connector.get_connection(")
            
        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Updated {file_path}")

if __name__ == "__main__":
    main()
