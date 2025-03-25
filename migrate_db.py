import os
import asyncio
import subprocess
from dotenv import load_dotenv
from sqlalchemy import text
from utils.database import db


load_dotenv()

async def create_postgres_db():
    """Create a postgres database if it doesn't exist"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url or "postgresql" not in database_url:
        print("PostgreSQL is not configured in DATABASE_URL")
        return False
    
    # Parse the URL to get the database name, username, and password
    parts = database_url.replace("postgresql+asyncpg://", "").split("@")
    user_pass = parts[0].split(":")
    username = user_pass[0]
    password = user_pass[1]
    host_port_db = parts[1].split("/")
    host_port = host_port_db[0].split(":")
    host = host_port[0]
    port = host_port[1] if len(host_port) > 1 else "5432"
    dbname = host_port_db[1]
    
    print(f"Checking access to PostgreSQL on {host}:{port}")
    print(f"User: {username}, Database: {dbname}")
    
    # Command to check if the database exists
    check_command = [
        "psql",
        "-h", host,
        "-p", port,
        "-U", username,
        "-c", f"SELECT 1 FROM pg_database WHERE datname='{dbname}'",
        "postgres"
    ]
    
    try:
        # Set the environment variable for the password
        env = os.environ.copy()
        env["PGPASSWORD"] = password
        
        # Execute the check command
        result = subprocess.run(
            check_command,
            capture_output=True,
            text=True,
            env=env
        )
        
        if "1 row" not in result.stdout:
            # Database doesn't exist, create it
            print(f"Creating database {dbname}...")
            create_command = [
                "psql",
                "-h", host,
                "-p", port,
                "-U", username,
                "-c", f"CREATE DATABASE {dbname}",
                "postgres"
            ]
            
            create_result = subprocess.run(
                create_command,
                capture_output=True,
                text=True,
                env=env
            )
            
            if "ERROR" in create_result.stderr:
                print(f"Error creating database: {create_result.stderr}")
                return False
            
            print(f"Database {dbname} created successfully")
        else:
            print(f"Database {dbname} already exists")
        
        return True
    except Exception as e:
        print(f"Error checking/creating database: {str(e)}")
        return False

async def migrate_database():
    """Database migration - adding new columns"""
    print("Starting database migration...")
    
    # Check the database type in DATABASE_URL
    database_url = os.getenv("DATABASE_URL", "")
    
    if not database_url or database_url == "":
        print("DATABASE_URL is not set. Migration is not possible.")
        return
    
    if "postgresql" in database_url:
        # Check if the PostgreSQL database exists
        if not await create_postgres_db():
            print("Failed to prepare PostgreSQL database. Migration aborted.")
            return
        
        try:
            # Initialize the database models
            await db.init_models()
            
            # PostgreSQL migration
            async with db.engine.begin() as conn:
                # Add columns if they don't exist
                # In PostgreSQL, we need to check the existence of columns through information_schema
                print("Checking for new columns in PostgreSQL...")
                
                # Check if the full_name column exists
                exists = await conn.scalar(
                    text("""
                    SELECT EXISTS (
                        SELECT 1 
                        FROM information_schema.columns 
                        WHERE table_name='users' AND column_name='full_name'
                    )
                    """)
                )
                if not exists:
                    print("Adding full_name column...")
                    await conn.execute(text("ALTER TABLE users ADD COLUMN full_name VARCHAR"))
                
                # Check if the phone_number column exists
                exists = await conn.scalar(
                    text("""
                    SELECT EXISTS (
                        SELECT 1 
                        FROM information_schema.columns 
                        WHERE table_name='users' AND column_name='phone_number'
                    )
                    """)
                )
                if not exists:
                    print("Adding phone_number column...")
                    await conn.execute(text("ALTER TABLE users ADD COLUMN phone_number VARCHAR"))
                
                # Check if the email column exists
                exists = await conn.scalar(
                    text("""
                    SELECT EXISTS (
                        SELECT 1 
                        FROM information_schema.columns 
                        WHERE table_name='users' AND column_name='email'
                    )
                    """)
                )
                if not exists:
                    print("Adding email column...")
                    await conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR"))
                
                print("PostgreSQL migration completed successfully.")
        except Exception as e:
            print(f"Error during PostgreSQL migration: {e}")
    else:
        print(f"Unsupported database type: {database_url}")
        print("Only PostgreSQL is supported!")
    
    print("Database migration completed.")

if __name__ == "__main__":
    asyncio.run(migrate_database()) 