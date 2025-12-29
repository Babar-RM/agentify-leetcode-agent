import psycopg2
import json

with open('config.json') as f:
    config = json.load(f)

with open('database_migration.sql') as f:
    sql = f.read()

conn = psycopg2.connect(config['neon_db_url'])
cursor = conn.cursor()
cursor.execute(sql)
conn.commit()
cursor.close()
conn.close()
print('✅ Database migrated')