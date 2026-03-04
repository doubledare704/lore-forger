from functools import lru_cache
from dotenv import load_dotenv
from google import genai

load_dotenv()


@lru_cache(maxsize=1)
def get_genai_client() -> genai.Client:
    """Create a singleton GenAI client.

    The best practice is to rely on env vars:
      - GEMINI_API_KEY (recommended)
      - GOOGLE_API_KEY (also supported)
    """

    return genai.Client()
