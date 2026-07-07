"""URL safety checks for user-supplied fetch targets."""

import ipaddress
import socket
from typing import Iterable
from urllib.parse import urljoin, urlparse


PRIVATE_HOSTNAMES = {"localhost"}
BLOCKED_METADATA_HOSTS = {
    "169.254.169.254",
    "metadata.google.internal",
}


class UnsafeURL(ValueError):
    """Raised when a user-supplied URL points to a blocked destination."""


def validate_public_http_url(url: str) -> str:
    """Return a normalized URL if it is safe to fetch from the server."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeURL("仅支持 http/https 链接")
    if not parsed.hostname:
        raise UnsafeURL("链接缺少有效域名")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in PRIVATE_HOSTNAMES or hostname in BLOCKED_METADATA_HOSTS:
        raise UnsafeURL("不允许访问本机或云厂商元数据地址")

    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        _validate_resolved_addresses(hostname)
    else:
        _validate_ip(ip)

    return parsed.geturl()


def resolve_redirect_url(base_url: str, location: str) -> str:
    """Resolve and validate a redirect target."""
    return validate_public_http_url(urljoin(base_url, location))


def _validate_resolved_addresses(hostname: str) -> None:
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURL("链接域名无法解析") from exc

    addresses: Iterable[str] = (info[4][0] for info in infos)
    for address in addresses:
        _validate_ip(ipaddress.ip_address(address))


def _validate_ip(ip: ipaddress._BaseAddress) -> None:
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise UnsafeURL("不允许访问内网、保留或本机地址")
