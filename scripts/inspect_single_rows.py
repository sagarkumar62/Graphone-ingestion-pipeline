import sqlite3
import json

con = sqlite3.connect('pipeline.db')
cur = con.cursor()

print("==================== STARTUPS ====================")
for r in cur.execute("SELECT * FROM startups").fetchall():
    print(r)

print("\n==================== PRODUCTS ====================")
for r in cur.execute("SELECT * FROM products").fetchall():
    print(r)

print("\n==================== JOBS ====================")
for r in cur.execute("SELECT * FROM jobs").fetchall():
    print(r)
