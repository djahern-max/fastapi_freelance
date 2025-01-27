import sys
from pathlib import Path
from faker import Faker
import random
from datetime import datetime, timedelta

project_root = str(Path(__file__).parent)
sys.path.append(project_root)

from app.models import Project, Request, User, RequestStatus
from app.database import SessionLocal

fake = Faker()


def generate_project_data():
    db = SessionLocal()
    try:
        # Get all client users
        clients = db.query(User).filter(User.user_type == "client").all()

        for client in clients:
            # Create 1-3 projects per client
            num_projects = random.randint(1, 3)
            for _ in range(num_projects):
                project = Project(
                    name=fake.catch_phrase(),
                    description=fake.text(max_nb_chars=200),
                    user_id=client.id,
                    is_active=random.choice(
                        [True, True, False]
                    ),  # 2/3 chance of being active
                    created_at=fake.date_time_between(start_date="-1y"),
                )
                db.add(project)
                db.flush()

                # Create 2-5 requests per project
                num_requests = random.randint(2, 5)
                for _ in range(num_requests):
                    status = random.choice(list(RequestStatus))
                    request = Request(
                        title=fake.sentence(),
                        content=fake.text(max_nb_chars=500),
                        user_id=client.id,
                        project_id=project.id,
                        status=status,
                        is_public=random.choice([True, False]),
                        estimated_budget=random.randint(500, 5000),
                        created_at=fake.date_time_between(start_date="-1y"),
                    )
                    db.add(request)

        db.commit()
        print("Successfully generated projects and requests")

    except Exception as e:
        db.rollback()
        print(f"Error: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    generate_project_data()
