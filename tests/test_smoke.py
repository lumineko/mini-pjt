"""Phase 1 스모크 테스트: 설계(SERVICE.md)에서 쓰는 핵심 API가 설치된 버전에서 import되는지 확인한다."""

import sys


def test_python_version():
    assert sys.version_info >= (3, 12)


def test_langgraph_apis():
    from langgraph.checkpoint.memory import MemorySaver  # noqa: F401
    from langgraph.graph import END, START, StateGraph  # noqa: F401
    from langgraph.types import Command, interrupt  # noqa: F401


def test_langchain_aws_bedrock_converse():
    from langchain_aws import ChatBedrockConverse  # noqa: F401


def test_support_libraries():
    import dotenv  # noqa: F401
    import pydantic
    import streamlit  # noqa: F401

    assert int(pydantic.VERSION.split(".")[0]) >= 2


def test_package_importable():
    import opic  # noqa: F401  (pytest.ini의 pythonpath=src 확인)
