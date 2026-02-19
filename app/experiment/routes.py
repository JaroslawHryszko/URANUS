import uuid
import json
import random
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort

from app import db
from app.models import Experiment, Participant, Session as ExpSession, MethodSession, Risk, Method
from app.methods import get_method_handler

experiment_bp = Blueprint('experiment', __name__)


def _get_current_session():
    """Get current experiment session from Flask session."""
    session_id = session.get('exp_session_id')
    if not session_id:
        return None
    return ExpSession.query.get(session_id)


@experiment_bp.route('/')
def index():
    """Landing page — list active experiments or show single experiment."""
    experiments = Experiment.query.filter_by(is_active=True, is_template=False).all()
    if len(experiments) == 1:
        return redirect(url_for('experiment.welcome', experiment_id=experiments[0].id))
    return render_template('experiment/welcome.html', experiments=experiments, experiment=None)


@experiment_bp.route('/experiment/<int:experiment_id>')
def welcome(experiment_id):
    """Welcome page for a specific experiment."""
    experiment = Experiment.query.get_or_404(experiment_id)
    if not experiment.is_active:
        abort(404)
    return render_template('experiment/welcome.html', experiment=experiment, experiments=None)


@experiment_bp.route('/experiment/<int:experiment_id>/start', methods=['POST'])
def start(experiment_id):
    """Start the experiment — create participant and session."""
    experiment = Experiment.query.get_or_404(experiment_id)
    if not experiment.is_active:
        abort(404)

    name = request.form.get('name', '').strip()
    if not name:
        flash('Please enter your name or nickname.', 'danger')
        return redirect(url_for('experiment.welcome', experiment_id=experiment_id))

    # Create or find participant
    participant = Participant.query.filter_by(experiment_id=experiment_id, name=name).first()
    if not participant:
        participant = Participant(
            experiment_id=experiment_id,
            uuid=str(uuid.uuid4()),
            name=name,
        )
        db.session.add(participant)
        db.session.flush()

    # Create experiment session
    exp_session = ExpSession(
        participant_id=participant.id,
        experiment_id=experiment_id,
        user_agent=request.headers.get('User-Agent', ''),
        ip_address=request.remote_addr or '',
        referrer=request.referrer or '',
    )
    db.session.add(exp_session)
    db.session.flush()

    # Assign methods
    active_methods = experiment.get_active_methods()
    mode = experiment.method_assignment_mode

    if mode == 'random':
        n = experiment.methods_per_participant or len(active_methods)
        selected = random.sample(active_methods, min(n, len(active_methods)))
        random.shuffle(selected)
    elif mode == 'fixed':
        order = experiment.get_method_order()
        if order:
            method_map = {m.id: m for m in active_methods}
            selected = [method_map[mid] for mid in order if mid in method_map]
        else:
            selected = active_methods
    else:
        # participant_choice — will be handled in method_choice view
        selected = []

    # Create method sessions
    for i, method in enumerate(selected):
        ms = MethodSession(
            session_id=exp_session.id,
            method_id=method.id,
            order=i,
            status='pending',
        )
        db.session.add(ms)

    db.session.commit()

    # Store in Flask session
    session['exp_session_id'] = exp_session.id
    session['participant_id'] = participant.id
    session['experiment_id'] = experiment_id

    if experiment.demographics_enabled:
        return redirect(url_for('experiment.demographics', experiment_id=experiment_id))

    if mode == 'participant_choice':
        return redirect(url_for('experiment.method_choice', experiment_id=experiment_id))

    return redirect(url_for('experiment.instructions', experiment_id=experiment_id))


@experiment_bp.route('/experiment/<int:experiment_id>/demographics', methods=['GET', 'POST'])
def demographics(experiment_id):
    """Demographics form."""
    experiment = Experiment.query.get_or_404(experiment_id)
    exp_session = _get_current_session()
    if not exp_session:
        return redirect(url_for('experiment.welcome', experiment_id=experiment_id))

    participant = Participant.query.get(exp_session.participant_id)

    if request.method == 'POST':
        demo_data = {}
        fields = experiment.get_demographics_fields()
        if not fields:
            fields = [
                {'name': 'email', 'label': 'Email (optional)', 'type': 'email', 'required': False},
                {'name': 'experience', 'label': 'Years of IT experience', 'type': 'select',
                 'options': ['0-2', '3-5', '6-10', '10+'], 'required': False},
            ]
        for field in fields:
            val = request.form.get(field['name'], '')
            demo_data[field['name']] = val
            if field['name'] == 'email' and val:
                participant.email = val

        participant.set_demographics(demo_data)
        db.session.commit()

        if experiment.method_assignment_mode == 'participant_choice':
            return redirect(url_for('experiment.method_choice', experiment_id=experiment_id))
        return redirect(url_for('experiment.instructions', experiment_id=experiment_id))

    fields = experiment.get_demographics_fields()
    if not fields:
        fields = [
            {'name': 'email', 'label': 'Email (optional)', 'type': 'email', 'required': False},
            {'name': 'experience', 'label': 'Years of IT experience', 'type': 'select',
             'options': ['0-2', '3-5', '6-10', '10+'], 'required': False},
        ]
    return render_template('experiment/demographics.html', experiment=experiment, fields=fields)


@experiment_bp.route('/experiment/<int:experiment_id>/method_choice', methods=['GET', 'POST'])
def method_choice(experiment_id):
    """Let participant choose which methods to use."""
    experiment = Experiment.query.get_or_404(experiment_id)
    exp_session = _get_current_session()
    if not exp_session:
        return redirect(url_for('experiment.welcome', experiment_id=experiment_id))

    active_methods = experiment.get_active_methods()

    if request.method == 'POST':
        chosen_ids = request.form.getlist('methods')
        chosen_ids = [int(x) for x in chosen_ids if x.isdigit()]

        if not chosen_ids:
            flash('Please select at least one assessment method.', 'danger')
            return render_template('experiment/method_choice.html', experiment=experiment, methods=active_methods)

        # Create method sessions for chosen methods
        for i, mid in enumerate(chosen_ids):
            method = Method.query.get(mid)
            if method and method.experiment_id == experiment_id:
                ms = MethodSession(
                    session_id=exp_session.id,
                    method_id=method.id,
                    order=i,
                    status='pending',
                )
                db.session.add(ms)
        db.session.commit()

        return redirect(url_for('experiment.instructions', experiment_id=experiment_id))

    return render_template('experiment/method_choice.html', experiment=experiment, methods=active_methods)


@experiment_bp.route('/experiment/<int:experiment_id>/instructions')
def instructions(experiment_id):
    """Show experiment instructions."""
    experiment = Experiment.query.get_or_404(experiment_id)
    exp_session = _get_current_session()
    if not exp_session:
        return redirect(url_for('experiment.welcome', experiment_id=experiment_id))
    return render_template('experiment/instructions.html', experiment=experiment)


@experiment_bp.route('/experiment/<int:experiment_id>/run')
def run_method(experiment_id):
    """Run the next pending method in the session."""
    experiment = Experiment.query.get_or_404(experiment_id)
    exp_session = _get_current_session()
    if not exp_session:
        return redirect(url_for('experiment.welcome', experiment_id=experiment_id))

    # Find next pending method session
    method_session = MethodSession.query.filter_by(
        session_id=exp_session.id
    ).filter(
        MethodSession.status.in_(['pending', 'in_progress'])
    ).order_by(MethodSession.order).first()

    if not method_session:
        # All methods completed
        exp_session.completed_at = datetime.utcnow()
        db.session.commit()
        return redirect(url_for('experiment.complete', experiment_id=experiment_id))

    # Mark as in_progress
    if method_session.status == 'pending':
        method_session.status = 'in_progress'
        method_session.started_at = datetime.utcnow()
        db.session.commit()

    session['current_method_session_id'] = method_session.id

    return redirect(url_for('experiment.method_page', experiment_id=experiment_id,
                            method_session_id=method_session.id))


@experiment_bp.route('/experiment/<int:experiment_id>/method/<int:method_session_id>', methods=['GET', 'POST'])
def method_page(experiment_id, method_session_id):
    """Render or process a specific method."""
    experiment = Experiment.query.get_or_404(experiment_id)
    exp_session = _get_current_session()
    if not exp_session:
        return redirect(url_for('experiment.welcome', experiment_id=experiment_id))

    method_session = MethodSession.query.get_or_404(method_session_id)
    if method_session.session_id != exp_session.id:
        abort(403)

    method = method_session.method
    risks = Risk.query.filter_by(experiment_id=experiment_id).order_by(Risk.order).all()
    handler = get_method_handler(method.method_type)

    if request.method == 'POST':
        result = handler.process_response(request.form, method_session, risks)

        if result.get('error'):
            flash(result['error'], 'danger')
            context = handler.get_context(method_session, risks)
            return render_template(handler.get_template(),
                                   experiment=experiment, method=method,
                                   method_session=method_session, **context)

        if result.get('complete'):
            # Check if there are more methods
            next_ms = MethodSession.query.filter_by(
                session_id=exp_session.id
            ).filter(
                MethodSession.status.in_(['pending', 'in_progress']),
                MethodSession.id != method_session_id,
            ).order_by(MethodSession.order).first()

            if next_ms:
                return redirect(url_for('experiment.between_methods',
                                        experiment_id=experiment_id))
            else:
                exp_session.completed_at = datetime.utcnow()
                db.session.commit()
                return redirect(url_for('experiment.complete',
                                        experiment_id=experiment_id))
        else:
            # Method not complete (e.g. Uranus needs more comparisons)
            context = result.get('context', handler.get_context(method_session, risks))
            return render_template(handler.get_template(),
                                   experiment=experiment, method=method,
                                   method_session=method_session, **context)

    # GET — show method page
    if method_session.status == 'pending':
        method_session.status = 'in_progress'
        method_session.started_at = datetime.utcnow()
        db.session.commit()

    context = handler.get_context(method_session, risks)
    # Show method intro first if method has instructions
    show_intro = session.get(f'method_intro_shown_{method_session_id}')
    if method.instructions and not show_intro:
        session[f'method_intro_shown_{method_session_id}'] = True
        return render_template('experiment/method_intro.html',
                               experiment=experiment, method=method,
                               method_session=method_session)

    return render_template(handler.get_template(),
                           experiment=experiment, method=method,
                           method_session=method_session, **context)


@experiment_bp.route('/experiment/<int:experiment_id>/between')
def between_methods(experiment_id):
    """Page shown between methods."""
    experiment = Experiment.query.get_or_404(experiment_id)
    exp_session = _get_current_session()
    if not exp_session:
        return redirect(url_for('experiment.welcome', experiment_id=experiment_id))

    # Count completed/total
    all_ms = MethodSession.query.filter_by(session_id=exp_session.id).all()
    completed = sum(1 for ms in all_ms if ms.status == 'completed')
    total = len(all_ms)

    return render_template('experiment/between_methods.html',
                           experiment=experiment, completed=completed, total=total)


@experiment_bp.route('/experiment/<int:experiment_id>/complete')
def complete(experiment_id):
    """Completion page."""
    experiment = Experiment.query.get_or_404(experiment_id)
    return render_template('experiment/complete.html', experiment=experiment)
