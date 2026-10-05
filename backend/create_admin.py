"""Provision an Admin locally; never expose an Admin registration API."""
import getpass
from app import get_connection, EMAIL_PATTERN
from werkzeug.security import generate_password_hash

if __name__ == '__main__':
    name = input('Admin full name: ').strip()
    email = input('Admin email: ').strip().lower()
    password = getpass.getpass('Password (12–128 characters): ')
    if not 2 <= len(name) <= 80 or len(email) > 254 or not EMAIL_PATTERN.fullmatch(email) or not 12 <= len(password) <= 128:
        raise SystemExit('Invalid name, email, or password.')
    connection = get_connection()
    try:
        with connection:
            connection.execute("INSERT INTO users (name,email,password_hash,role) VALUES (?,?,?,'admin')", (name, email, generate_password_hash(password, method='scrypt')))
        print('Admin created. Sign in using the normal login page.')
    finally:
        connection.close()
