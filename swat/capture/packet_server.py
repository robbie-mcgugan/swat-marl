from flask import Flask, jsonify
from capture import PacketCapture  # Assuming the original code is in packet_capture.py
import threading

app = Flask(__name__)

# Initialize PacketCapture with your interfaces
interfaces = ['s1-eth1', 's1-eth2', 's1-eth3']
capture = PacketCapture(interfaces)

# Start capture in a separate thread
capture_thread = threading.Thread(target=capture.start_capture)
capture_thread.daemon = True
capture_thread.start()

@app.route('/metrics', methods=['GET'])
def get_metrics():
    """Get metrics for all interfaces combined"""
    try:
        metrics = capture.get_current_metrics()
        return jsonify(metrics), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/metrics/<interface_id>', methods=['GET'])
def get_interface_metrics(interface_id):
    """Get metrics for a specific interface"""
    try:
        
        local_metrics = capture.get_current_metrics(interface_id)
        
        global_metrics = capture.get_current_metrics()

        return jsonify({
            'local': local_metrics,
            'global': global_metrics
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/restart', methods=['GET'])
def restart_capture():
    """Restart the packet capture by clearing stored data"""
    try:
        capture.restart_capture()
        return jsonify({
            'status': 'success',
            'message': 'Packet capture restarted successfully'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)