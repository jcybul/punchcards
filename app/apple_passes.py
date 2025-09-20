import tempfile
from pathlib import Path

def build_pkpass(card, program) -> str:
    """
    Build and sign a .pkpass for a given WalletCard.
    For now, just return a placeholder file to prove wiring works.
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pkpass")
    tmp.write(b"placeholder pkpass content")
    tmp.close()
    return tmp.name