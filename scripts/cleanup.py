# cleanup.py

import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text
from typing import Optional


def get_database_url(env: str) -> str:
    """Get database URL based on environment"""
    if env == "local":
        return "postgresql://postgres:Guitar0123!@localhost:5432/fastapi"
    elif env == "production":
        return "postgresql://postgres:Guitar0123@localhost:5432/ryze"
    else:
        raise ValueError("Invalid environment specified")


class DatabaseCleaner:
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def cleanup_test_data(self, hours: int = 24, dry_run: bool = True):
        """
        Clean up test data older than specified hours
        Args:
            hours: Number of hours old the test data should be
            dry_run: If True, only print what would be deleted without actually deleting
        """
        session = self.SessionLocal()
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)

            # Define tables in order of dependency
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

            # Count and optionally delete test data from each table
            for table in tables:
                # For users table, only delete test users
                if table == "users":
                    query = text(
                        f"""
                        SELECT COUNT(*) 
                        FROM {table} 
                        WHERE created_at <= :cutoff_time
                        AND (email LIKE '%@example.com' 
                             OR username IN (:test_client, :test_dev))
                    """
                    )
                    delete_query = text(
                        f"""
                        DELETE FROM {table} 
                        WHERE created_at <= :cutoff_time
                        AND (email LIKE '%@example.com' 
                             OR username IN (:test_client, :test_dev))
                    """
                    )
                else:
                    query = text(
                        f"""
                        SELECT COUNT(*) 
                        FROM {table} 
                        WHERE created_at <= :cutoff_time
                    """
                    )
                    delete_query = text(
                        f"""
                        DELETE FROM {table} 
                        WHERE created_at <= :cutoff_time
                    """
                    )

                # Count records
                params = {
                    "cutoff_time": cutoff_time,
                    "test_client": "testclient",
                    "test_dev": "testdev",
                }
                count = session.execute(query, params).scalar()

                print(f"{table}: {count} records found")

                # Delete if not dry run
                if not dry_run and count > 0:
                    result = session.execute(delete_query, params)
                    session.commit()
                    print(f"Deleted {result.rowcount} records from {table}")

            if not dry_run:
                session.commit()
                print("Cleanup completed successfully")
            else:
                print("\nThis was a dry run. No data was actually deleted.")
                print("Run with --execute flag to perform actual deletion")

        except Exception as e:
            print(f"Error during cleanup: {str(e)}")
            session.rollback()
            raise
        finally:
            session.close()


def main():
    """Main function to run the cleanup script"""
    import argparse

    parser = argparse.ArgumentParser(description="Clean up test data from the database")
    parser.add_argument(
        "--env",
        choices=["local", "production"],
        required=True,
        help="Environment to clean up (local or production)",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Clean up test data older than this many hours (default: 24)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform the deletion (without this flag, it's a dry run)",
    )

    args = parser.parse_args()

    # Safety check for production
    if args.env == "production" and args.execute:
        confirm = input("Are you sure you want to delete data from PRODUCTION? (yes/no): ")
        if confirm.lower() != "yes":
            print("Aborting production cleanup")
            return

    database_url = get_database_url(args.env)
    cleaner = DatabaseCleaner(database_url)

    print(f"Running cleanup on {args.env} environment")
    print(f"Will clean up test data older than {args.hours} hours")
    print(f"Execute mode: {args.execute}")

    cleaner.cleanup_test_data(hours=args.hours, dry_run=not args.execute)


if __name__ == "__main__":
    main()
