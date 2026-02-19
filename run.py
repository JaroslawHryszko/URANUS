#!/usr/bin/env python3
"""Entry point for URANUS v3 (Neptune v3.0)."""

import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.config import Config

app = create_app(Config)

if __name__ == '__main__':
    host = Config.HOST
    port = Config.PORT
    debug_mode = Config.FLASK_ENV == 'development'

    print(f"Starting URANUS v3 at http://{host}:{port}")
    print(f"Admin panel: http://{host}:{port}/admin/login")

    if debug_mode:
        app.run(debug=True, host=host, port=port)
    else:
        from waitress import serve
        try:
            serve(app, host=host, port=port)
        except Exception as e:
            print(f"Error starting Waitress: {e}")
            print("Falling back to Flask dev server...")
            app.run(debug=True, host=host, port=port)
