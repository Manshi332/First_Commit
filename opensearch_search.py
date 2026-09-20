# opensearch_search.py
"""Optional local OpenSearch-backed full-text search over tickets.

This is CivicFlow's "Data and search" building block for the Build It track,
following the exact same pattern the codebase already uses for Ollama
(grievance_agent.py / evidence.py) and LocalStack (dispatch_notifier.py):

  * Nothing here is required for the app to run. If OpenSearch isn't
    installed/reachable, every function fails soft and the caller falls
    back to the naive in-memory substring search that already existed
    (see staff_ui.render_search).
  * Configuration is via env vars only, so the same code runs unchanged
    whether OpenSearch is a `finch compose` service on localhost, another
    container on the same network, or (Ship It) a managed Amazon OpenSearch
    Service domain — just point OPENSEARCH_HOST at it.

Why search needs this at all: the header search bar and "Ticket Command
Center" search already exist (staff_ui.render_search), but they do a plain
Python substring scan over every field of every ticket on every keystroke.
That's fine for a demo with ~20 tickets; a real city-scale deployment with
tens of thousands of tickets needs a proper inverted index, fuzzy matching,
and the ability to search ticket history/notes text — which is exactly what
OpenSearch is for. Indexing also gives the Registry & Audit page a
real search-behind-the-scenes story instead of a client-side dataframe scan.
"""
import os

OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "http://localhost:9200")
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "civicflow-tickets")
USE_OPENSEARCH = os.getenv("CIVIC_USE_OPENSEARCH", "1") == "1"

_client = None
_unavailable = False  # sticky flag so we don't retry a dead connection on every rerun


def _get_client():
    """Lazily create (and cache) the OpenSearch client. Returns None if the
    `opensearch-py` package isn't installed or the cluster can't be reached —
    callers must treat None as "search index unavailable, fall back."""
    global _client, _unavailable
    if not USE_OPENSEARCH or _unavailable:
        return None
    if _client is not None:
        return _client
    try:
        from opensearchpy import OpenSearch
        client = OpenSearch(
            hosts=[OPENSEARCH_HOST],
            http_compress=True,
            use_ssl=OPENSEARCH_HOST.startswith("https"),
            verify_certs=False,
            timeout=2,
        )
        if not client.ping():
            raise ConnectionError("OpenSearch did not respond to ping")
        if not client.indices.exists(OPENSEARCH_INDEX):
            client.indices.create(OPENSEARCH_INDEX, body={
                "settings": {"number_of_shards": 1, "number_of_replicas": 0},
                "mappings": {"properties": {
                    "ticket_id": {"type": "keyword"},
                    "title": {"type": "text"},
                    "category": {"type": "keyword"},
                    "ward": {"type": "keyword"},
                    "state": {"type": "keyword"},
                    "language": {"type": "keyword"},
                    "evidence_text": {"type": "text"},
                    "notes_text": {"type": "text"},
                }},
            })
        _client = client
        return _client
    except Exception:
        _unavailable = True
        return None


def _doc(ticket: dict) -> dict:
    notes = " ".join(h.get("note", "") for h in ticket.get("history", []) if h.get("note"))
    return {
        "ticket_id": ticket["ticket_id"],
        "title": ticket["title"],
        "category": ticket["category"],
        "ward": ticket["ward"],
        "state": ticket["state"],
        "language": ticket.get("language", "English"),
        "evidence_text": " ".join(ticket.get("evidence_list", [])),
        "notes_text": notes,
    }


def index_ticket(ticket: dict) -> bool:
    """Upserts one ticket into the search index. Safe to call after every
    mutation (new complaint, dispatch, resolution, dispute, ...) — failures
    are swallowed so indexing can never break the actual civic workflow."""
    client = _get_client()
    if client is None:
        return False
    try:
        client.index(index=OPENSEARCH_INDEX, id=ticket["ticket_id"], body=_doc(ticket))
        return True
    except Exception:
        return False


def reindex_all(tickets: dict) -> int:
    """Bulk (re)index every ticket — call once at startup / after seeding."""
    client = _get_client()
    if client is None:
        return 0
    ok = 0
    for t in tickets.values():
        if index_ticket(t):
            ok += 1
    return ok


def search_tickets(query: str, tickets: dict) -> list:
    """Full-text search across ticket title, evidence and notes.

    Returns a list of ticket_ids ranked by relevance. Falls back to the
    original naive substring scan (same fields the app searched before)
    whenever OpenSearch is unavailable, so the search bar always works —
    it just gets smarter/faster automatically once OpenSearch is up."""
    client = _get_client()
    if client is not None:
        try:
            resp = client.search(index=OPENSEARCH_INDEX, body={
                "query": {"multi_match": {
                    "query": query,
                    "fields": ["ticket_id^3", "title^2", "category", "ward",
                               "evidence_text", "notes_text", "language"],
                    "fuzziness": "AUTO",
                }},
                "size": 50,
            })
            hits = [h["_source"]["ticket_id"] for h in resp.get("hits", {}).get("hits", [])]
            if hits:
                return [h for h in hits if h in tickets]
        except Exception:
            pass  # fall through to the naive scan below

    ql = query.lower()
    return [tid for tid, t in tickets.items()
            if ql in " ".join([t["ticket_id"], t["title"], t["ward"], t["category"],
                               t["state"], *t.get("evidence_list", [])]).lower()]