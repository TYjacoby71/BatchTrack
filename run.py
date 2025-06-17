#!/usr/bin/env python3
"""
Application entry point using factory pattern
"""
import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
