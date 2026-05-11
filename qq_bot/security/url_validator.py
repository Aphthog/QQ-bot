import ipaddress
import socket
from urllib.parse import urlparse

PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

ALLOWED_SCHEMES = {"http", "https"}


class URLValidationError(ValueError):
    pass


def validate_url(url: str) -> None:
    """校验 URL 安全性。不通过抛 URLValidationError。"""
    parsed = urlparse(url)

    host = parsed.hostname

    if parsed.scheme and parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise URLValidationError(f"blocked scheme: {parsed.scheme}")

    if not host:
        raise URLValidationError("no host in URL")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # 是域名，DNS 解析后再检查
        try:
            ip = ipaddress.ip_address(socket.gethostbyname(host))
        except (socket.gaierror, ValueError):
            raise URLValidationError(f"cannot resolve host: {host}")

    for net in PRIVATE_NETWORKS:
        if ip in net:
            raise URLValidationError(f"private/internal IP blocked: {ip}")
