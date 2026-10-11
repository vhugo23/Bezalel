"""Operator-only credentials for a known pre-account v2 workspace.

No public claim/import endpoint. The operator must independently establish who
owns the exact requested user ID. Passwords are prompted, never CLI arguments.
"""
import argparse
import asyncio
import getpass
import secrets
import asyncpg
from app.v2 import auth,db


async def bind(user_id,email,password):
    credentials=auth.Credentials(email=email,password=password)
    hashed=await auth.password_work(auth.hasher.hash,credentials.password)
    async with (await db.pool()).acquire() as conn,conn.transaction():
        user=await conn.fetchrow('SELECT id,deleted_at FROM users WHERE id=$1 FOR UPDATE',user_id)
        if not user or user['deleted_at']:raise ValueError('Active workspace not found.')
        await conn.execute('INSERT INTO accounts(user_id,email,password_hash) VALUES($1,$2,$3)',user_id,credentials.email,hashed)


async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user-id',required=True)
    args=parser.parse_args()
    email=input('New account email: ')
    password=getpass.getpass('Password (at least 12 characters): ')
    confirm=getpass.getpass('Repeat password: ')
    if not secrets.compare_digest(password,confirm):raise SystemExit('Passwords did not match; nothing changed.')
    try:
        await bind(args.user_id,email,password)
        print('Account bound to the requested workspace. Sign in in the app.')
    except asyncpg.UniqueViolationError:raise SystemExit('That workspace or email already has an account; nothing changed.')
    except ValueError:raise SystemExit('Invalid credentials or inactive workspace; nothing changed.')
    finally:
        if db._pool:await db._pool.close();db._pool=None


if __name__=='__main__':asyncio.run(main())
