import sqlite3

# 1. Connect to our database
connection = sqlite3.connect("data/maroonway.db")

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
connection.close()
