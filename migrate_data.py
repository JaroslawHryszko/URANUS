#!/usr/bin/env python3
"""Migrate data from Neptune v2 (data.db) to Neptune v3 schema.

Creates a legacy experiment with the original risks and migrates
ClassicResults and NoveltyResults into the new AssessmentResult format.
"""

import os
import sys
import json
import sqlite3
import uuid
from datetime import datetime

# Setup Flask app context
os.environ.setdefault('DATABASE_URI', 'sqlite:///data.db')
from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app.config import Config
from app.models import (Experiment, Risk, Method, Participant,
                         Session as ExpSession, MethodSession, AssessmentResult)

app = create_app(Config)


def migrate():
    # Load old config
    config_path = 'config.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    risk_names = config['risks']
    instructions_list = config.get('instructions', [])
    welcome_list = config.get('welcome_text', [])

    instructions_html = '<br>\n'.join(f'<p>{p}</p>' for p in instructions_list)
    welcome_html = '<br>\n'.join(f'<p>{p}</p>' for p in welcome_list)

    # Connect to old DB
    old_db_path = 'instance/data_v2_backup.db'
    if not os.path.exists(old_db_path):
        old_db_path = 'instance/data.db'
    print(f"Reading old data from: {old_db_path}")
    old_conn = sqlite3.connect(old_db_path)
    old_conn.row_factory = sqlite3.Row

    with app.app_context():
        # Create legacy experiment
        exp = Experiment(
            name='ERP Risk Assessment (legacy)',
            description='Migrated from Neptune v2.0',
            welcome_text=welcome_html,
            instructions=instructions_html,
            method_assignment_mode='participant_choice',
            demographics_enabled=False,
            is_active=True,
        )
        db.session.add(exp)
        db.session.flush()
        print(f"Created experiment: {exp.name} (id={exp.id})")

        # Create risks
        risk_map = {}  # old_index -> new Risk
        for i, name in enumerate(risk_names):
            risk = Risk(experiment_id=exp.id, name=name, order=i)
            db.session.add(risk)
            db.session.flush()
            risk_map[i] = risk
        print(f"Created {len(risk_map)} risks")

        # Create methods
        matrix_method = Method(
            experiment_id=exp.id,
            method_type='matrix',
            display_name='Classic Risk Assessment (FMEA Style)',
            instructions='Evaluate each risk for probability and impact on a scale of 1-5.',
            config=json.dumps({
                'criteria': [
                    {'name': 'probability', 'display_name': 'Probability', 'scale_min': 1, 'scale_max': 5,
                     'labels': {'1': 'Very Low', '2': 'Low', '3': 'Medium', '4': 'High', '5': 'Very High'}},
                    {'name': 'impact', 'display_name': 'Impact', 'scale_min': 1, 'scale_max': 5,
                     'labels': {'1': 'Very Low', '2': 'Low', '3': 'Medium', '4': 'High', '5': 'Very High'}},
                ],
                'aggregation': 'product',
                'weights': {},
            }),
            order=1,
        )
        db.session.add(matrix_method)

        uranus_method = Method(
            experiment_id=exp.id,
            method_type='uranus',
            display_name='Comparison-based Risk Assessment (Uranus)',
            instructions='Compare pairs of risks to determine relative priority.',
            config=json.dumps({'parameters': ['impact', 'probability']}),
            order=0,
        )
        db.session.add(uranus_method)
        db.session.flush()
        print(f"Created methods: Uranus (id={uranus_method.id}), Matrix (id={matrix_method.id})")

        # Migrate users -> participants
        old_users = old_conn.execute("SELECT * FROM user").fetchall()
        participant_map = {}  # old user_id -> new Participant
        for u in old_users:
            p = Participant(
                experiment_id=exp.id,
                uuid=u['user_id'],
                name=u['name'],
            )
            db.session.add(p)
            db.session.flush()
            participant_map[u['user_id']] = p
        print(f"Migrated {len(participant_map)} users -> participants")

        # Migrate ClassicResults
        classic_rows = old_conn.execute("SELECT * FROM classic_results").fetchall()
        classic_count = 0
        # Group by user_id + start_time to create sessions
        classic_sessions = {}
        for row in classic_rows:
            key = (row['user_id'], str(row['start_time']))
            if key not in classic_sessions:
                classic_sessions[key] = []
            classic_sessions[key].append(row)

        for (user_id, start_time), rows in classic_sessions.items():
            participant = participant_map.get(user_id)
            if not participant:
                # Create synthetic participant
                participant = Participant(
                    experiment_id=exp.id,
                    uuid=user_id if user_id else str(uuid.uuid4()),
                    name=f'legacy_user_{user_id[:8]}' if user_id else 'unknown',
                )
                db.session.add(participant)
                db.session.flush()
                participant_map[user_id] = participant

            # Create session
            exp_session = ExpSession(
                participant_id=participant.id,
                experiment_id=exp.id,
                started_at=datetime.fromisoformat(rows[0]['start_time']) if rows[0]['start_time'] else datetime.utcnow(),
                completed_at=datetime.fromisoformat(rows[0]['end_time']) if rows[0]['end_time'] else datetime.utcnow(),
            )
            db.session.add(exp_session)
            db.session.flush()

            # Create method session
            ms = MethodSession(
                session_id=exp_session.id,
                method_id=matrix_method.id,
                order=0,
                started_at=exp_session.started_at,
                completed_at=exp_session.completed_at,
                status='completed',
            )
            db.session.add(ms)
            db.session.flush()

            # Create assessment results
            for row in rows:
                risk_idx = row['risk_id']
                risk = risk_map.get(risk_idx)
                ar = AssessmentResult(
                    method_session_id=ms.id,
                    risk_id=risk.id if risk else None,
                )
                ar.set_result_data({
                    'criteria_values': {
                        'probability': row['probability'],
                        'impact': row['impact'],
                    },
                    'priority': row['priority'],
                    'migrated_from': 'ClassicResults',
                    'original_risk_name': row['risk_name'],
                })
                db.session.add(ar)
                classic_count += 1

        print(f"Migrated {classic_count} ClassicResults -> AssessmentResult")

        # Migrate NoveltyResults
        novelty_rows = old_conn.execute("SELECT * FROM novelty_results").fetchall()
        novelty_count = 0
        # Group by user_id to create sessions
        novelty_sessions = {}
        for row in novelty_rows:
            uid = row['user_id']
            if uid not in novelty_sessions:
                novelty_sessions[uid] = []
            novelty_sessions[uid].append(row)

        for user_id, rows in novelty_sessions.items():
            participant = participant_map.get(user_id)
            if not participant:
                participant = Participant(
                    experiment_id=exp.id,
                    uuid=user_id if user_id else str(uuid.uuid4()),
                    name=f'legacy_user_{user_id[:8]}' if user_id else 'unknown',
                )
                db.session.add(participant)
                db.session.flush()
                participant_map[user_id] = participant

            # Create session
            exp_session = ExpSession(
                participant_id=participant.id,
                experiment_id=exp.id,
                started_at=datetime.fromisoformat(rows[0]['start_time']) if rows[0]['start_time'] else datetime.utcnow(),
                completed_at=datetime.fromisoformat(rows[-1]['end_time']) if rows[-1]['end_time'] else None,
            )
            db.session.add(exp_session)
            db.session.flush()

            ms = MethodSession(
                session_id=exp_session.id,
                method_id=uranus_method.id,
                order=0,
                started_at=exp_session.started_at,
                completed_at=exp_session.completed_at,
                status='completed' if exp_session.completed_at else 'abandoned',
            )
            db.session.add(ms)
            db.session.flush()

            for row in rows:
                # Find risk by name
                risk_a_id = None
                risk_b_id = None
                for idx, risk in risk_map.items():
                    if risk.name == row['risk_a_description']:
                        risk_a_id = risk.id
                    if risk.name == row['risk_b_description']:
                        risk_b_id = risk.id

                ar = AssessmentResult(
                    method_session_id=ms.id,
                    risk_id=risk_a_id,
                )
                ar.set_result_data({
                    'risk_a_id': risk_a_id,
                    'risk_b_id': risk_b_id,
                    'risk_a_description': row['risk_a_description'],
                    'risk_b_description': row['risk_b_description'],
                    'chosen': row['chosen_risk'],
                    'parameter': row['parameter'],
                    'start_time': str(row['start_time']),
                    'end_time': str(row['end_time']),
                    'migrated_from': 'NoveltyResults',
                })
                db.session.add(ar)
                novelty_count += 1

        print(f"Migrated {novelty_count} NoveltyResults -> AssessmentResult")

        db.session.commit()
        print("Migration complete!")

        # Validation
        print("\n--- Validation ---")
        print(f"Old ClassicResults: {len(classic_rows)}, migrated: {classic_count}")
        print(f"Old NoveltyResults: {len(novelty_rows)}, migrated: {novelty_count}")
        print(f"Old Users: {len(old_users)}, new Participants: {Participant.query.count()}")
        print(f"New Experiments: {Experiment.query.count()}")
        print(f"New Risks: {Risk.query.count()}")
        print(f"New Methods: {Method.query.count()}")
        print(f"New Sessions: {ExpSession.query.count()}")
        print(f"New MethodSessions: {MethodSession.query.count()}")
        print(f"New AssessmentResults: {AssessmentResult.query.count()}")

    old_conn.close()


if __name__ == '__main__':
    migrate()
