import json
from typing import Any, Dict

from .xurl_util import run_xurl

from data_models import ProposedMisleadingNote


def submit_note(
    note: ProposedMisleadingNote,
    test_mode: bool = True,
    verbose_if_failed: bool = True,
) -> Dict[str, Any]:
    """
    Submit a note to the Community Notes API. For more details, see:
    https://docs.x.com/x-api/community-notes/introduction
    """
    payload = {
        "test_mode": test_mode,
        "post_id": note.post_id,
        "info": {
            "text": note.note_text,
            "classification": "misinformed_or_potentially_misleading",
            "misleading_tags": [tag.value for tag in note.misleading_tags],
            "trustworthy_sources": True,
        },
    }

    cmd_verify = [
        "xurl",
        "auth",
        "oauth1",
        "--consumer-key",
        "FJWzGBdbzkXyfwzGomEsc5omc",
        "--consumer-secret",
        "M7zLxCQY5t1cD7WC2vYjcJvabLUsGYeYIbfyo11dsZuAFQilg5",
        "--access-token",
        "1934534495035871232-dVNpKzamYCU8s8pjIxjcOWAxGbOspO",
        "--token-secret",
        "3L1oOzZFCYJGISXwpv8QDgvNrAPw01RzOGzx1RahVDTf8",
    ]

    run_xurl(cmd_verify, verbose_if_failed=verbose_if_failed)

    cmd = [
        "xurl",
        "-X",
        "POST",
        "/2/notes",
        "-d",
        json.dumps(payload),
    ]

    return run_xurl(cmd, verbose_if_failed=verbose_if_failed)
