"""
Tests for tradingagents.llm_adapters.embeddings module
(HSBC Internal Embedding Adapter)
"""

import os
from unittest.mock import patch

from tradingagents.llm_adapters.embeddings import (
    OpenAIEmbeddings,
    HSBCEmbeddings,
    create_hsbc_embeddings,
    embedding_text,
)


# Test OpenAIEmbeddings/HSBCEmbeddings initialization
def test_openai_embeddings_init():
    """Test OpenAIEmbeddings initialization with HSBC config"""
    embeddings = OpenAIEmbeddings(
        api_key="test-key",  # 会被忽略，仅保持兼容
        base_url="https://api.test.com",
        model="text-embedding-3-large",
        auth_method="B2B",
    )

    assert embeddings.base_url == "https://api.test.com"
    assert embeddings.model == "text-embedding-3-large"
    assert embeddings.auth_method == "B2B"

    print("PASS OpenAIEmbeddings init test passed")


def test_hsbc_embeddings_init_with_env():
    """Test HSBCEmbeddings initialization with environment variables"""
    with patch.dict(os.environ, {
        "HSBC_BASE_URL": "https://env.test.com",
        "HSBC_MODEL": "text-embedding-3-small",
        "HSBC_AUTH_METHOD": "S2B",
    }):
        embeddings = HSBCEmbeddings()

        assert embeddings.base_url == "https://env.test.com"
        assert embeddings.auth_method == "S2B"

    print("PASS HSBCEmbeddings with env test passed")


# Test embed_query
def test_embed_query():
    """Test embed_query method with HSBC auth"""
    with patch('tradingagents.llm_adapters.embedding_hsbc.embed_texts_direct') as mock_embed:
        mock_embed.return_value = [[0.1, 0.2, 0.3]]

        embeddings = OpenAIEmbeddings(
            base_url="https://api.test.com",
            auth_method="B2B",
        )
        result = embeddings.embed_query("测试文本")

        assert result == [0.1, 0.2, 0.3]
        mock_embed.assert_called_once()
        call_kwargs = mock_embed.call_args.kwargs
        assert call_kwargs['texts'] == ["测试文本"]
        assert call_kwargs['model'] == "text-embedding-3-large"
        assert call_kwargs['base_url'] == "https://api.test.com"

    print("PASS embed_query test passed")


def test_embed_query_empty():
    """Test embed_query with empty string"""
    embeddings = OpenAIEmbeddings(base_url="https://api.test.com")
    result = embeddings.embed_query("")
    assert result == []

    print("PASS embed_query empty test passed")


# Test embed_documents
def test_embed_documents():
    """Test embed_documents method"""
    with patch('tradingagents.llm_adapters.embedding_hsbc.embed_texts_direct') as mock_embed:
        mock_embed.return_value = [[0.1, 0.2], [0.3, 0.4]]

        embeddings = OpenAIEmbeddings(base_url="https://api.test.com")
        result = embeddings.embed_documents(["文本1", "文本2"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2]
        assert result[1] == [0.3, 0.4]
        mock_embed.assert_called_once()

    print("PASS embed_documents test passed")


def test_embed_documents_batch_processing():
    """Test embed_documents with large batch"""
    with patch('tradingagents.llm_adapters.embedding_hsbc.embed_texts_direct') as mock_embed:
        def create_mock_response(*args, **kwargs):
            texts = kwargs.get('texts', [])
            return [[float(i), float(i + 1)] for i in range(len(texts))]

        mock_embed.side_effect = create_mock_response

        embeddings = OpenAIEmbeddings(base_url="https://api.test.com")

        # Test with 25 texts (should be split into 3 batches: 10+10+5)
        texts = [f"文本{i}" for i in range(25)]
        result = embeddings.embed_documents(texts, batch_size=10)

        assert len(result) == 25
        # Should be called 3 times (10 + 10 + 5)
        assert mock_embed.call_count == 3

    print("PASS embed_documents batch processing test passed")


def test_embed_documents_empty():
    """Test embed_documents with empty list"""
    embeddings = OpenAIEmbeddings(base_url="https://api.test.com")
    result = embeddings.embed_documents([])
    assert result == []

    print("PASS embed_documents empty test passed")


def test_embed_documents_fallback():
    """Test embed_documents falls back to single-text processing on batch failure"""
    with patch('tradingagents.llm_adapters.embedding_hsbc.embed_texts_direct') as mock_embed:
        def side_effect(*args, **kwargs):
            texts = kwargs.get('texts', [])
            if len(texts) > 1:
                raise Exception("batch failed")
            return [[0.1, 0.2, 0.3]]

        mock_embed.side_effect = side_effect

        embeddings = OpenAIEmbeddings(base_url="https://api.test.com")
        result = embeddings.embed_documents(["文本1", "文本2"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] == [0.1, 0.2, 0.3]

    print("PASS embed_documents fallback test passed")


# Test create_hsbc_embeddings
def test_create_hsbc_embeddings():
    """Test create_hsbc_embeddings helper"""
    embeddings = create_hsbc_embeddings(
        model="text-embedding-3-small",
        auth_method="S2B",
    )

    assert isinstance(embeddings, OpenAIEmbeddings)
    assert embeddings.model == "text-embedding-3-small"
    assert embeddings.auth_method == "S2B"

    print("PASS create_hsbc_embeddings test passed")


# Test embedding_text function
def test_embedding_text():
    """Test embedding_text helper function"""
    with patch('tradingagents.llm_adapters.embedding_hsbc.embed_texts_direct') as mock_embed:
        mock_embed.return_value = [[0.1, 0.2, 0.3]]

        result = embedding_text("测试文本")

        assert result == [0.1, 0.2, 0.3]
        mock_embed.assert_called_once()

    print("PASS embedding_text test passed")


# Test HSBCEmbeddings alias
def test_hsbc_embeddings_alias():
    """Test HSBCEmbeddings is alias for OpenAIEmbeddings"""
    assert HSBCEmbeddings is OpenAIEmbeddings
    print("PASS HSBCEmbeddings alias test passed")


# Run all tests
if __name__ == "__main__":
    print("Running embeddings module tests...")
    print("=" * 50)

    print("\n1. Testing OpenAIEmbeddings initialization:")
    test_openai_embeddings_init()
    test_hsbc_embeddings_init_with_env()

    print("\n2. Testing embed_query:")
    test_embed_query()
    test_embed_query_empty()

    print("\n3. Testing embed_documents:")
    test_embed_documents()
    test_embed_documents_empty()
    test_embed_documents_batch_processing()
    test_embed_documents_fallback()

    print("\n4. Testing create_hsbc_embeddings:")
    test_create_hsbc_embeddings()

    print("\n5. Testing embedding_text:")
    test_embedding_text()

    print("\n6. Testing HSBCEmbeddings alias:")
    test_hsbc_embeddings_alias()

    print("\n" + "=" * 50)
    print("All embeddings tests completed!")
