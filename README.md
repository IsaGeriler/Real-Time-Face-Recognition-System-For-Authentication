# Real-Time-Face-Recognition-System-For-Authentication
A secure, on-premise, contactless face recognition system designed for university student authentication, ensuring real-time performance (<5s), data privacy, and KVKK/GDPR compliance. Developed as part of a graduation project and presented via poster and thesis presentations.

# Features
Real-Time Face Detection & Recognition: Uses OpenCV Haar Cascade for CPU-efficient face detection and FaceNet embeddings for accurate identity verification.

On-Premise Deployment: All components (web server, database, ML models) run locally, ensuring full data control and legal compliance.

Web-Based Dashboard: Role-specific interfaces for Security Personnel, Managers, and Admins. Real-time log monitoring, user management, and reporting.

Secure Authentication: Passwords hashed with bcrypt, Two-Factor Authentication (TOTP via pyotp), and Role-Based Access Control (RBAC).

Efficient Similarity Search: PostgreSQL + pgvector extension to store 512‑dimensional embeddings and perform fast KNN queries (<0.7 threshold).

Asynchronous Updates & Reporting: AJAX (Fetch API) for live log updates; ReportLab for PDF report generation.

# Usage

Security Personnel: View live logs and video feed at /guard/dashboard.

Manager: Monitor system status and generate CSV/PDF reports at /manager/dashboard.

Admin: Register students, manage users, and load embeddings at /admin.

# Testing & Results

Response Time: 2.5–3.5s (<5s target)

Accuracy: ≥70% genuine pairs below threshold in 30‑student dataset

User Acceptance: All core scenarios passed (authentication, registration, RBAC)

KVKK Compliance: On‑premise data storage, informed consent, data minimization

# Acknowledgements

Prof. Dr. Mehmet Devrim Akça (Supervisor)

Volunteer students for KVKK‑consented data collection

Team members: Duygu Önder, İsa Berk Geriler
