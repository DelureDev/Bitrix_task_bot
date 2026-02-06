from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx


@dataclass
class BitrixError(Exception):
    message: str
    details: str = ""


class BitrixClient:
    def __init__(self, webhook_base: str, timeout: float = 20.0, upload_timeout: float = 90.0):
        self.webhook_base = webhook_base
        self.timeout = timeout
        self.upload_timeout = upload_timeout

    async def call(self, method: str, data: list[tuple[str, str]] | dict[str, str]) -> dict[str, Any]:
        url = f"{self.webhook_base}{method}"
        encoded = urlencode(data).encode("utf-8")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                content=encoded,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        try:
            payload = response.json()
        except Exception:
            raise BitrixError(
                f"Bitrix returned non-JSON response (HTTP {response.status_code})",
                response.text,
            )

        if "error" in payload:
            raise BitrixError(payload.get("error", "bitrix_error"), payload.get("error_description", ""))
        return payload

    @staticmethod
    def _extract_disk_file_id(payload: dict[str, Any]) -> int | None:
        result = payload.get("result")
        if not isinstance(result, dict):
            return None

        # Most common shape: {"result": {"ID": "..."}}
        for key in ("ID", "id", "FILE_ID", "fileId"):
            value = result.get(key)
            if value is not None:
                try:
                    return int(value)
                except Exception:
                    pass

        # Some responses wrap the file object inside nested nodes.
        for node_key in ("FILE", "file", "ITEM", "item", "OBJECT", "object"):
            node = result.get(node_key)
            if isinstance(node, dict):
                for key in ("ID", "id", "FILE_ID", "fileId"):
                    value = node.get(key)
                    if value is not None:
                        try:
                            return int(value)
                        except Exception:
                            pass

        return None

    async def _upload_via_file_content(self, folder_id: int, local_path: str, name: str) -> int:
        with open(local_path, "rb") as file_obj:
            encoded = base64.b64encode(file_obj.read()).decode("ascii")

        data: list[tuple[str, str]] = [
            ("id", str(int(folder_id))),
            ("data[NAME]", name),
            ("generateUniqueName", "true"),
            ("fileContent[0]", name),
            ("fileContent[1]", encoded),
        ]
        encoded_data = urlencode(data).encode("utf-8")
        timeout = httpx.Timeout(
            connect=min(20.0, self.upload_timeout),
            read=self.upload_timeout,
            write=self.upload_timeout,
            pool=min(20.0, self.upload_timeout),
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.webhook_base}disk.folder.uploadfile",
                content=encoded_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        try:
            payload = response.json()
        except Exception:
            raise BitrixError(
                f"Bitrix returned non-JSON response (HTTP {response.status_code})",
                response.text,
            )
        if "error" in payload:
            raise BitrixError(payload.get("error", "bitrix_error"), payload.get("error_description", ""))

        file_id = self._extract_disk_file_id(payload)
        if file_id is not None:
            return file_id
        raise BitrixError("Cannot parse disk file id from fileContent response", str(payload))

    async def _upload_via_upload_url(self, folder_id: int, local_path: str, name: str) -> int:
        timeout = httpx.Timeout(
            connect=min(20.0, self.upload_timeout),
            read=self.upload_timeout,
            write=self.upload_timeout,
            pool=min(20.0, self.upload_timeout),
        )

        # Step 1: request an upload slot from Bitrix Disk.
        payload = await self.call(
            "disk.folder.uploadfile",
            [
                ("id", str(int(folder_id))),
                ("data[NAME]", name),
                ("generateUniqueName", "true"),
            ],
        )
        file_id = self._extract_disk_file_id(payload)
        if file_id is not None:
            return file_id

        result = payload.get("result")
        if not isinstance(result, dict):
            raise BitrixError("Cannot parse upload descriptor from Bitrix response", str(payload))

        upload_url = result.get("uploadUrl")
        field_name = result.get("field")
        if not upload_url or not field_name:
            raise BitrixError("Upload URL or field is missing in Bitrix response", str(payload))

        # Step 2: upload binary to the signed URL returned by Step 1.
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                with open(local_path, "rb") as file_obj:
                    response = await client.post(
                        str(upload_url),
                        files={str(field_name): (name, file_obj)},
                    )
        except httpx.TransportError:
            # Fallback for unstable uploadUrl transport path: send content via REST fileContent.
            return await self._upload_via_file_content(folder_id=folder_id, local_path=local_path, name=name)

        try:
            upload_payload = response.json()
        except Exception:
            return await self._upload_via_file_content(folder_id=folder_id, local_path=local_path, name=name)

        if "error" in upload_payload:
            return await self._upload_via_file_content(folder_id=folder_id, local_path=local_path, name=name)

        file_id = self._extract_disk_file_id(upload_payload)
        if file_id is not None:
            return file_id

        raise BitrixError("Cannot parse disk file id from upload response", str(upload_payload))

    async def upload_to_folder(self, folder_id: int, local_path: str, filename: str | None = None) -> int:
        name = filename or Path(local_path).name
        size_bytes = Path(local_path).stat().st_size

        # For small files use one REST call (fileContent) first to avoid long waits on uploadUrl transport.
        prefer_file_content = size_bytes <= 5 * 1024 * 1024
        strategies = (
            ("fileContent", self._upload_via_file_content),
            ("uploadUrl", self._upload_via_upload_url),
        )
        if not prefer_file_content:
            strategies = (
                ("uploadUrl", self._upload_via_upload_url),
                ("fileContent", self._upload_via_file_content),
            )

        failures: list[str] = []
        for strategy_name, strategy in strategies:
            try:
                return await strategy(folder_id=folder_id, local_path=local_path, name=name)
            except Exception as exc:
                failures.append(f"{strategy_name}: {exc}")

        raise BitrixError("All disk upload strategies failed", " | ".join(failures))

    async def create_task(
        self,
        title: str,
        description: str,
        responsible_id: int,
        group_id: int | None = None,
        priority: int | None = None,
        created_by: int | None = None,
        webdav_file_ids: list[int] | None = None,
    ) -> int:
        fields: list[tuple[str, str]] = [
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
        if webdav_file_ids:
            for idx, file_id in enumerate(webdav_file_ids):
                fields.append((f"fields[UF_TASK_WEBDAV_FILES][{idx}]", f"n{int(file_id)}"))

        payload = await self.call("tasks.task.add", fields)
        try:
            return int(payload["result"]["task"]["id"])
        except Exception:
            try:
                return int(payload["result"]["id"])
            except Exception:
                raise BitrixError("Cannot parse task id from Bitrix response", str(payload))
