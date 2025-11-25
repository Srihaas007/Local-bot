import sys
import json
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from local_agent.tools.skill_tools import ProposeSkill, InstallSkill
from local_agent.skills.manager import SkillManager

def test_skill_factory():
    print("Testing ProposeSkill...")
    proposer = ProposeSkill()
    res = proposer.run(
        name="echo_test",
        description="Echoes input text",
        inputs={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
    )
    
    if not res.ok:
        print(f"ERROR: ProposeSkill failed: {res.content}")
        sys.exit(1)
        
    print("Proposal successful. Parsing manifest and code...")
    # Extract manifest and code from output (simulating user review)
    # The output format is: Proposed skill '...'.\n\nManifest:\n{...}\n\nCode:\n...\n\nTests:\n...
    
    content = res.content
    manifest_start = content.find("Manifest:\n") + 10
    code_start = content.find("\n\nCode:\n")
    tests_start = content.find("\n\nTests:\n")
    
    manifest_str = content[manifest_start:code_start].strip()
    code_str = content[code_start+8:tests_start].strip()
    tests_str = content[tests_start+9:].strip()
    
    manifest = json.loads(manifest_str)
    
    print("Testing InstallSkill...")
    installer = InstallSkill()
    # We use approve=False to skip interactive pytest run in this script, 
    # but we can manually trigger it if we want. For now let's just install.
    # Actually, let's try approve=True but we need to make sure pytest doesn't hang or fail.
    # The generated test uses the generated tool.
    
    res_install = installer.run(
        manifest=manifest,
        code=code_str,
        tests=tests_str,
        approve=True 
    )
    
    if not res_install.ok:
        print(f"ERROR: InstallSkill failed: {res_install.content}")
        sys.exit(1)
        
    print(f"Installation successful: {res_install.content}")
    
    # Verify the tool is actually loadable
    print("Verifying tool loading...")
    try:
        from local_agent.tools.generated.echo_test import EchoTestTool
        t = EchoTestTool()
        r = t.run(text="hello world")
        if r.content == "hello world":
            print("SUCCESS: Skill factory verification passed.")
        else:
            print(f"ERROR: Tool output mismatch: {r.content}")
            sys.exit(1)
    except ImportError:
        print("ERROR: Could not import generated tool.")
        sys.exit(1)
        
    # Cleanup (optional, maybe keep it for inspection)
    # SkillManager doesn't have uninstall yet, so we leave it.

if __name__ == "__main__":
    test_skill_factory()
