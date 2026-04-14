import pytest
import sys
sys.path.insert(0, "/c/Users/Camille/Desktop/qq-bot")


@pytest.fixture
def mock_ollama_response():
    return {"message": {"content": "test response"}}


@pytest.fixture
def mock_deepseek_response():
    return {"choices": [{"message": {"content": "test response"}}]}
