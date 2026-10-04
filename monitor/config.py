"""All settings in one place: secrets from .env, sources from sources.yaml."""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent      # the consulum/ folder
load_dotenv(ROOT / ".env")                          # puts .env values into os.environ

if not os.getenv("OPENAI_API_KEY"):
    raise SystemExit("OPENAI_API_KEY is missing: copy .env.example to .env and fill it in.")

DB_PATH = ROOT / "data" / "monitor.db"
N8N_URL = os.getenv("N8N_URL", "http://localhost:5678")   # the control room's buttons start n8n workflows here

# Models (D9, D14). Upgrading after the eval is a one-line change here.
EMBED_MODEL = "text-embedding-3-large"
CLASSIFY_MODEL = "gpt-6-luna"
BRIEFING_MODEL = "gpt-6.1-sol"

# Ingestion
FETCH_TIMEOUT_S = 10                                # give up on a slow feed after 10 s
USER_AGENT = "Mozilla/5.0 (Macintosh) MediaMonitor/0.1"  # says what we are (see CONCEPTS.md)
STORY_WINDOW_H = 48                                 # how far back to look for the same story (D8)
SIMILARITY_THRESHOLD = 0.55                         # same story at or above this score; provisional, tuned in ticket 1.6


def load_sources() -> list[dict]:
    """The enabled feeds from sources.yaml (read fresh each run, so edits apply without a restart)."""
    with open(ROOT / "sources.yaml", encoding="utf-8") as f:
        sources = yaml.safe_load(f)["sources"]
    return [s for s in sources if s.get("enabled", True)]
