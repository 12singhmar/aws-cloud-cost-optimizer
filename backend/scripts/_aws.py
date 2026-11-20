"""Small shared helpers for the scripts that talk to AWS."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:  # pragma: no cover
    sys.exit("boto3 is not installed. Run: pip install -r requirements.txt")

LAB_TAG = "ccx-lab"


def session(profile: str | None, region: str):
    try:
        s = boto3.Session(profile_name=profile, region_name=region)
        s.client("sts").get_caller_identity()
        return s
    except NoCredentialsError:
        sys.exit("No AWS credentials found. See docs/REAL_ACCOUNT_GUIDE.md, step 3.")
    except ClientError as e:
        sys.exit(f"AWS rejected the credentials: {e}")


def tags_to_dict(tags: list[dict] | None) -> dict[str, str]:
    return {t["Key"]: t["Value"] for t in (tags or [])}


def mask_account(account_id: str) -> str:
    """Never store the full account number in files that may go to GitHub."""
    return "*" * 8 + account_id[-4:]


__all__ = ["session", "tags_to_dict", "mask_account", "ClientError", "LAB_TAG"]
