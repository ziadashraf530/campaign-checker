import os
import re
from typing import Any

import pandas as pd

_DEFAULT_USER_KEYS = {
    "username",
    "user",
    "user_name",
    "handle",
    "influencer",
    "creator",
    "account",
    "account_name",
    "author",
    "profile",
    "name",
}

_DEFAULT_LINK_KEYS = {
    "link",
    "url",
    "post",
    "post_url",
    "post_link",
    "media",
    "media_url",
    "media_link",
    "permalink",
    "share_url",
    "video_url",
    "image_url",
}

_DEFAULT_CAPTION_KEYS = {
    "caption",
    "caption_text",
    "post_text",
    "description",
    "text",
    "copy",
    "content",
}


def load_excel_posts(
    excel_path: str,
    username_column: str | None = None,
    link_column: str | None = None,
    caption_column: str | None = None,
) -> list[dict[str, Any]]:
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    df = pd.read_excel(excel_path)
    if df.empty:
        return []

    column_map = {_normalize_column(c): c for c in df.columns}

    requested_user = _normalize_column(username_column) if username_column else None
    requested_link = _normalize_column(link_column) if link_column else None
    requested_caption = _normalize_column(caption_column) if caption_column else None

    user_col = _resolve_column(column_map, requested_user, _DEFAULT_USER_KEYS)
    link_col = _resolve_column(column_map, requested_link, _DEFAULT_LINK_KEYS)
    caption_col = _resolve_column(column_map, requested_caption, _DEFAULT_CAPTION_KEYS)

    if not user_col or not link_col:
        available = ", ".join(str(c) for c in df.columns)
        raise ValueError(
            "Could not auto-detect username/link columns. "
            f"Available columns: {available}"
        )

    posts: list[dict[str, Any]] = []
    for idx, row in df.iterrows():
        link_val = row.get(link_col)
        if pd.isna(link_val):
            continue
        link = str(link_val).strip()
        if not link:
            continue

        username_val = row.get(user_col)
        username = "Unknown" if pd.isna(username_val) else str(username_val).strip()
        if not username:
            username = "Unknown"

        posts.append({
            "username": username,
            "link": link,
            "row_index": int(idx),
            "caption": "" if caption_col is None or pd.isna(row.get(caption_col)) else str(row.get(caption_col)).strip(),
        })

    return posts


def _normalize_column(column: Any) -> str:
    if column is None:
        return ""
    text = str(column).strip().lower()
    text = re.sub(r"[\s\-]+", "_", text)
    text = re.sub(r"[^a-z0-9_]", "", text)
    return text


def _resolve_column(
    normalized_map: dict[str, Any],
    requested: str | None,
    keywords: set[str],
) -> Any:
    if requested and requested in normalized_map:
        return normalized_map[requested]

    for key in keywords:
        if key in normalized_map:
            return normalized_map[key]

    for norm, original in normalized_map.items():
        for key in keywords:
            if key and key in norm:
                return original

    return None
