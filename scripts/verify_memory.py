import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from local_agent.memory.sqlite_memory import MemoryStore, MemoryItem

def test_semantic_memory():
    print("Initializing MemoryStore...")
    # Use a temporary DB for testing
    db_path = Path("test_memory.db")
    if db_path.exists():
        db_path.unlink()
    
    store = MemoryStore(db_path=db_path)
    
    if not store.embedder.enabled:
        print("ERROR: Embeddings provider not enabled. Check dependencies.")
        sys.exit(1)
        
    print("Adding memories...")
    memories = [
        MemoryItem(kind="fact", text="The capital of France is Paris."),
        MemoryItem(kind="fact", text="Python is a popular programming language."),
        MemoryItem(kind="fact", text="The sky is blue."),
    ]
    store.add_with_embeddings(memories)
    
    print("Searching for 'programming'...")
    results = store.search_semantic("programming", limit=1)
    print(f"Results: {results}")
    
    if not results:
        print("ERROR: No results found.")
        sys.exit(1)
        
    top_text = results[0][2]
    if "Python" not in top_text:
        print(f"ERROR: Expected Python memory, got: {top_text}")
        sys.exit(1)
        
    print("SUCCESS: Semantic memory verification passed.")
    
    # Cleanup
    if db_path.exists():
        db_path.unlink()

if __name__ == "__main__":
    test_semantic_memory()
