import json
import os

import requests


def send_discord(
    webhook_url: str,
    *,
    title: str,
    description: str,
    fields: list[dict[str, object]] | None = None,
    image_paths: list[str] | None = None,
) -> None:
    image_paths = image_paths or []
    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": 0x2563EB,
                "fields": fields or [],
            }
        ],
    }
    files: dict[str, tuple[str, object, str]] = {}
    handles = []

    for idx, image_path in enumerate(image_paths):
        filename = os.path.basename(image_path)
        if idx == 0:
            payload["embeds"][0]["image"] = {"url": f"attachment://{filename}"}
        else:
            payload["embeds"].append(
                {
                    "color": 0x0F766E,
                    "image": {"url": f"attachment://{filename}"},
                }
            )
        file_handle = open(image_path, "rb")
        handles.append(file_handle)
        files[f"files[{idx}]"] = (filename, file_handle, "image/png")

    try:
        resp = requests.post(
            webhook_url,
            data={"payload_json": json.dumps(payload, ensure_ascii=False)},
            files=files,
            timeout=20,
        )
    finally:
        for file_handle in handles:
            file_handle.close()

    if resp.status_code not in (200, 204):
        raise RuntimeError(f"Discord webhook 失敗：{resp.status_code} {resp.text}")
