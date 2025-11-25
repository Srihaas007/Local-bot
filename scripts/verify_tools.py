import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from local_agent.tools.web_fetch import WebFetch
from local_agent.tools.run_python import RunPython
from local_agent.config import FLAGS

def test_web_fetch():
    print("Testing WebFetch...")
    # Enable example.com for testing
    # FLAGS.allowed_domains is likely a tuple from config
    original_domains = FLAGS.allowed_domains
    FLAGS.allowed_domains = tuple(list(original_domains) + ["example.com"])
    
    wf = WebFetch()
    res = wf.run(url="https://example.com")
    
    if not res.ok:
        print(f"ERROR: WebFetch failed: {res.content}")
        sys.exit(1)
        
    if "Example Domain" not in res.content:
        print("ERROR: WebFetch content mismatch")
        sys.exit(1)
        
    print("WebFetch success.")

def test_run_python():
    print("Testing RunPython...")
    rp = RunPython()
    
    # Test 1: Simple calculation
    res = rp.run(code="print(1 + 1)")
    if not res.ok or "2" not in res.content:
        print(f"ERROR: RunPython simple calc failed: {res.content}")
        sys.exit(1)
        
    # Test 2: Sandbox violation (try to read a file outside sandbox)
    # We'll try to read the current script file which is definitely outside the sandbox
    this_file = Path(__file__).resolve()
    code = f"""
try:
    with open(r"{this_file}", "r") as f:
        print(f.read())
except Exception as e:
    print(f"Caught expected error: {{e}}")
"""
    res = rp.run(code=code)
    if "Caught expected error" not in res.content and "PermissionError" not in res.content:
        # Note: The tool might return ok=False or ok=True with the error printed, depending on how it handles exceptions.
        # But we expect the *content* to indicate failure to read.
        # If it actually read the file, that's a failure of the sandbox.
        if "def test_run_python" in res.content:
             print(f"ERROR: Sandbox violation! File was read.\n{res.content}")
             sys.exit(1)
             
    print("RunPython success.")

if __name__ == "__main__":
    test_web_fetch()
    test_run_python()
