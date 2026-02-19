import json
import csv
import io
from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, Response
import bcrypt
import pandas as pd

from app import db, PASSWORD_HASH
from app.models import (Experiment, Risk, Method, Participant, Session as ExpSession,
                         MethodSession, AssessmentResult, InteractionEvent)
from app.methods import METHOD_TYPE_LABELS, get_default_config, get_method_handler

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password', '').encode('utf-8')
        if bcrypt.checkpw(password, PASSWORD_HASH):
            session['admin_logged_in'] = True
            return redirect(url_for('admin.dashboard'))
        flash('Invalid password.', 'danger')
    return render_template('admin/login.html')


@admin_bp.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin.login'))


@admin_bp.route('/')
@admin_required
def dashboard():
    experiments = Experiment.query.order_by(Experiment.created_at.desc()).all()
    stats = {}
    for exp in experiments:
        sessions = ExpSession.query.filter_by(experiment_id=exp.id).all()
        completed = sum(1 for s in sessions if s.completed_at)
        stats[exp.id] = {
            'participants': Participant.query.filter_by(experiment_id=exp.id).count(),
            'sessions': len(sessions),
            'completed': completed,
            'abandoned': len(sessions) - completed,
        }
    return render_template('admin/dashboard.html', experiments=experiments, stats=stats,
                           METHOD_TYPE_LABELS=METHOD_TYPE_LABELS)


# --- Experiment CRUD ---

@admin_bp.route('/experiment/new', methods=['GET', 'POST'])
@admin_required
def experiment_new():
    if request.method == 'POST':
        exp = Experiment(
            name=request.form.get('name', 'New Experiment'),
            description=request.form.get('description', ''),
            welcome_text=request.form.get('welcome_text', ''),
            instructions=request.form.get('instructions', ''),
            method_assignment_mode=request.form.get('method_assignment_mode', 'fixed'),
            methods_per_participant=int(request.form.get('methods_per_participant', 0) or 0),
            demographics_enabled='demographics_enabled' in request.form,
            custom_css=request.form.get('custom_css', ''),
            is_active='is_active' in request.form,
            is_template='is_template' in request.form,
        )
        db.session.add(exp)
        db.session.commit()
        flash('Experiment created.', 'success')
        return redirect(url_for('admin.experiment_edit', experiment_id=exp.id))
    return render_template('admin/experiment_form.html', experiment=None,
                           METHOD_TYPE_LABELS=METHOD_TYPE_LABELS)


@admin_bp.route('/experiment/<int:experiment_id>/edit', methods=['GET', 'POST'])
@admin_required
def experiment_edit(experiment_id):
    exp = Experiment.query.get_or_404(experiment_id)
    if request.method == 'POST':
        exp.name = request.form.get('name', exp.name)
        exp.description = request.form.get('description', '')
        exp.welcome_text = request.form.get('welcome_text', '')
        exp.instructions = request.form.get('instructions', '')
        exp.method_assignment_mode = request.form.get('method_assignment_mode', 'fixed')
        exp.methods_per_participant = int(request.form.get('methods_per_participant', 0) or 0)
        exp.demographics_enabled = 'demographics_enabled' in request.form
        exp.custom_css = request.form.get('custom_css', '')
        exp.is_active = 'is_active' in request.form
        exp.is_template = 'is_template' in request.form

        # Demographics fields JSON
        demo_fields_raw = request.form.get('demographics_fields', '')
        if demo_fields_raw.strip():
            try:
                exp.demographics_fields = json.dumps(json.loads(demo_fields_raw))
            except json.JSONDecodeError:
                flash('Invalid JSON in demographics fields.', 'danger')

        db.session.commit()
        flash('Experiment updated.', 'success')
        return redirect(url_for('admin.experiment_edit', experiment_id=exp.id))

    return render_template('admin/experiment_form.html', experiment=exp,
                           METHOD_TYPE_LABELS=METHOD_TYPE_LABELS)


@admin_bp.route('/experiment/<int:experiment_id>/delete', methods=['POST'])
@admin_required
def experiment_delete(experiment_id):
    exp = Experiment.query.get_or_404(experiment_id)
    db.session.delete(exp)
    db.session.commit()
    flash('Experiment deleted.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/experiment/<int:experiment_id>/clone', methods=['POST'])
@admin_required
def experiment_clone(experiment_id):
    exp = Experiment.query.get_or_404(experiment_id)
    new_exp = Experiment(
        name=f"{exp.name} (copy)",
        description=exp.description,
        welcome_text=exp.welcome_text,
        instructions=exp.instructions,
        method_assignment_mode=exp.method_assignment_mode,
        method_order=exp.method_order,
        methods_per_participant=exp.methods_per_participant,
        demographics_enabled=exp.demographics_enabled,
        demographics_fields=exp.demographics_fields,
        custom_css=exp.custom_css,
        is_active=False,
        is_template=False,
        cloned_from_id=exp.id,
    )
    db.session.add(new_exp)
    db.session.flush()

    # Clone risks
    for risk in exp.risks:
        new_risk = Risk(
            experiment_id=new_exp.id,
            name=risk.name,
            description=risk.description,
            order=risk.order,
        )
        db.session.add(new_risk)

    # Clone methods
    for method in exp.methods:
        new_method = Method(
            experiment_id=new_exp.id,
            method_type=method.method_type,
            display_name=method.display_name,
            instructions=method.instructions,
            config=method.config,
            order=method.order,
            is_active=method.is_active,
        )
        db.session.add(new_method)

    db.session.commit()
    flash(f'Experiment cloned as "{new_exp.name}".', 'success')
    return redirect(url_for('admin.experiment_edit', experiment_id=new_exp.id))


@admin_bp.route('/experiment/<int:experiment_id>/toggle', methods=['POST'])
@admin_required
def experiment_toggle(experiment_id):
    exp = Experiment.query.get_or_404(experiment_id)
    exp.is_active = not exp.is_active
    db.session.commit()
    status = 'activated' if exp.is_active else 'deactivated'
    flash(f'Experiment {status}.', 'success')
    return redirect(url_for('admin.dashboard'))


# --- Risk Management ---

@admin_bp.route('/experiment/<int:experiment_id>/risks', methods=['GET', 'POST'])
@admin_required
def risks_manage(experiment_id):
    exp = Experiment.query.get_or_404(experiment_id)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('risk_name', '').strip()
            desc = request.form.get('risk_description', '').strip()
            if name:
                max_order = db.session.query(db.func.max(Risk.order)).filter_by(
                    experiment_id=experiment_id).scalar() or 0
                risk = Risk(experiment_id=experiment_id, name=name, description=desc,
                            order=max_order + 1)
                db.session.add(risk)
                db.session.commit()
                flash('Risk added.', 'success')
        elif action == 'delete':
            risk_id = request.form.get('risk_id')
            risk = Risk.query.get(risk_id)
            if risk and risk.experiment_id == experiment_id:
                db.session.delete(risk)
                db.session.commit()
                flash('Risk deleted.', 'success')
        elif action == 'reorder':
            order_str = request.form.get('risk_order', '')
            if order_str:
                ids = [int(x) for x in order_str.split(',') if x.strip()]
                for i, rid in enumerate(ids):
                    risk = Risk.query.get(rid)
                    if risk and risk.experiment_id == experiment_id:
                        risk.order = i
                db.session.commit()
                flash('Risk order updated.', 'success')
        elif action == 'edit':
            risk_id = request.form.get('risk_id')
            risk = Risk.query.get(risk_id)
            if risk and risk.experiment_id == experiment_id:
                risk.name = request.form.get('risk_name', risk.name)
                risk.description = request.form.get('risk_description', risk.description)
                db.session.commit()
                flash('Risk updated.', 'success')
        elif action == 'bulk_add':
            risks_text = request.form.get('risks_bulk', '')
            lines = [l.strip() for l in risks_text.strip().split('\n') if l.strip()]
            max_order = db.session.query(db.func.max(Risk.order)).filter_by(
                experiment_id=experiment_id).scalar() or 0
            for i, line in enumerate(lines):
                risk = Risk(experiment_id=experiment_id, name=line, order=max_order + i + 1)
                db.session.add(risk)
            db.session.commit()
            flash(f'{len(lines)} risks added.', 'success')

        return redirect(url_for('admin.risks_manage', experiment_id=experiment_id))

    risks = Risk.query.filter_by(experiment_id=experiment_id).order_by(Risk.order).all()
    return render_template('admin/risks.html', experiment=exp, risks=risks)


# --- Method Management ---

@admin_bp.route('/experiment/<int:experiment_id>/methods', methods=['GET', 'POST'])
@admin_required
def methods_manage(experiment_id):
    exp = Experiment.query.get_or_404(experiment_id)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            method_type = request.form.get('method_type', 'matrix')
            display_name = request.form.get('display_name', '').strip()
            if not display_name:
                display_name = METHOD_TYPE_LABELS.get(method_type, method_type)
            max_order = db.session.query(db.func.max(Method.order)).filter_by(
                experiment_id=experiment_id).scalar() or 0
            default_cfg = get_default_config(method_type)
            method = Method(
                experiment_id=experiment_id,
                method_type=method_type,
                display_name=display_name,
                instructions=request.form.get('method_instructions', ''),
                config=json.dumps(default_cfg),
                order=max_order + 1,
            )
            db.session.add(method)
            db.session.commit()
            flash('Method added.', 'success')
        elif action == 'delete':
            method_id = request.form.get('method_id')
            method = Method.query.get(method_id)
            if method and method.experiment_id == experiment_id:
                db.session.delete(method)
                db.session.commit()
                flash('Method deleted.', 'success')
        elif action == 'toggle':
            method_id = request.form.get('method_id')
            method = Method.query.get(method_id)
            if method and method.experiment_id == experiment_id:
                method.is_active = not method.is_active
                db.session.commit()
        elif action == 'reorder':
            order_str = request.form.get('method_order', '')
            if order_str:
                ids = [int(x) for x in order_str.split(',') if x.strip()]
                for i, mid in enumerate(ids):
                    method = Method.query.get(mid)
                    if method and method.experiment_id == experiment_id:
                        method.order = i
                db.session.commit()
                flash('Method order updated.', 'success')
        elif action == 'update_config':
            method_id = request.form.get('method_id')
            method = Method.query.get(method_id)
            if method and method.experiment_id == experiment_id:
                method.display_name = request.form.get('display_name', method.display_name)
                method.instructions = request.form.get('method_instructions', method.instructions)
                config_raw = request.form.get('config_json', '')
                if config_raw.strip():
                    try:
                        method.config = json.dumps(json.loads(config_raw))
                    except json.JSONDecodeError:
                        flash('Invalid JSON in config.', 'danger')
                db.session.commit()
                flash('Method updated.', 'success')

        return redirect(url_for('admin.methods_manage', experiment_id=experiment_id))

    methods = Method.query.filter_by(experiment_id=experiment_id).order_by(Method.order).all()
    return render_template('admin/methods.html', experiment=exp, methods=methods,
                           METHOD_TYPE_LABELS=METHOD_TYPE_LABELS)


# --- Participants ---

@admin_bp.route('/experiment/<int:experiment_id>/participants')
@admin_required
def participants(experiment_id):
    exp = Experiment.query.get_or_404(experiment_id)
    participants_list = Participant.query.filter_by(experiment_id=experiment_id).order_by(
        Participant.created_at.desc()).all()
    sessions = {}
    for p in participants_list:
        sessions[p.id] = ExpSession.query.filter_by(participant_id=p.id).all()
    return render_template('admin/participants.html', experiment=exp,
                           participants=participants_list, sessions=sessions)


# --- Results ---

@admin_bp.route('/experiment/<int:experiment_id>/results')
@admin_required
def results(experiment_id):
    exp = Experiment.query.get_or_404(experiment_id)
    risks = Risk.query.filter_by(experiment_id=experiment_id).order_by(Risk.order).all()
    methods = Method.query.filter_by(experiment_id=experiment_id).order_by(Method.order).all()

    # Get all completed method sessions with results
    results_data = []
    for method in methods:
        method_sessions = MethodSession.query.filter_by(method_id=method.id).filter(
            MethodSession.status == 'completed').all()
        for ms in method_sessions:
            exp_session = ExpSession.query.get(ms.session_id)
            participant = Participant.query.get(exp_session.participant_id) if exp_session else None
            handler = get_method_handler(method.method_type)
            summary = handler.get_results_summary(ms, risks)
            results_data.append({
                'method': method,
                'method_session': ms,
                'participant': participant,
                'summary': summary,
            })

    return render_template('admin/results.html', experiment=exp, results_data=results_data,
                           risks=risks, methods=methods)


@admin_bp.route('/experiment/<int:experiment_id>/results/export/<format>')
@admin_required
def results_export(experiment_id, format):
    exp = Experiment.query.get_or_404(experiment_id)
    risks = Risk.query.filter_by(experiment_id=experiment_id).order_by(Risk.order).all()

    # Collect all assessment results
    rows = []
    sessions = ExpSession.query.filter_by(experiment_id=experiment_id).all()
    for exp_session in sessions:
        participant = Participant.query.get(exp_session.participant_id)
        method_sessions = MethodSession.query.filter_by(session_id=exp_session.id).all()
        for ms in method_sessions:
            method = Method.query.get(ms.method_id)
            ars = AssessmentResult.query.filter_by(method_session_id=ms.id).all()
            for ar in ars:
                risk = Risk.query.get(ar.risk_id) if ar.risk_id else None
                data = ar.get_result_data()
                rows.append({
                    'participant_name': participant.name if participant else '',
                    'participant_uuid': participant.uuid if participant else '',
                    'session_id': exp_session.id,
                    'method_type': method.method_type if method else '',
                    'method_name': method.display_name if method else '',
                    'method_session_id': ms.id,
                    'risk_id': ar.risk_id or '',
                    'risk_name': risk.name if risk else '',
                    'result_data': json.dumps(data),
                    'started_at': str(ms.started_at or ''),
                    'completed_at': str(ms.completed_at or ''),
                })

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    if format == 'csv':
        if not rows:
            return Response("No data", mimetype="text/plain")
        df = pd.DataFrame(rows)
        csv_data = df.to_csv(index=False)
        return Response(csv_data, mimetype="text/csv",
                        headers={"Content-disposition":
                                 f"attachment; filename=results-{exp.id}-{timestamp}.csv"})
    elif format == 'json':
        return Response(json.dumps(rows, indent=2, default=str), mimetype="application/json",
                        headers={"Content-disposition":
                                 f"attachment; filename=results-{exp.id}-{timestamp}.json"})
    return "Invalid format", 400


# --- Interaction Logs ---

@admin_bp.route('/experiment/<int:experiment_id>/interactions')
@admin_required
def interaction_logs(experiment_id):
    exp = Experiment.query.get_or_404(experiment_id)

    # Filters
    session_filter = request.args.get('session_id', type=int)
    event_type_filter = request.args.get('event_type', '')
    page = request.args.get('page', 1, type=int)
    per_page = 100

    query = InteractionEvent.query.join(ExpSession).filter(ExpSession.experiment_id == experiment_id)
    if session_filter:
        query = query.filter(InteractionEvent.session_id == session_filter)
    if event_type_filter:
        query = query.filter(InteractionEvent.event_type == event_type_filter)

    query = query.order_by(InteractionEvent.id.desc())
    total = query.count()
    events = query.offset((page - 1) * per_page).limit(per_page).all()

    # Get unique event types for filter dropdown
    event_types = db.session.query(InteractionEvent.event_type).distinct().all()
    event_types = sorted([et[0] for et in event_types])

    # Get sessions for filter dropdown
    sessions_list = ExpSession.query.filter_by(experiment_id=experiment_id).all()

    return render_template('admin/interaction_logs.html', experiment=exp, events=events,
                           event_types=event_types, sessions=sessions_list,
                           page=page, per_page=per_page, total=total,
                           session_filter=session_filter, event_type_filter=event_type_filter)


@admin_bp.route('/experiment/<int:experiment_id>/interactions/export/<format>')
@admin_required
def interactions_export(experiment_id, format):
    exp = Experiment.query.get_or_404(experiment_id)
    events = InteractionEvent.query.join(ExpSession).filter(
        ExpSession.experiment_id == experiment_id
    ).order_by(InteractionEvent.id).all()

    rows = []
    for evt in events:
        rows.append({
            'id': evt.id,
            'session_id': evt.session_id,
            'method_session_id': evt.method_session_id or '',
            'timestamp': evt.timestamp,
            'event_type': evt.event_type,
            'element_id': evt.element_id,
            'element_tag': evt.element_tag,
            'element_class': evt.element_class,
            'page_url': evt.page_url,
            'event_data': json.dumps(evt.get_event_data()),
        })

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    if format == 'csv':
        if not rows:
            return Response("No data", mimetype="text/plain")
        df = pd.DataFrame(rows)
        csv_data = df.to_csv(index=False)
        return Response(csv_data, mimetype="text/csv",
                        headers={"Content-disposition":
                                 f"attachment; filename=interactions-{exp.id}-{timestamp}.csv"})
    elif format == 'json':
        return Response(json.dumps(rows, indent=2, default=str), mimetype="application/json",
                        headers={"Content-disposition":
                                 f"attachment; filename=interactions-{exp.id}-{timestamp}.json"})
    return "Invalid format", 400
