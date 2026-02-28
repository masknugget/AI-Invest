"""
Tests for tradingagents.llm_adapters.embeddings module
"""

import os
from unittest.mock import Mock, patch, MagicMock

from tradingagents.llm_adapters.embeddings import (
    OpenAIEmbeddings,
    create_dashscope_embeddings,
    embedding_text,
)


# Test OpenAIEmbeddings initialization
def test_openai_embeddings_init():
    """Test OpenAIEmbeddings initialization"""
    with patch('tradingagents.llm_adapters.embeddings.OpenAI') as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        
        embeddings = OpenAIEmbeddings(
            api_key="test-key",
            base_url="https://api.test.com",
            model="text-embedding-v3"
        )
        
        assert embeddings.api_key == "test-key"
        assert embeddings.base_url == "https://api.test.com"
        assert embeddings.model == "text-embedding-v3"
        
    print("✅ OpenAIEmbeddings init test passed")


# Test embed_query
def test_embed_query():
    """Test embed_query method"""
    with patch('tradingagents.llm_adapters.embeddings.OpenAI') as mock_client_class:
        # Setup mock response
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
        
        mock_instance = MagicMock()
        mock_instance.embeddings.create.return_value = mock_response
        mock_client_class.return_value = mock_instance
        
        embeddings = OpenAIEmbeddings(api_key="test-key")
        result = embeddings.embed_query("测试文本")
        
        assert result == [0.1, 0.2, 0.3]
        mock_instance.embeddings.create.assert_called_once_with(
            model="text-embedding-v3",
            input="测试文本"
        )
        
    print("✅ embed_query test passed")


def test_embed_query_empty():
    """Test embed_query with empty string"""
    with patch('tradingagents.llm_adapters.embeddings.OpenAI'):
        embeddings = OpenAIEmbeddings(api_key="test-key")
        result = embeddings.embed_query("")
        assert result == []
        
    print("✅ embed_query empty test passed")


# Test embed_documents
def test_embed_documents():
    """Test embed_documents method"""
    with patch('tradingagents.llm_adapters.embeddings.OpenAI') as mock_client_class:
        # Setup mock response
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1, 0.2]),
            MagicMock(embedding=[0.3, 0.4]),
        ]
        
        mock_instance = MagicMock()
        mock_instance.embeddings.create.return_value = mock_response
        mock_client_class.return_value = mock_instance
        
        embeddings = OpenAIEmbeddings(api_key="test-key")
        result = embeddings.embed_documents(["文本1", "文本2"])
        
        assert len(result) == 2
        assert result[0] == [0.1, 0.2]
        assert result[1] == [0.3, 0.4]
        mock_instance.embeddings.create.assert_called_once_with(
            model="text-embedding-v3",
            input=["文本1", "文本2"]
        )
        
    print("✅ embed_documents test passed")


def test_embed_documents_batch_processing():
    """Test embed_documents with large batch (DashScope limit test)"""
    with patch('tradingagents.llm_adapters.embeddings.OpenAI') as mock_client_class:
        # Setup mock response - returns 12 embeddings per call
        def create_mock_response(batch):
            mock = MagicMock()
            mock.data = [MagicMock(embedding=[float(i), float(i+1)]) for i in range(len(batch))]
            return mock
        
        mock_instance = MagicMock()
        mock_instance.embeddings.create.side_effect = create_mock_response
        mock_client_class.return_value = mock_instance
        
        embeddings = OpenAIEmbeddings(api_key="test-key")
        
        # Test with 25 texts (should be split into 3 batches: 10+10+5)
        texts = [f"文本{i}" for i in range(25)]
        result = embeddings.embed_documents(texts, batch_size=10)
        
        assert len(result) == 25
        # Should be called 3 times (10 + 10 + 5)
        assert mock_instance.embeddings.create.call_count == 3
        
    print("✅ embed_documents batch processing test passed")


def test_embed_documents_batch_size_limit():
    """Test embed_documents respects batch_size limit"""
    with patch('tradingagents.llm_adapters.embeddings.OpenAI') as mock_client_class:
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1, 0.2]) for _ in range(20)]
        
        mock_instance = MagicMock()
        mock_instance.embeddings.create.return_value = mock_response
        mock_client_class.return_value = mock_instance
        
        embeddings = OpenAIEmbeddings(api_key="test-key")
        
        # Request batch_size=20, but should be capped to 10
        texts = [f"文本{i}" for i in range(20)]
        result = embeddings.embed_documents(texts, batch_size=20)
        
        assert len(result) == 20
        # Should be called 2 times (10 + 10) because 20 is capped to 10
        assert mock_instance.embeddings.create.call_count == 2
        
    print("✅ embed_documents batch size limit test passed")


def test_embed_documents_empty():
    """Test embed_documents with empty list"""
    with patch('tradingagents.llm_adapters.embeddings.OpenAI'):
        embeddings = OpenAIEmbeddings(api_key="test-key")
        result = embeddings.embed_documents([])
        assert result == []
        
    print("✅ embed_documents empty test passed")


# Test create_dashscope_embeddings
def test_create_dashscope_embeddings():
    """Test create_dashscope_embeddings helper"""
    with patch('tradingagents.llm_adapters.embeddings.OpenAI') as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "dash-key"}):
            embeddings = create_dashscope_embeddings()
            
            assert embeddings.api_key == "dash-key"
            assert embeddings.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
            assert embeddings.model == "text-embedding-v3"
            
    print("✅ create_dashscope_embeddings test passed")


def test_create_dashscope_embeddings_custom_key():
    """Test create_dashscope_embeddings with explicit api_key"""
    with patch('tradingagents.llm_adapters.embeddings.OpenAI') as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        
        embeddings = create_dashscope_embeddings(api_key="custom-key")
        
        assert embeddings.api_key == "custom-key"
        
    print("✅ create_dashscope_embeddings custom key test passed")


# Test embedding_text function
def test_embedding_text():
    """Test embedding_text helper function"""
    with patch('tradingagents.llm_adapters.embeddings.OpenAI') as mock_client_class:
        # Setup mock
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
        
        mock_instance = MagicMock()
        mock_instance.embeddings.create.return_value = mock_response
        mock_client_class.return_value = mock_instance
        
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-key"}):
            result = embedding_text("测试文本")
            
            assert result == [0.1, 0.2, 0.3]
            
    print("✅ embedding_text test passed")


# Run all tests
if __name__ == "__main__":
    print("Running embeddings module tests...")
    print("=" * 50)
    
    print("\n1. Testing OpenAIEmbeddings initialization:")
    test_openai_embeddings_init()
    
    print("\n2. Testing embed_query:")
    test_embed_query()
    test_embed_query_empty()
    
    print("\n3. Testing embed_documents:")
    test_embed_documents()
    test_embed_documents_empty()
    test_embed_documents_batch_processing()
    test_embed_documents_batch_size_limit()
    
    print("\n4. Testing create_dashscope_embeddings:")
    test_create_dashscope_embeddings()
    test_create_dashscope_embeddings_custom_key()
    
    print("\n5. Testing embedding_text:")
    test_embedding_text()
    
    print("\n" + "=" * 50)
    print("All embeddings tests completed!")
