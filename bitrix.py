from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx


@dataclass
class BitrixError(Exception):
    message: str
    details: str = ""


class BitrixClient:
    def __init__(self, webhook_base: str, timeout: float = 20.0):
        self.webhook_base = webhook_base
        self.timeout = timeout

    async def call(self, method: str, data) -> Dict[str, Any]:
        url = f"{self.webhook_base}{method}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(url, data=data)
        try:
            payload = r.json()
        except Exception:
            raise BitrixError(f"Bitrix returned non-JSON response (HTTP {r.status_code})", r.text)

        if "error" in payload:
            raise BitrixError(payload.get("error", "bitrix_error"), payload.get("error_description", ""))
        return payload


      async def upload_to_folder(self, folder_id: int, local_path: str, filename: str | None = None) -> int:
          url = f"{self.webhook_base}disk.folder.uploadfile"
          name = filename or local_path.split("/")[-1]
          async with httpx.AsyncClient(timeout=self.timeout) as client:
              with open(local_path, "rb") as f:
                  r = await client.post(url, data={"id": str(int(folder_id))}, files={"file": (name, f)})
          try:
              payload = r.json()
          except Exception:
              raise BitrixError(f"Bitrix returned non-JSON response (HTTP {r.status_code})", r.text)
          if "error" in payload:
              raise BitrixError(payload.get("error", "bitrix_error"), payload.get("error_description", ""))
          # обычно: {"result":{"ID":"123",...}}
          try:
              return int(payload["result"]["ID"])
          except Exception:
              raise BitrixError("Cannot parse disk file id from Bitrix response", str(payload))


    async def create_task(
        self,
        title: str,
        description: str,
        responsible_id: int,
        group_id: Optional[int] = None,
        priority: Optional[int] = None,
        created_by: Optional[int] = None,
          webdav_file_ids: Optional[list[int]] = None,
    ) -> int:
                  fields = [
              ("fields[TITLE]", title),
              ("fields[DESCRIPTION]", description),
              ("fields[RESPONSIBLE_ID]", str(responsible_id)),
          ]

        if group_id is not None:
            fields.append(("fields[GROUP_ID]", str(group_id)))
        if priority is not None:
            fields.append(("fields[PRIORITY]", str(priority)))
        if created_by is not None:
            fields.append(("fields[CREATED_BY]", str(created_by)))

        resp = await self.call("tasks.task.add", fields)

        # Bitrix обычно возвращает: {"result":{"task":{"id":"123",...}}}
        task_id = None
        try:
            task_id = int(resp["result"]["task"]["id"])
        except Exception:
            # fallback attempts
            try:
                task_id = int(resp["result"]["id"])
            except Exception:
                raise BitrixError("Cannot parse task id from Bitrix response", str(resp))

        return task_id
