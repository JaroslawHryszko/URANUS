import json
from flask import Blueprint, request, jsonify, session
from app import db
from app.models import InteractionEvent, Session as ExpSession

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/track', methods=['POST'])
def track():
    """Receive interaction events from tracker.js."""
    session_id = session.get('exp_session_id')
    if not session_id:
        return jsonify({'status': 'no_session'}), 200

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'status': 'no_data'}), 400

    events = data.get('events', [])
    method_session_id = data.get('method_session_id') or session.get('current_method_session_id')

    for evt in events:
        event = InteractionEvent(
            session_id=session_id,
            method_session_id=method_session_id,
            timestamp=evt.get('timestamp', 0),
            event_type=evt.get('event_type', 'unknown'),
            element_id=evt.get('element_id', ''),
            element_tag=evt.get('element_tag', ''),
            element_class=evt.get('element_class', ''),
            page_url=evt.get('page_url', ''),
        )
        event.set_event_data(evt.get('event_data', {}))
        db.session.add(event)

    db.session.commit()
    return jsonify({'status': 'ok', 'count': len(events)}), 200


@api_bp.route('/session_meta', methods=['POST'])
def session_meta():
    """Receive session metadata (screen size, language, timezone, iframe detection)."""
    session_id = session.get('exp_session_id')
    if not session_id:
        return jsonify({'status': 'no_session'}), 200

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'status': 'no_data'}), 400

    exp_session = ExpSession.query.get(session_id)
    if exp_session:
        exp_session.screen_width = data.get('screen_width')
        exp_session.screen_height = data.get('screen_height')
        exp_session.language = data.get('language', '')
        exp_session.timezone = data.get('timezone', '')
        exp_session.is_iframe = data.get('is_iframe', False)
        db.session.commit()

    return jsonify({'status': 'ok'}), 200
