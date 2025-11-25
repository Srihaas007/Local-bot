import uvicorn
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

if __name__ == "__main__":
    print("Starting Local Agent Web UI...")
    print("Open http://127.0.0.1:8000 in your browser.")
    # Run from project root to ensure imports work correctly
    os.chdir(project_root)
    uvicorn.run("src.local_agent.web.server:app", host="127.0.0.1", port=8000, reload=True)
