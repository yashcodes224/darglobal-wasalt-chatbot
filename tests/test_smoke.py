import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.rag import load_index, wants_listing


def test_retrieval():
    idx = load_index()
    assert len(idx.chunks) >= 50
    top = idx.search("Which projects are in Oman?", k=12)
    assert top and all("Oman" in h["chunk_text"] for h in top[:8])
    assert idx.search("Who owns Wasalt?", k=3)[0]["source"] == "wasalt"
    assert idx.search("Trump Mansions Riyadh", k=1)[0]["title"] == "Trump Mansions"
    assert idx.search("Fendi Casa", k=5)
    assert wants_listing("list all projects in Spain")
