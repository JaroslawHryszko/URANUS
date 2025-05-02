# URANUS Research Project (Neptune)

URANUS (Ultra-light Risk ANalysis Using Stepwise Comparison) is a research project for evaluating software development risk assessment methodologies developed by the Department of Software Engineering at Jagiellonian University.

## Overview

This Flask-based web application allows users to participate in a research study comparing traditional risk matrix assessment with a novel comparison-based approach for evaluating risks in a hypothetical ERP system implementation at Jagiellonian University.

## Features

- **Dual Risk Assessment Methods**
  - Classic approach: Rate risks on probability and impact (1-5 scale)
  - Novelty approach: Compare pairs of risks to determine relative priority

- **Admin Dashboard**
  - View assessment results
  - Export data to CSV for analysis
  - Configure risks and assessment parameters
  - User data management

- **Research Data Collection**
  - Secure storage of assessment results
  - User session tracking
  - Structured data export for analysis

## Installation

1. Clone the repository
   ```
   git clone [repository URL]
   cd neptune
   ```

2. Create a virtual environment (recommended)
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables
   - Create a `.env` file based on `.env.example`
   - Set necessary environment variables (admin password, etc.)

5. Initialize the database
   ```
   python -c "from backend import db, app; with app.app_context(): db.create_all()"
   ```

## Usage

1. Start the application
   ```
   python backend.py
   ```

2. Access the application in your web browser
   - Development: http://localhost:5000
   - Follow the instructions to complete the risk assessment exercise

3. Access admin features
   - Go to `/admin` and log in with credentials set in the `.env` file
   - View results and export data for research analysis

## Development

- The application uses Flask and SQLAlchemy with SQLite
- Templates are built with Jinja2 and stored in the `templates/` directory
- Static files (CSS, JS) are in the `static/` directory
- Configuration settings can be modified in `config.json`

## Security

- Admin interface is protected with password authentication
- Passwords are hashed using bcrypt
- User sessions are tracked with secure UUIDs
- Input sanitization is implemented with bleach

## License

This code is distributed under the MIT license.

## Contributors

Jarosław Hryszko - jaroslaw.hryszko@uj.edu.pl
Adam Roman - adam.roman@uj.edu.pl
