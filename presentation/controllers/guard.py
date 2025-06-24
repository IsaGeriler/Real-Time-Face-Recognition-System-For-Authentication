from flask import render_template, session, jsonify, redirect, url_for, flash  # Ensure flash, redirect, url_for are imported
from presentation.controllers.auth import requires_role
from business.services import log_service  # You'll use this to record the new event


def init_guard_routes(app):
    @app.route('/dashboard')
    @requires_role('Security Personnel')
    def dashboard():
        logs = log_service.get_application_logs(limit=None)
        has_unknown = False
        if logs:
            for log_entry in logs:
                if "Unknown" in log_entry.get('event', ''):
                    has_unknown = True
                    break
        return render_template('guard/guard_dashboard.html',
                               username=session['username'],
                               role=session['role'],
                               logs=logs,
                               has_unknown=has_unknown
                               )

    @app.route('/api/logs')
    @requires_role('Security Personnel')
    def api_get_logs():
        logs_data = log_service.get_application_logs(limit=None)
        formatted_logs = []
        if logs_data:
            for log_entry in logs_data:
                if isinstance(log_entry, dict) and 'timestamp' in log_entry:
                    ts = log_entry['timestamp']
                    ts_str = ts.strftime('%Y-%m-%d %H:%M %Z') if hasattr(ts, 'strftime') else str(ts)
                    formatted_logs.append({
                        "timestamp": ts_str,
                        "event": log_entry.get('event', 'N/A'),
                        "role": log_entry.get('role', 'N/A')
                    })
        return jsonify(formatted_logs)

    # Simplest Manual Action Logging
    @app.route('/verify_unrecognized_person',
               methods=['GET'])  # Or POST if you prefer, link in template would need to be a form
    @requires_role('Security Personnel')
    def verify_unrecognized():
        actor_username = session.get('username', 'System')  # Get current user
        actor_role = session.get('role', 'Security Personnel')  # Get current user's role

        log_message = f"Manual Verification: Personnel '{actor_username}' confirmed an unrecognized person's entry."
        log_service.record_event(log_message, actor_role)  # student_id will be NULL

        flash("Unrecognized person's entry manually recorded as verified. Event logged.", "success")
        return redirect(url_for('dashboard'))  # Or whatever endpoint 'dashboard' is for guard

    @app.route('/reject_unrecognized_person', methods=['POST'])
    @requires_role('Security Personnel')
    def reject_unrecognized():
        actor_username = session.get('username', 'System')  # Get current user
        actor_role = session.get('role', 'Security Personnel')  # Get current user's role

        log_message = f"Manual Rejection: Personnel '{actor_username}' denied an unrecognized person's entry."
        log_service.record_event(log_message, actor_role)  # student_id will be NULL

        flash("Unrecognized person's entry manually recorded as rejected. Event logged.", "warning")
        return redirect(url_for('dashboard'))  # Or whatever endpoint 'dashboard' is for guard