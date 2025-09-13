import sqlite3

conn = sqlite3.connect("../manu.db")

cursor = conn.cursor()

cursor.execute("UPDATE robots SET voice = ? WHERE id = '77a2ca9f-b7b0-46cb-b732-3cf011b0a867'", ("bN1bDXgDIGX5lw0rtY2B",))

conn.commit()
