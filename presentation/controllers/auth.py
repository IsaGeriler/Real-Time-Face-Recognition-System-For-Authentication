import base64
from functools import wraps
from io import BytesIO

import qrcode
from flask import render_template, request, redirect, url_for, session

from business.services import auth_service


def requires_role(role):
    # Decorator to enforce RBA (role-based access)
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if session.get('role') != role:
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return wrapped
    return decorator


def init_auth_routes(app):
    @app.route('/')
    def index():
        return redirect(url_for('login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        error = None
        # Values to pre-fill form in case of error
        form_username = ''
        form_selected_role = ''

        if request.method == 'POST':
            u = request.form.get('username', '').strip()
            p = request.form.get('password', '')
            selected_role = request.form.get('role')

            # Preserve submitted values for re-rendering form
            form_username = u
            form_selected_role = selected_role

            if not u or not p:
                error = "Username and password are required."
            elif not selected_role:
                error = "Please select a role."
            else:
                if auth_service.verify_user_credentials(u, p):
                    actual_user_role = auth_service.get_user_role(u)

                    if actual_user_role == selected_role:
                        session['username'] = u
                        session['role'] = actual_user_role  # Store the verified role
                        totp_secret = auth_service.get_totp_secret_for_user(u)

                        if totp_secret:
                            return redirect(url_for('verify_2fa'))
                        else:
                            return redirect(url_for('setup_2fa'))
                    elif actual_user_role is None:
                        # User authenticated but has no role assigned in the system
                        error = "Login failed: User has no assigned role. Please contact an administrator."
                    else:
                        # Password correct, but selected role does not match user's actual role
                        error = "Invalid credentials or role selection."  # Generic error
                else:
                    # Username/password combination is incorrect
                    error = "Invalid credentials or role selection."  # Generic error

            # If there's an error, render login page again with error and pre-filled values
            if error:
                return render_template('auth/login.html', error=error, username_value=form_username,
                                       selected_role_value=form_selected_role)

        # For GET request or if POST didn't lead to redirect/error specific render
        return render_template('auth/login.html', error=error, username_value=form_username,
                               selected_role_value=form_selected_role)

    @app.route('/verify_2fa', methods=['GET', 'POST'])
    def verify_2fa():
        error = None
        username = session.get('username')
        if not username:
            return redirect(url_for('login'))

        totp_secret = auth_service.get_totp_secret_for_user(username)
        if not totp_secret:  # Should not happen if logic is correct, but good to check
            return redirect(url_for('setup_2fa'))

        if request.method == 'POST':
            totp_code = request.form['totp_code']
            # Re-fetch secret for verification, or ensure it's securely handled if passed around
            # totp_secret = auth_service.get_totp_secret_for_user(username) # Already fetched

            if auth_service.verify_totp_code(totp_secret, totp_code):  # Use service function
                auth_service.establish_session_for_user(session['username'])
                return redirect(url_for(get_dashboard_route(session['role'])))
            else:
                error = "Invalid 2FA code"
        return render_template('auth/verify_2fa.html', error=error)

    @app.route('/setup_2fa', methods=['GET', 'POST'])
    def setup_2fa():
        username = session.get('username')
        if not username:
            return redirect(url_for('login'))

        # Check if user already has a TOTP secret; if so, they should verify, not set up.
        # This check prevents re-setup unless explicitly desired through another flow.
        existing_totp_secret = auth_service.get_totp_secret_for_user(username)
        if existing_totp_secret and 'force_setup' not in request.args:  # Add a way to force re-setup if needed
            # If user has a secret and POSTs here without 'setup' or 'verify' actions,
            # it might be a misnavigation. Redirect to verify.
            if request.method == 'GET':
                return redirect(url_for('verify_2fa'))

        if request.method == 'POST':
            if 'setup' in request.form:
                new_totp_secret = auth_service.generate_new_totp_secret()
                provisioning_uri = auth_service.get_totp_provisioning_uri(new_totp_secret, username, issuer_name="Your App")

                qr_img = qrcode.make(provisioning_uri)
                img_buffer = BytesIO()
                qr_img.save(img_buffer, 'PNG')
                img_buffer.seek(0)
                qr_code_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')

                # Pass the new_totp_secret to the template so it can be submitted with the verification code
                return render_template('auth/setup_2fa.html', username=username, qr_code=qr_code_base64,
                                       totp_secret_to_verify=new_totp_secret, show_verify_form=True, message=None)

            elif 'verify' in request.form:
                totp_secret_from_form = request.form['totp_secret']  # This is the secret generated in 'setup' step
                totp_code = request.form['totp_code']

                if auth_service.verify_totp_code(totp_secret_from_form, totp_code):
                    auth_service.establish_session_for_user(username)
                    auth_service.set_totp_secret_for_user(username, totp_secret_from_form)
                    return redirect(url_for(get_dashboard_route(session['role'])))
                else:
                    message = "Invalid verification code. Please try again."
                    # Re-render the setup page with the QR code and an error message
                    # Need to regenerate QR for the same secret
                    provisioning_uri = auth_service.get_totp_provisioning_uri(totp_secret_from_form, username, issuer_name="Your App")
                    qr_img = qrcode.make(provisioning_uri)
                    img_buffer = BytesIO()
                    qr_img.save(img_buffer, 'PNG')
                    img_buffer.seek(0)
                    qr_code_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')

                    return render_template('auth/setup_2fa.html', username=username, qr_code=qr_code_base64,
                                           totp_secret_to_verify=totp_secret_from_form, show_verify_form=True,
                                           message=message)

            elif 'skip' in request.form:
                # Skipping 2FA setup means the user will be prompted again next login
                # unless a flag is set or logic is adjusted.
                auth_service.establish_session_for_user(username)
                return redirect(url_for(get_dashboard_route(session['role'])))

        # For GET request, or if POST didn't match any actions above
        # If user has no secret, show initial setup page (button to generate QR)
        # If user has a secret (e.g. navigated back), they should be at verify_2fa or have a clear path
        if existing_totp_secret:  # Should have been redirected earlier, but handle defensively
            return redirect(url_for('verify_2fa'))

        return render_template('auth/setup_2fa.html', username=username, qr_code=None,
                               totp_secret_to_verify=None, show_verify_form=False, message=None)

    def get_dashboard_route(role):
        return {
            'Security Manager': 'manager_dashboard',
            'Security Personnel': 'dashboard',
            'Administrator': 'admin_staff'
        }.get(role, 'login')

    @app.route('/logout')
    def logout():
        username_to_logout = session.get('username')
        session.clear()
        if username_to_logout:
            auth_service.clear_session_for_user(username_to_logout)
        return redirect(url_for('login'))