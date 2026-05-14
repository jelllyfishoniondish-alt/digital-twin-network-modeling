"""Ryu REST API client for polling network state."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import urlopen


JsonValue = Any
Fetcher = Callable[[str, float], JsonValue]


@dataclass(slots=True)
class FetchFailure:
    """Structured record for a failed Ryu API call."""

    endpoint: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"endpoint": self.endpoint, "message": self.message}


def default_fetcher(url: str, timeout: float) -> JsonValue:
    """Default JSON fetcher used by the Ryu API client."""

    with urlopen(url, timeout=timeout) as response:  # noqa: S310
        return json.load(response)


def normalize_dpid(value: Any) -> str:
    """Normalize a datapath identifier into a stable string form."""

    if isinstance(value, int):
        return f"{value:016x}"

    text = str(value).strip().lower()
    if text.startswith("0x"):
        return text[2:].zfill(16)
    if all(ch in "0123456789abcdef" for ch in text) and len(text) == 16:
        return text
    if text.isdigit():
        return f"{int(text):016x}"
    return text


def normalize_port_no(value: Any) -> int:
    """Normalize a port number into an integer when possible."""

    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    raise ValueError(f"Unsupported port number: {value!r}")


class RyuAPIClient:
    """Small, fault-tolerant client for the Ryu REST APIs used by the twin."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 2.0,
        fetcher: Fetcher | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.fetcher = fetcher or default_fetcher
        self.last_api_call_count = 0

    def _get_json(self, path: str) -> JsonValue:
        url = urljoin(self.base_url, path.lstrip("/"))
        self.last_api_call_count += 1
        return self.fetcher(url, self.timeout)

    def _safe_get(self, path: str, default: JsonValue, errors: list[FetchFailure]) -> tuple[JsonValue, bool]:
        try:
            return self._get_json(path), True
        except (HTTPError, URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
            errors.append(FetchFailure(endpoint=path, message=str(exc)))
            return default, False

    def _candidate_switch_ids(self, raw_switch_id: Any) -> list[str]:
        candidates: list[str] = []
        for candidate in (str(raw_switch_id), normalize_dpid(raw_switch_id)):
            if candidate not in candidates:
                candidates.append(candidate)

        normalized_switch_id = normalize_dpid(raw_switch_id)
        if len(normalized_switch_id) == 16 and all(ch in "0123456789abcdef" for ch in normalized_switch_id):
            decimal_switch_id = str(int(normalized_switch_id, 16))
            if decimal_switch_id not in candidates:
                candidates.append(decimal_switch_id)
        return candidates

    def _safe_get_switch_stats(
        self,
        path_template: str,
        raw_switch_id: Any,
        default: JsonValue,
        errors: list[FetchFailure],
    ) -> tuple[JsonValue, bool]:
        endpoints: list[str] = []
        last_error: Exception | None = None

        for candidate_switch_id in self._candidate_switch_ids(raw_switch_id):
            path = path_template.format(switch_id=candidate_switch_id)
            endpoints.append(path)
            try:
                return self._get_json(path), True
            except (HTTPError, URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc

        errors.append(
            FetchFailure(
                endpoint=endpoints[0],
                message=str(last_error) if last_error is not None else "Unknown fetch failure",
            )
        )
        return default, False

    def get_switch_ids(self) -> list[str]:
        """Return normalized switch ids reported by Ryu."""

        raw_ids = self._get_json("/stats/switches")
        return [normalize_dpid(item) for item in raw_ids]

    def collect_state_payload(self) -> dict[str, Any]:
        """Collect the raw state needed to build a `NetworkState`."""

        self.last_api_call_count = 0
        errors: list[FetchFailure] = []
        topology_switches, topology_switches_ok = self._safe_get("/v1.0/topology/switches", [], errors)
        topology_links, topology_links_ok = self._safe_get("/v1.0/topology/links", [], errors)
        topology_hosts, topology_hosts_ok = self._safe_get("/v1.0/topology/hosts", [], errors)
        switch_ids, switch_ids_ok = self._safe_get("/stats/switches", [], errors)

        port_descriptions: dict[str, Any] = {}
        port_stats: dict[str, Any] = {}
        flows: dict[str, Any] = {}
        fetch_status: dict[str, Any] = {
            "topology_switches": topology_switches_ok,
            "links": topology_links_ok,
            "hosts": topology_hosts_ok,
            "switch_ids": switch_ids_ok,
            "port_descriptions": {},
            "port_stats": {},
            "flows": {},
        }

        for raw_switch_id in switch_ids:
            normalized_switch_id = normalize_dpid(raw_switch_id)
            port_descriptions[normalized_switch_id], fetch_status["port_descriptions"][normalized_switch_id] = (
                self._safe_get_switch_stats(
                    "/stats/portdesc/{switch_id}",
                    raw_switch_id,
                    {},
                    errors,
                )
            )
            port_stats[normalized_switch_id], fetch_status["port_stats"][normalized_switch_id] = (
                self._safe_get_switch_stats(
                    "/stats/port/{switch_id}",
                    raw_switch_id,
                    {},
                    errors,
                )
            )
            flows[normalized_switch_id], fetch_status["flows"][normalized_switch_id] = (
                self._safe_get_switch_stats(
                    "/stats/flow/{switch_id}",
                    raw_switch_id,
                    {},
                    errors,
                )
            )

        return {
            "topology_switches": topology_switches,
            "links": topology_links,
            "hosts": topology_hosts,
            "port_descriptions": port_descriptions,
            "port_stats": port_stats,
            "flows": flows,
            "fetch_status": fetch_status,
            "errors": [error.to_dict() for error in errors],
            "api_call_count": self.last_api_call_count,
        }
