import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

# Import after path setup
from app.models import Base, User, DeveloperProfile, ClientProfile, UserType
from app.database import engine, SessionLocal
from app.utils import hash_password
from faker import Faker
import random

fake = Faker()


def generate_test_data(num_users=100):
    db = SessionLocal()

    try:
        num_developers = int(num_users * 0.4)
        # Developer creation
        for _ in range(num_developers):
            name = fake.name().split()
            username = (
                name[0][0] + name[-1] + str(fake.random_int(min=100, max=999))
            ).lower()

            user = User(
                username=username,
                email=fake.email(),
                full_name=" ".join(name),
                password=hash_password("123456"),
                user_type=UserType.developer,
                terms_accepted=True,
                is_active=True,
            )
            db.add(user)
            db.flush()

            profile = DeveloperProfile(
                user_id=user.id,
                skills=", ".join(
                    random.sample(
                        [
                            "Python",
                            "JavaScript",
                            "React",
                            "Node.js",
                            "FastAPI",
                            "Machine Learning",
                            "AI Development",
                            "Data Science",
                            "Web Development",
                            "API Development",
                            "Cloud Computing",
                        ],
                        k=random.randint(3, 6),
                    )
                ),
                experience_years=random.randint(1, 15),
                bio=fake.text(max_nb_chars=200),
                is_public=True,  # All developers should be public
                rating=round(random.uniform(3.5, 5.0), 1),
                total_projects=random.randint(5, 50),
                success_rate=round(random.uniform(0.7, 1.0), 2),
            )
            db.add(profile)
            print(f"Created developer: {username}")

        # Client creation
        for _ in range(num_users - num_developers):
            name = fake.name().split()
            username = (name[0][0] + name[-1]).lower()

            user = User(
                username=username,
                email=fake.email(),
                full_name=" ".join(name),
                password=hash_password("123456"),
                user_type=UserType.client,
                terms_accepted=True,
                is_active=True,
            )
            db.add(user)
            db.flush()

            profile = ClientProfile(
                user_id=user.id,
                company_name=fake.company(),
                industry=random.choice(
                    [
                        "Technology",
                        "Finance",
                        "Healthcare",
                        "Education",
                        "E-commerce",
                        "Manufacturing",
                        "Real Estate",
                    ]
                ),
                company_size=random.choice(
                    ["1-10", "11-50", "51-200", "201-500", "500+"]
                ),
                website=fake.url(),
            )
            db.add(profile)
            print(f"Created client: {username}")

        db.commit()
        print(f"\nSuccessfully generated {num_users} users")

    except Exception as e:
        db.rollback()
        print(f"Error generating data: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    generate_test_data(100)
