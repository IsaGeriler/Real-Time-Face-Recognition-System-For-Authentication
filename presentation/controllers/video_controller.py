from flask import Blueprint, Response, session
from business.services import video_processing_service
from business.services import log_service

video_bp = Blueprint('video_routes', __name__)

@video_bp.route('/video_feed')
def video_feed_route():
    # Here check for authentication/authorization if needed
    user_role = session.get('role', 'AnonymousVideoStreamUser')
    log_service.record_event(f"Video stream accessed by {user_role}", user_role)

    def generate():
        for raw_frame_bytes in video_processing_service.generate_processed_frames():
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + raw_frame_bytes + b'\r\n')
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

def init_video_routes(app):
    app.register_blueprint(video_bp)
