import sqlite3
from pathlib import Path
p = Path('/home/ubuntu/strategos-backend/strategos_dev.db')
con = sqlite3.connect(str(p))
cur = con.cursor()
cur.execute("UPDATE app_users SET requested_role = role WHERE requested_role IS NULL OR requested_role = ''")
cur.execute("UPDATE app_users SET approval_status = 'approved' WHERE approval_status IS NULL OR approval_status = 'pending'")
cur.execute("UPDATE app_users SET email_verified = 1 WHERE email_verified IS NULL OR email_verified = 0")
con.commit()
cur.execute('SELECT COUNT(*) FROM app_users')
print('app_users', cur.fetchone()[0])
con.close()