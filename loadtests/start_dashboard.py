
#!/usr/bin/env python3
"""
Simple Locust dashboard starter
"""
import subprocess
import sys

def start_dashboard():
    """Start Locust with web dashboard"""
    print("🚀 Starting Locust load test dashboard...")
    print("💡 Dashboard will be available at:")
    print("   - Internal: http://0.0.0.0:8091")
    print("   - In webview: Switch to port 3002")
    print("   - Target: Your Flask app on port 5000")
    print()
    
    cmd = [
        'locust',
        '-f', 'loadtests/locustfile.py',
        '--host=http://0.0.0.0:5000',
        '--web-host=0.0.0.0',
        '--web-port=8091'
    ]
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n🛑 Load test dashboard stopped")
        return True
    except Exception as e:
        print(f"❌ Error starting dashboard: {e}")
        return False

if __name__ == '__main__':
    start_dashboard()
