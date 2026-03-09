#!/usr/bin/env python
"""
Production WSGI application entry point
"""
import os
from app import create_app

# Create application instance
app = create_app()

if __name__ == "__main__":
    # Development server (not for production)
    app.run(
        host=os.environ.get('HOST', '0.0.0.0'),
        port=int(os.environ.get('PORT', 5000)),
        debug=os.environ.get('FLASK_ENV', 'development') == 'development'
    )
