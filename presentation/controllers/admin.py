from flask import render_template, session, request, flash

from presentation.controllers.auth import requires_role
from business.services import user_service, student_service, log_service


def init_admin_routes(app):
    @app.route('/admin/staff', methods=['GET', 'POST'])
    @requires_role('Administrator')
    def admin_staff():
        message = None
        current_user = session['username']
        current_role = session['role']

        if request.method == 'POST':
            action = request.form.get('action', 'add_user')
            if action == 'add_user':
                username = request.form['username']
                password = request.form['password']
                role = request.form['role']
                user_service.add_new_user(username, password, role, current_user, current_role)
            elif action == 'delete_user':
                username = request.form['username']
                user_service.remove_user(username, current_user, current_role)
            elif action == 'change_role':
                username = request.form['username']
                new_role = request.form['new_role']
                user_service.change_user_role(username, new_role, current_user, current_role)

        # Fetch users from the database
        db_users = user_service.list_all_users()
        users_list = [
            {'username': user['username'], 'role': user['role_name'], 'can_delete': (user['username'] != current_user)}
            for user in db_users
        ]
        logs = log_service.get_application_logs(limit=20)
        return render_template('admin/admin_staff_user_management.html',
                               username=current_user,
                               role=session['role'],
                               message=message,
                               users_list=users_list,
                               logs=logs
                               )

    @app.route('/admin/students', methods=['GET', 'POST'])
    @requires_role('Administrator')
    def admin_students():
        message = None
        students = student_service.get_all_registered_students()
        if request.method == 'POST':
            student_id = request.form['student_id'].strip()
            first_name = request.form['first_name'].strip()
            middle_name = request.form.get('middle_name', '').strip()
            last_name = request.form['last_name'].strip()
            gender = request.form['gender']
            nationality = request.form['nationality'].strip()
            department = request.form['department'].strip()
            try:
                message = student_service.register_student(student_id, first_name, middle_name, last_name, gender, nationality, department, session['username'], session['role'])
            except Exception as e:
                message = f"Error adding student: {str(e)}"
        # placeholder for future student management
        return render_template('admin/admin_student_management.html',
                               username=session['username'],
                               role=session['role'],
                               message=message,
                               students=students
                               )

    @app.route('/admin/load_embeddings', methods=['GET', 'POST'])
    @requires_role('Administrator')
    def load_embeddings_route():
        message = None
        if request.method == 'POST':
            # Determine which type of embeddings to load
            # For simplicity, let's use a hidden field or a specific button name
            # Or, more explicitly from a form field if you add one
            load_type = request.form.get('load_type', 'mean')  # Default to 'mean'

            use_mean = True
            if load_type == 'all':
                use_mean = False

            try:
                # Call the modified service function
                message_from_service, stored, skipped = student_service.load_embeddings_from_file(
                    actor_username=session['username'],
                    actor_role=session['role'],
                    use_mean_embeddings=use_mean
                )
                flash(message_from_service, 'info')  # Use flash for messages
            except Exception as e:
                flash(f"Error during embedding loading: {str(e)}", 'danger')
                message_from_service = f"Error: {str(e)}"  # Also set message for direct display if needed

            return render_template('admin/load_embeddings.html',
                                   username=session['username'],
                                   role=session['role'],
                                   active_panel='load_embeddings',  # For sidebar active state
                                   message=message_from_service)  # Display message directly on page too

        # For GET request
        return render_template('admin/load_embeddings.html',
                               username=session['username'],
                               role=session['role'],
                               active_panel='load_embeddings',  # For sidebar active state
                               message=None)
