
#!/usr/bin/env python3
"""
Application entry point using factory pattern
"""
import logging
import sys
from app import create_app

app = create_app()

if __name__ == '__main__':
    # Enable console logging for development
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s: %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    app.logger.setLevel(logging.DEBUG)
    app.run(host='0.0.0.0', port=5000, debug=True)
