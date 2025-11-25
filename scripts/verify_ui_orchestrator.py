import threading
import time
import requests
import uvicorn
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.local_agent.web.server import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="critical")

def test_orchestrator_endpoint():
    print("Starting server for verification...")
    # Start server in a thread
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    time.sleep(3) # Wait for server to start

    try:
        print("Sending request to /orchestrate...")
        # Simple task that shouldn't require complex tools
        resp = requests.post("http://127.0.0.1:8001/orchestrate", json={"task": "What is 2 + 2?"})
        
        if resp.status_code != 200:
            print(f"FAILED: Status code {resp.status_code}")
            print(resp.text)
            return

        data = resp.json()
        
        if "history" not in data:
            print("FAILED: 'history' not in response")
            print(data)
            return
        
        history = data["history"]
        print(f"Received history with {len(history)} steps.")
        for step in history:
            print(f"Step {step['step']}: {step['action']} -> {step['output']}")
            
        print("SUCCESS: Orchestrator endpoint verified.")
            
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    test_orchestrator_endpoint()
