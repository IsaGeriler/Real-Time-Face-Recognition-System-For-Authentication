import os

BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "COMP4902_20SOFT1034_21COMP1014")
CROPPED_IMAGES_DIR = os.path.join(os.path.dirname(BASE_DIR), "persistence", "student_data", "cropped_faces")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:[password]@localhost:[port_number]/postgres")
HAAR_CASCADE = os.path.join(BASE_DIR, "persistence", "models", "haarcascade_frontalface_default.xml")
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")
SECRET_KEY = "our-mysterious-secret-key"