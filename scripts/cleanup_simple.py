# cleanup_simple.py

import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text


class DatabaseCleaner:
    def __init__(self, is_production=False):
        # Choose database connection based on environment
        if is_production:
            self.db_url = "postgresql://postgres:Guitar0123@localhost:5432/ryze"
        else:
            self.db_url = "postgresql://postgres:Guitar0123!@localhost:5432/fastapi"

        self.engine = create_engine(self.db_url)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def cleanup(self, hours=24):
        """Clean up test data older than specified hours"""
        session = self.SessionLocal()
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        try:
            # Tables in order of dependency
            tables = [
                "conversation_messages",
                "conversations",
                "request_comment_votes",
                "request_comments",
                "request_shares",
                "agreements",
                "requests",
                "videos",
                "projects",
                "developer_profiles",
                "client_profiles",
                "users",
            ]

            print(f"\nStarting cleanup of test data older than {hours} hours...")
            print(f"Database: {self.db_url}")
            print("-" * 50)

            for table in tables:
                if table == "users":
                    query = text(
                        f"""
                        DELETE FROM {table} 
                        WHERE created_at <= :cutoff_time
                        AND (email LIKE '%@example.com' 
                             OR username IN ('testclient', 'testdev'))
                        RETURNING id
                    """
                    )
                else:
                    query = text(
                        f"""
                        DELETE FROM {table} 
                        WHERE created_at <= :cutoff_time
                        RETURNING id
                    """
                    )

                result = session.execute(query, {"cutoff_time": cutoff_time})
                deleted_count = len(result.fetchall())
                print(f"Deleted {deleted_count} records from {table}")

            session.commit()
            print("-" * 50)
            print("Cleanup completed successfully!")

        except Exception as e:
            print(f"Error during cleanup: {str(e)}")
            session.rollback()
        finally:
            session.close()


if __name__ == "__main__":
    # Simple command line interface
    env = input("Which environment to clean? (local/production): ").lower()

    if env == "production":
        confirm = input("Are you sure you want to clean PRODUCTION? (yes/no): ").lower()
        if confirm != "yes":
            print("Aborting production cleanup")
            exit()

    is_production = env == "production"
    cleaner = DatabaseCleaner(is_production)

    hours = input("How many hours of test data to clean? (default 24): ")
    hours = int(hours) if hours.isdigit() else 24

    cleaner.cleanup(hours)
