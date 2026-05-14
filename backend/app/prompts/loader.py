from functools import lru_cache
from pathlib import Path


PROMPT_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=32)
def load_prompt(relative_path: str) -> str:
    path = (PROMPT_DIR / relative_path).resolve()
    if PROMPT_DIR not in path.parents and path != PROMPT_DIR:
        raise ValueError("prompt path must stay inside prompt directory")
    return path.read_text(encoding="utf-8").strip()


def load_domain_prompt(domain: str) -> str:
    return load_prompt(f"domains/{domain}.md")
