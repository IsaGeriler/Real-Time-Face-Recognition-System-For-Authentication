import json
import os

from business.services import log_service
from config import BASE_DIR
from database import database as db_access


def register_student(student_id: str, first_name: str, middle_name: str, last_name: str, gender: str, nationality: str, department: str, actor_username: str, actor_role: str):
    if not all([student_id, first_name, last_name, gender, nationality, department]): # Added department to check
        raise ValueError("All fields (student_id, first_name, last_name, gender, nationality, department) are required.")

    db_access.add_student(student_id, first_name, middle_name, last_name, gender, nationality, department)
    db_access.record_student_registration(student_id, actor_username)
    log_service.record_event(f"Registered student {first_name} {last_name} ({student_id}) by {actor_username}", actor_role)
    return f"Successfully added student: {first_name} {last_name}"


def get_all_registered_students():
    return db_access.get_all_students()

# NEW FUNCTION
def get_student_by_id(student_id: str):
    return db_access.get_student_details_by_id(student_id)


def load_embeddings_from_file(actor_username: str, actor_role: str, use_mean_embeddings: bool = True):
    if use_mean_embeddings:
        file_name = "reduced_face_embeddings_mean.json"
        source_description = "mean"
    else:
        file_name = "raw_face_embeddings.json"  # Assuming this file exists and has all 8 per angle
        source_description = "all individual"

    file_path = os.path.join(BASE_DIR, 'persistence', 'models', file_name)
    log_message_prefix = f"Loading {source_description} embeddings from {file_name} by {actor_username}: "

    try:
        with open(file_path, 'r') as f:
            student_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        err_msg = f"{log_message_prefix}Error loading file - {e}"
        log_service.record_event(err_msg, actor_role)
        raise ValueError(err_msg)

    stored, skipped = 0, 0

    # Clear existing embeddings before loading new ones ---
    # This prevents duplicates when switching between mean and all, or reload.
    try:
        print(f"{log_message_prefix}Clearing existing student embeddings from database...")
        db_access.clear_all_student_embeddings()  # You'll need to create this DB function
        log_service.record_event(f"{log_message_prefix}Cleared existing student embeddings.", actor_role)
    except Exception as e_clear:
        err_msg = f"{log_message_prefix}Error clearing existing embeddings: {e_clear}"
        log_service.record_event(err_msg, actor_role)
        raise RuntimeError(err_msg)  # Stop if we can't clear

    for student_id, views_data in student_data.items():
        if not get_student_by_id(student_id):
            print(f"{log_message_prefix}SKIP EMBEDDINGS for {student_id}: Student not found in database.")
            log_service.record_event(f"{log_message_prefix}Skipped embeddings for non-existent student {student_id}",
                                     actor_role)
            # Crude skip count for now
            if isinstance(views_data, dict):
                for _, angle_data in views_data.items():
                    if isinstance(angle_data, list) and use_mean_embeddings == False:  # list of embeddings for 'all'
                        skipped += len(angle_data)
                    elif isinstance(angle_data,
                                    list) and use_mean_embeddings == True:  # single embedding list for 'mean'
                        skipped += 1
            continue

        if not isinstance(views_data, dict):
            print(f"{log_message_prefix}SKIP {student_id}: expected dict of views, got {type(views_data)}")
            skipped += 1
            continue

        for view_angle, angle_data in views_data.items():
            embeddings_to_store = []
            if use_mean_embeddings:
                # angle_data is a single embedding list [0.1, 0.2, ...]
                if (isinstance(angle_data, list) and len(angle_data) == 512 and
                        all(isinstance(x, (int, float)) for x in angle_data)):
                    embeddings_to_store.append(
                        {'embedding': angle_data, 'sample_index': 1})  # Use sample_index 1 for mean
                else:
                    print(f"{log_message_prefix}SKIP {student_id}/{view_angle}: Invalid mean embedding format.")
                    skipped += 1
                    continue
            else:  # use_mean_embeddings is False, so load all individual embeddings
                # angle_data should be a list of embedding lists: [[0.1,..], [0.3,...], ...]
                if isinstance(angle_data, list):
                    for idx, emb_list in enumerate(angle_data):
                        if (isinstance(emb_list, list) and len(emb_list) == 512 and
                                all(isinstance(x, (int, float)) for x in emb_list)):
                            embeddings_to_store.append({'embedding': emb_list, 'sample_index': idx + 1})
                        else:
                            print(
                                f"{log_message_prefix}SKIP {student_id}/{view_angle}/sample_{idx + 1}: Invalid individual embedding format.")
                            skipped += 1  # Count this specific skipped embedding
                else:
                    print(
                        f"{log_message_prefix}SKIP {student_id}/{view_angle}: Expected list of embeddings, got {type(angle_data)}.")
                    # Crude skip count for now if format is unexpected
                    if isinstance(angle_data, dict):
                        skipped += len(angle_data.get("embedding", []))
                    else:
                        skipped += 1
                    continue

            # Now iterate through embeddings_to_store (either 1 for mean, or up to 8 for all)
            for emb_item in embeddings_to_store:
                embedding_list = emb_item['embedding']
                sample_idx = emb_item['sample_index']

                # Coerce to floats (already checked for type, but good to be sure)
                try:
                    emb_floats = [float(x) for x in embedding_list]
                except ValueError:
                    print(
                        f"{log_message_prefix}SKIP {student_id}/{view_angle}/sample_{sample_idx}: Non-numeric in embedding.")
                    skipped += 1
                    continue

                # Store into DB
                try:
                    # Pass sample_idx to store_student_embedding
                    db_access.store_student_embedding(student_id, view_angle, emb_floats, sample_idx)
                    stored += 1
                except Exception as e:
                    print(f"{log_message_prefix}ERR {student_id}/{view_angle}/sample_{sample_idx}: DB error {e}")
                    log_service.record_event(
                        f"{log_message_prefix}DB error storing embedding for {student_id}/{view_angle}/sample_{sample_idx}: {e}",
                        actor_role)
                    skipped += 1

    final_message = f"{log_message_prefix}Loaded {stored} embeddings; skipped {skipped} entries."
    log_service.record_event(final_message, actor_role)
    return final_message, stored, skipped