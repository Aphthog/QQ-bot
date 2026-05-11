import pytest
from qq_bot.security.url_validator import validate_url, URLValidationError

def test_valid_https():
    validate_url("https://example.com/page")

def test_valid_http():
    validate_url("http://example.com")

def test_block_file():
    with pytest.raises(URLValidationError, match="blocked scheme"):
        validate_url("file:///etc/passwd")

def test_block_loopback():
    with pytest.raises(URLValidationError, match="private/internal"):
        validate_url("http://127.0.0.1/admin")

def test_block_169_254():
    with pytest.raises(URLValidationError, match="private/internal"):
        validate_url("http://169.254.169.254/latest/meta-data/")

def test_block_private_10():
    with pytest.raises(URLValidationError, match="private/internal"):
        validate_url("http://10.0.0.1/secret")

def test_block_private_192_168():
    with pytest.raises(URLValidationError, match="private/internal"):
        validate_url("http://192.168.1.1/config")

def test_block_private_172_16():
    with pytest.raises(URLValidationError, match="private/internal"):
        validate_url("http://172.16.0.1/")

def test_block_no_host():
    with pytest.raises(URLValidationError, match="no host"):
        validate_url("not-a-url")

def test_valid_ipv4_public():
    validate_url("https://8.8.8.8/index.html")
