import io
from datetime import datetime, timezone, date as py_date  # MODIFIED: Added py_date
from flask import render_template, session, request, Response, flash  # flash if not already imported
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from presentation.controllers.auth import requires_role
from business.services import log_service  # log_service used for new features


def init_manager_routes(app):
    @app.route('/manager/dashboard')
    @requires_role('Security Manager')
    def manager_dashboard():
        logs = log_service.get_application_logs(limit=None)
        recognized_count = 0
        unknown_count = 0  # For "Unknown face"
        noface_count = 0  # For "No face in crop" or similar

        temp_fails = []  # For "Unknown face" events
        for row in logs:
            event_lower = row.get('event', '').lower()
            if event_lower.startswith('recognized student'):  # More specific
                recognized_count += 1
            elif event_lower.startswith('unknown face detected'):  # More specific
                unknown_count += 1
                ts_val = row.get('timestamp')
                ts_dt = ts_val if isinstance(ts_val, datetime) else None
                if isinstance(ts_val, str):
                    try:
                        ts_dt = datetime.fromisoformat(ts_val)
                    except ValueError:
                        pass
                if ts_dt and (ts_dt.tzinfo is None or ts_dt.tzinfo.utcoffset(ts_dt) is None):
                    ts_dt = ts_dt.replace(tzinfo=timezone.utc)
                temp_fails.append({'timestamp': ts_dt, 'event': row.get('event'), 'role': row.get('role')})
            elif event_lower.startswith('no face in crop'):  # Example for another category
                noface_count += 1

        temp_fails_sorted = sorted(
            [f for f in temp_fails if f['timestamp'] is not None],
            key=lambda x: x['timestamp'],
            reverse=True
        )
        last_10_unknown_face = temp_fails_sorted[:10]  # Renamed for clarity

        # --- NEW: Data for "Today's Student Entries" ---
        today = py_date.today()
        todays_entries_raw = log_service.get_detailed_student_entries(today)

        todays_recognized_students_list = []
        # Filter for unique students today, keeping first entry time.
        # The log_service.get_detailed_student_entries already returns data ordered by timestamp desc
        # So, if we iterate and add, the first one encountered for a student_id (if we reverse)
        # or the last one (if we don't reverse) can be chosen.
        # For "first seen today", we might need to query ASC or process the list.
        # Let's assume get_detailed_student_entries gives us all entries, we can list them
        # or pick the earliest timestamp per student for a "first seen" summary.

        # For a simple list of entries today:
        todays_entries_list_for_display = todays_entries_raw

        # For department summary today:
        department_counts_today = {}
        unique_students_today_for_dept_count = set()  # To count each student once for department summary
        for entry in todays_entries_raw:
            if entry['student_id'] not in unique_students_today_for_dept_count:
                dept = entry['department']
                department_counts_today[dept] = department_counts_today.get(dept, 0) + 1
                unique_students_today_for_dept_count.add(entry['student_id'])

        today_formatted_string = today.strftime("%Y-%m-%d")

        return render_template('manager/manager_dashboard.html',
                               username=session['username'],
                               role=session['role'],
                               recognized_count=recognized_count,
                               unknown_count=unknown_count,  # For "Unknown Face"
                               last_10_unknown_face=last_10_unknown_face,
                               active_page='dashboard',
                               todays_entries_list=todays_entries_list_for_display,  # NEW
                               department_summary_today=department_counts_today,  # NEW
                               today_date_str = today_formatted_string
                               )

    @app.route('/manager/logs')
    @requires_role('Security Manager')
    def manager_authentication_logs():
        logs_data = log_service.get_application_logs(limit=None)
        processed_logs = []
        for log_entry in logs_data:
            ts_val = log_entry.get('timestamp')
            ts_dt = ts_val if isinstance(ts_val, datetime) else None
            if isinstance(ts_val, str):
                try:
                    ts_dt = datetime.fromisoformat(ts_val)
                except ValueError:
                    pass
            if ts_dt and (ts_dt.tzinfo is None or ts_dt.tzinfo.utcoffset(ts_dt) is None):
                ts_dt = ts_dt.replace(tzinfo=timezone.utc)  # Standardize to UTC
            processed_logs.append({
                'timestamp': ts_dt,
                'event': log_entry.get('event'),
                'role': log_entry.get('role')
            })
        return render_template('manager/manager_authentication_logs.html',
                               username=session['username'],
                               role=session['role'],
                               logs=processed_logs,
                               active_page='logs')

    @app.route('/manager/personnel')
    @requires_role('Security Manager')
    def manager_security_personnel_monitoring():
        all_logs = log_service.get_application_logs(limit=None)
        personnel_logs = []
        for row in all_logs:
            if row.get('role') == 'Security Personnel':
                ts_val = row.get('timestamp')
                ts_dt = ts_val if isinstance(ts_val, datetime) else None
                if isinstance(ts_val, str):
                    try:
                        ts_dt = datetime.fromisoformat(ts_val)
                    except ValueError:
                        pass
                if ts_dt and (ts_dt.tzinfo is None or ts_dt.tzinfo.utcoffset(ts_dt) is None):
                    ts_dt = ts_dt.replace(tzinfo=timezone.utc)
                personnel_logs.append({'timestamp': ts_dt, 'event': row.get('event'), 'role': row.get('role')})
        return render_template('manager/manager_security_personnel_monitoring.html',
                               username=session['username'],
                               role=session['role'],
                               logs=personnel_logs,
                               active_page='personnel')

    # --- NEW ROUTE for Student Entries Report ---
    @app.route('/manager/student_entries_report', methods=['GET'])
    @requires_role('Security Manager')
    def manager_student_entries_report():
        report_date_str = request.args.get('report_date')
        target_date_obj = None

        if report_date_str:
            try:
                target_date_obj = datetime.strptime(report_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash("Invalid date format. Displaying entries for today.", "warning")
                target_date_obj = py_date.today()
        else:
            target_date_obj = py_date.today()  # Default to today

        student_entries = log_service.get_detailed_student_entries(target_date_obj)

        return render_template('manager/manager_student_entries_report.html',
                               username=session['username'],
                               role=session['role'],
                               student_entries=student_entries,
                               report_date_str=target_date_obj.isoformat(),  # For pre-filling date picker
                               active_page='student_entries')

    @app.route('/manager/reports')
    @requires_role('Security Manager')
    def manager_reports_analysis():
        report_date_str = request.args.get('report_date')
        chart_type = request.args.get('chart_type', 'bar')
        target_date_obj = None

        if report_date_str:
            try:
                target_date_obj = datetime.strptime(report_date_str, '%Y-%m-%d').date()  # Use strptime
            except ValueError:
                flash(f"Invalid date format: '{report_date_str}'. Please use YYYY-MM-DD.", "danger")

        raw_logs = log_service.get_application_logs(limit=None)
        filtered_data = []
        for log_entry in raw_logs:
            timestamp_val = log_entry.get('timestamp')
            log_datetime_obj = None
            if isinstance(timestamp_val, datetime):
                log_datetime_obj = timestamp_val
            elif isinstance(timestamp_val, str):
                try:
                    log_datetime_obj = datetime.fromisoformat(timestamp_val)
                except ValueError:
                    continue
            else:
                continue

            if log_datetime_obj.tzinfo is None or log_datetime_obj.tzinfo.utcoffset(log_datetime_obj) is None:
                log_datetime_obj = log_datetime_obj.replace(tzinfo=timezone.utc)

            if target_date_obj:
                if log_datetime_obj.date() == target_date_obj:
                    filtered_data.append(log_entry)  # Append original log_entry
            else:  # All time
                filtered_data.append(log_entry)

        recognized_count = sum(
            1 for log in filtered_data if log.get('event', '').lower().startswith('recognized student'))
        unknown_count = sum(1 for log in filtered_data if log.get('event', '').lower().startswith('unknown face'))

        return render_template('manager/manager_reports_analysis.html',
                               username=session['username'],
                               role=session['role'],
                               recognized_count=recognized_count,
                               unknown_count=unknown_count,
                               report_date=report_date_str,
                               chart_type=chart_type,
                               active_page='reports')

    @app.route('/manager/reports/export', methods=['POST'])
    @requires_role('Security Manager')
    def manager_reports_export():
        date_str = request.form.get('report_date')
        export_format = request.form.get('export_format')  # chart_type for PDF is also in form

        if not date_str:
            flash("Date is required for export.", "danger")
            return "Date is required for export.", 400

        target_date_obj = None
        try:
            target_date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()  # Use strptime
        except ValueError:
            flash(f"Invalid date format for export: '{date_str}'.", "danger")
            return "Invalid date format for export.", 400

        # Fetch logs for the specific date for export
        # Re-using the general log fetching might be too broad for export.
        # Better to fetch specific "Recognized" and "Unknown" counts for that day.

        # This part should ideally use the same filtering as manager_reports_analysis if counts are needed for PDF
        raw_logs = log_service.get_application_logs(limit=None)  # Could be refined
        filtered_data_for_export = []
        for log_entry in raw_logs:  # Same filtering as manager_reports_analysis
            timestamp_val = log_entry.get('timestamp')
            log_datetime_obj = None
            if isinstance(timestamp_val, datetime):
                log_datetime_obj = timestamp_val
            elif isinstance(timestamp_val, str):
                try:
                    log_datetime_obj = datetime.fromisoformat(timestamp_val)
                except ValueError:
                    continue
            else:
                continue
            if log_datetime_obj.tzinfo is None or log_datetime_obj.tzinfo.utcoffset(log_datetime_obj) is None:
                log_datetime_obj = log_datetime_obj.replace(tzinfo=timezone.utc)
            if log_datetime_obj.date() == target_date_obj:
                filtered_data_for_export.append(log_entry)

        if export_format == 'csv':
            # Exporting detailed student entries might be more useful here
            student_entries_for_export = log_service.get_detailed_student_entries(target_date_obj)
            string_io = io.StringIO()
            # CSV headers for student entries
            string_io.write('Timestamp,Student ID,Full Name,Department,Event Description\n')
            for entry in student_entries_for_export:
                ts_str = entry['timestamp'].isoformat() if isinstance(entry.get('timestamp'), datetime) else 'N/A'
                sid_str = entry.get('student_id', 'N/A')
                name_str = entry.get('full_name', 'N/A')
                dept_str = entry.get('department', 'N/A')
                event_str = entry.get('event_description', 'N/A').replace('"', '""')  # Basic CSV escaping for event
                string_io.write(f'"{ts_str}","{sid_str}","{name_str}","{dept_str}","{event_str}"\n')

            csv_data = string_io.getvalue().encode('utf-8')
            string_io.close()
            return Response(csv_data,
                            mimetype='text/csv',
                            headers={
                                'Content-Disposition': f'attachment; filename="student_entries_report_{date_str}.csv"'})

        elif export_format == 'pdf':
            # PDF for general summary counts (recognized/unknown) as before
            recognized_count_pdf = sum(
                1 for log in filtered_data_for_export if log.get('event', '').lower().startswith('recognized student'))
            unknown_count_pdf = sum(
                1 for log in filtered_data_for_export if log.get('event', '').lower().startswith('unknown face'))

            bytes_io = io.BytesIO()
            pdf = canvas.Canvas(bytes_io, pagesize=letter)
            pdf.setTitle(f"Authentication Summary Report {date_str}")
            page_width, page_height = letter
            margin = 50
            current_y = page_height - margin

            pdf.setFont('Helvetica-Bold', 16)
            pdf.drawCentredString(page_width / 2, current_y, f"Authentication Summary: {date_str}")
            current_y -= 30
            pdf.setFont('Helvetica', 12)
            pdf.drawString(margin, current_y, f"Recognized Student Count: {recognized_count_pdf}")
            current_y -= 20
            pdf.drawString(margin, current_y, f"Unknown Face Count: {unknown_count_pdf}")
            current_y -= 30

            # (Simplified Bar Chart as in original code)
            if recognized_count_pdf > 0 or unknown_count_pdf > 0:
                pdf.setFont('Helvetica-Bold', 12)
                pdf.drawString(margin, current_y, "Summary Chart:")
                current_y -= 20
                chart_x_start, bar_max_width, bar_height, label_offset_x = margin + 100, page_width - (
                            margin + 100) - margin - 50, 20, -95
                max_val = max(recognized_count_pdf, unknown_count_pdf, 1)

                pdf.setFillColorRGB(0.3, 0.7, 0.3);
                bar_width_rec = (recognized_count_pdf / max_val) * bar_max_width
                pdf.rect(chart_x_start, current_y, bar_width_rec, bar_height, fill=1, stroke=0)
                pdf.setFillColorRGB(0, 0, 0);
                pdf.drawString(chart_x_start + label_offset_x, current_y + 5, "Recognized:");
                pdf.drawString(chart_x_start + bar_width_rec + 5, current_y + 5, str(recognized_count_pdf))
                current_y -= (bar_height + 10)
                pdf.setFillColorRGB(0.9, 0.3, 0.3);
                bar_width_unk = (unknown_count_pdf / max_val) * bar_max_width
                pdf.rect(chart_x_start, current_y, bar_width_unk, bar_height, fill=1, stroke=0)
                pdf.setFillColorRGB(0, 0, 0);
                pdf.drawString(chart_x_start + label_offset_x, current_y + 5, "Unknown Face:");
                pdf.drawString(chart_x_start + bar_width_unk + 5, current_y + 5, str(unknown_count_pdf))

            pdf.showPage()
            pdf.save()
            pdf_data = bytes_io.getvalue()
            bytes_io.close()
            return Response(pdf_data,
                            mimetype='application/pdf',
                            headers={
                                'Content-Disposition': f'attachment; filename="auth_summary_report_{date_str}.pdf"'})
        else:
            flash("Invalid export format selected.", "danger")
            return "Invalid export format", 400