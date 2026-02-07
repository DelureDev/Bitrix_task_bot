from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

log = logging.getLogger(__name__)


@dataclass
class BitrixError(Exception):
    message: str
    details: str = ""


class BitrixClient:
    def __init__(
        self,
        webhook_base: str,
        timeout: float = 20.0,
        upload_timeout: float = 90.0,
        upload_url_timeout: float = 25.0,
    ):
        self.webhook_base = webhook_base
        self.timeout = timeout
        self.upload_timeout = upload_timeout
        self.upload_url_timeout = upload_url_timeout

    @staticmethod
    def _exc_brief(exc: Exception) -> str:
        text = str(exc).strip()
        if text:
            return f"{exc.__class__.__name__}: {text}"
        return exc.__class__.__name__

    @staticmethod
    def _is_timeout_error(exc: Exception) -> bool:
        if isinstance(exc, httpx.TimeoutException):
            return True
        if isinstance(exc, BitrixError):
            details = f"{exc.message} {exc.details}".lower()
            markers = ("timeout", "readtimeout", "writetimeout", "connecttimeout", "pooltimeout")
            return any(marker in details for marker in markers)
        return False

    async def call(
        self,
        method: str,
        data: list[tuple[str, str]] | dict[str, str],
        timeout: float | httpx.Timeout | None = None,
    ) -> dict[str, Any]:
        url = f"{self.webhook_base}{method}"
        encoded = urlencode(data).encode("utf-8")
        request_timeout = timeout if timeout is not None else self.timeout
        async with httpx.AsyncClient(timeout=request_timeout) as client:
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

    async def _upload_via_file_content(
        self,
        folder_id: int,
        local_path: str,
        name: str,
        timeout_s: float | None = None,
    ) -> int:
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
        effective_timeout = timeout_s if timeout_s is not None else self.upload_timeout
        timeout = httpx.Timeout(
            connect=min(20.0, effective_timeout),
            read=effective_timeout,
            write=effective_timeout,
            pool=min(20.0, effective_timeout),
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

    async def _upload_via_upload_url(
        self,
        folder_id: int,
        local_path: str,
        name: str,
        timeout_s: float | None = None,
    ) -> int:
        effective_timeout = timeout_s if timeout_s is not None else self.upload_url_timeout
        timeout = httpx.Timeout(
            connect=min(20.0, effective_timeout),
            read=effective_timeout,
            write=effective_timeout,
            pool=min(20.0, effective_timeout),
        )

        # Step 1: request an upload slot from Bitrix Disk.
        payload = await self.call(
            "disk.folder.uploadfile",
            [
                ("id", str(int(folder_id))),
                ("data[NAME]", name),
                ("generateUniqueName", "true"),
            ],
            timeout=effective_timeout,
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
        async with httpx.AsyncClient(timeout=timeout) as client:
            with open(local_path, "rb") as file_obj:
                response = await client.post(
                    str(upload_url),
                    files={str(field_name): (name, file_obj)},
                )

        try:
            upload_payload = response.json()
        except Exception:
            raise BitrixError(
                f"Bitrix upload URL returned non-JSON response (HTTP {response.status_code})",
                response.text,
            )

        if "error" in upload_payload:
            raise BitrixError(
                upload_payload.get("error", "bitrix_error"),
                upload_payload.get("error_description", ""),
            )

        file_id = self._extract_disk_file_id(upload_payload)
        if file_id is not None:
            return file_id

        raise BitrixError("Cannot parse disk file id from upload response", str(upload_payload))

    async def upload_to_folder(self, folder_id: int, local_path: str, filename: str | None = None) -> int:
        name = filename or Path(local_path).name
        size_bytes = Path(local_path).stat().st_size

        # For small files prefer fileContent to avoid waiting on unstable signed upload URL.
        small_file = size_bytes <= 2 * 1024 * 1024
        if small_file:
            # Keep small-file uploads fast but avoid overly aggressive timeouts on unstable links.
            small_fc_timeout = min(self.upload_timeout, 15.0)
            small_url_timeout = min(self.upload_url_timeout, 12.0)
            strategies = (
                ("fileContent", self._upload_via_file_content, small_fc_timeout),
                ("uploadUrl", self._upload_via_upload_url, small_url_timeout),
            )
        else:
            strategies = (
                ("uploadUrl", self._upload_via_upload_url, self.upload_timeout),
                ("fileContent", self._upload_via_file_content, self.upload_timeout),
            )

        failures: list[str] = []
        for strategy_name, strategy, timeout_s in strategies:
            started = time.monotonic()
            try:
                file_id = await strategy(
                    folder_id=folder_id,
                    local_path=local_path,
                    name=name,
                    timeout_s=timeout_s,
                )
                elapsed_ms = int((time.monotonic() - started) * 1000)
                log.info(
                    "Bitrix disk upload strategy=%s success file=%s size=%sB elapsed_ms=%s timeout_s=%s",
                    strategy_name,
                    name,
                    size_bytes,
                    elapsed_ms,
                    timeout_s,
                )
                return file_id
            except Exception as exc:
                elapsed_ms = int((time.monotonic() - started) * 1000)
                err = self._exc_brief(exc)
                log.warning(
                    "Bitrix disk upload strategy=%s failed file=%s size=%sB elapsed_ms=%s timeout_s=%s error=%s",
                    strategy_name,
                    name,
                    size_bytes,
                    elapsed_ms,
                    timeout_s,
                    err,
                )
                failures.append(f"{strategy_name}: {err}")
                # For small files, timeout on fileContent usually means transient Bitrix/network stall.
                # Skip uploadUrl in the same attempt and let outer retry happen immediately.
                if small_file and strategy_name == "fileContent" and self._is_timeout_error(exc):
                    log.warning(
                        "Bitrix disk upload short-circuit file=%s reason=fileContent_timeout",
                        name,
                    )
                    break

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
