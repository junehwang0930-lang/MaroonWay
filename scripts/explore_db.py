from contextlib import closing
import sqlite3
from pathlib import Path

# 1. Connect to our database
with closing(sqlite3.connect(Path(__file__).resolve().parents[1] / "data" / "maroonway.db")) as connection:

    # 2. Write an SQL query
    query = """
    SELECT subject, COUNT(*)
    FROM grade_sections
    GROUP BY subject;
    """

    # 3. Execute the query
    cursor = connection.execute(query)

    # 4. Display the results
    for row in cursor:
        print(row)

    # 5. Close the connection
