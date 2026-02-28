"""
Tests for tradingagents.searcher.vector_store module
"""

import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock

from tradingagents.searcher import (
    VectorStore,
    SearchResult,
    create_vector_store,
    DEFAULT_CHROMA_PERSIST_DIR,
)


# Test SearchResult dataclass
def test_search_result():
    """Test SearchResult dataclass"""
    result = SearchResult(
        id="doc_001",
        content="test content",
        score=0.95,
        metadata={"key": "value"}
    )
    assert result.id == "doc_001"
    assert result.content == "test content"
    assert result.score == 0.95
    assert result.metadata == {"key": "value"}
    
    print("✅ SearchResult dataclass test passed")


# Test VectorStore initialization
def test_vector_store_init_default():
    """Test VectorStore initialization with default settings"""
    with patch('tradingagents.searcher.vector_store.get_default_chromadb_client') as mock_get_client:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_get_client.return_value = mock_client
        
        with patch('tradingagents.searcher.vector_store.create_dashscope_embeddings') as mock_emb:
            mock_embeddings = MagicMock()
            mock_emb.return_value = mock_embeddings
            
            store = VectorStore(collection_name="test_collection")
            
            assert store.collection_name == "test_collection"
            mock_get_client.assert_called_once()
            
    print("✅ VectorStore init default test passed")


def test_vector_store_init_with_persist_directory():
    """Test VectorStore initialization with persist directory"""
    temp_dir = tempfile.mkdtemp()
    
    try:
        with patch('tradingagents.searcher.vector_store.get_persistent_chromadb_client') as mock_get_client:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.create_collection.return_value = mock_collection
            mock_client.get_collection.side_effect = Exception("not found")
            mock_get_client.return_value = mock_client
            
            with patch('tradingagents.searcher.vector_store.create_dashscope_embeddings') as mock_emb:
                mock_embeddings = MagicMock()
                mock_emb.return_value = mock_embeddings
                
                store = VectorStore(
                    collection_name="test_collection",
                    persist_directory=temp_dir
                )
                
                assert store.collection_name == "test_collection"
                mock_get_client.assert_called_once_with(temp_dir)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        
    print("✅ VectorStore init with persist directory test passed")


def test_vector_store_init_memory_mode():
    """Test VectorStore initialization with memory mode (empty string)"""
    with patch('tradingagents.searcher.vector_store.get_optimal_chromadb_client') as mock_get_client:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_get_client.return_value = mock_client
        
        with patch('tradingagents.searcher.vector_store.create_dashscope_embeddings') as mock_emb:
            mock_embeddings = MagicMock()
            mock_emb.return_value = mock_embeddings
            
            store = VectorStore(
                collection_name="test_collection",
                persist_directory=""
            )
            
            mock_get_client.assert_called_once()
            
    print("✅ VectorStore init memory mode test passed")


# Test insert method
def test_insert_single_document():
    """Test inserting a single document"""
    with patch('tradingagents.searcher.vector_store.get_default_chromadb_client') as mock_get_client:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_get_client.return_value = mock_client
        
        with patch('tradingagents.searcher.vector_store.create_dashscope_embeddings') as mock_emb:
            mock_embeddings = MagicMock()
            mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]
            mock_emb.return_value = mock_embeddings
            
            store = VectorStore(collection_name="test")
            
            doc_id = store.insert(
                content="test content",
                metadata={"key": "value"},
                doc_id="custom_id"
            )
            
            assert doc_id == "custom_id"
            mock_collection.add.assert_called_once()
            call_args = mock_collection.add.call_args
            assert call_args[1]["ids"] == ["custom_id"]
            assert call_args[1]["documents"] == ["test content"]
            assert call_args[1]["metadatas"] == [{"key": "value"}]
            
    print("✅ Insert single document test passed")


def test_insert_auto_generate_id():
    """Test inserting a document with auto-generated ID"""
    with patch('tradingagents.searcher.vector_store.get_default_chromadb_client') as mock_get_client:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_get_client.return_value = mock_client
        
        with patch('tradingagents.searcher.vector_store.create_dashscope_embeddings') as mock_emb:
            mock_embeddings = MagicMock()
            mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]
            mock_emb.return_value = mock_embeddings
            
            store = VectorStore(collection_name="test")
            
            doc_id = store.insert(content="test content")
            
            assert doc_id.startswith("doc_")
            assert len(doc_id) == 16  # "doc_" + 12 hex chars
            
    print("✅ Insert auto-generate ID test passed")


def test_insert_empty_content():
    """Test inserting empty content raises error"""
    with patch('tradingagents.searcher.vector_store.get_default_chromadb_client'):
        with patch('tradingagents.searcher.vector_store.create_dashscope_embeddings') as mock_emb:
            mock_emb.return_value = MagicMock()
            
            store = VectorStore(collection_name="test")
            
            try:
                store.insert(content="")
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "不能为空" in str(e)
                
    print("✅ Insert empty content test passed")


# Test add_documents method
def test_add_documents_batch():
    """Test adding multiple documents"""
    with patch('tradingagents.searcher.vector_store.get_default_chromadb_client') as mock_get_client:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_get_client.return_value = mock_client
        
        with patch('tradingagents.searcher.vector_store.create_dashscope_embeddings') as mock_emb:
            mock_embeddings = MagicMock()
            mock_embeddings.embed_documents.return_value = [
                [0.1, 0.2],
                [0.3, 0.4],
            ]
            mock_emb.return_value = mock_embeddings
            
            store = VectorStore(collection_name="test")
            
            docs = [
                {"content": "doc1", "metadata": {"type": "A"}},
                {"content": "doc2", "metadata": {"type": "B"}},
            ]
            ids = store.add_documents(docs)
            
            assert len(ids) == 2
            mock_collection.add.assert_called_once()
            
    print("✅ Add documents batch test passed")


def test_add_documents_empty_list():
    """Test adding empty list returns empty"""
    with patch('tradingagents.searcher.vector_store.get_default_chromadb_client'):
        with patch('tradingagents.searcher.vector_store.create_dashscope_embeddings') as mock_emb:
            mock_emb.return_value = MagicMock()
            
            store = VectorStore(collection_name="test")
            
            ids = store.add_documents([])
            assert ids == []
            
    print("✅ Add documents empty list test passed")


# Test search method
def test_search_basic():
    """Test basic search functionality"""
    with patch('tradingagents.searcher.vector_store.get_default_chromadb_client') as mock_get_client:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        
        # Setup mock query response
        mock_collection.query.return_value = {
            "ids": [["doc1", "doc2"]],
            "documents": [["content1", "content2"]],
            "metadatas": [[{"k1": "v1"}, {"k2": "v2"}]],
            "distances": [[0.1, 0.3]],
        }
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_get_client.return_value = mock_client
        
        with patch('tradingagents.searcher.vector_store.create_dashscope_embeddings') as mock_emb:
            mock_embeddings = MagicMock()
            mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]
            mock_emb.return_value = mock_embeddings
            
            store = VectorStore(collection_name="test")
            
            results = store.search("query", top_k=2)
            
            assert len(results) == 2
            assert results[0].id == "doc1"
            assert results[0].content == "content1"
            assert results[0].score == 0.9  # 1.0 - 0.1
            assert results[1].id == "doc2"
            
    print("✅ Search basic test passed")


def test_search_with_filter():
    """Test search with metadata filter"""
    with patch('tradingagents.searcher.vector_store.get_default_chromadb_client') as mock_get_client:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        
        mock_collection.query.return_value = {
            "ids": [["doc1"]],
            "documents": [["content1"]],
            "metadatas": [[{"type": "news"}]],
            "distances": [[0.1]],
        }
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_get_client.return_value = mock_client
        
        with patch('tradingagents.searcher.vector_store.create_dashscope_embeddings') as mock_emb:
            mock_embeddings = MagicMock()
            mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]
            mock_emb.return_value = mock_embeddings
            
            store = VectorStore(collection_name="test")
            
            results = store.search(
                "query",
                top_k=5,
                filter_metadata={"type": "news"}
            )
            
            # Verify filter was passed
            call_args = mock_collection.query.call_args
            assert call_args[1]["where"] == {"type": "news"}
            
    print("✅ Search with filter test passed")


def test_search_empty_query():
    """Test search with empty query returns empty list"""
    with patch('tradingagents.searcher.vector_store.get_default_chromadb_client'):
        with patch('tradingagents.searcher.vector_store.create_dashscope_embeddings') as mock_emb:
            mock_emb.return_value = MagicMock()
            
            store = VectorStore(collection_name="test")
            
            results = store.search("")
            assert results == []
            
    print("✅ Search empty query test passed")


# Test delete method
def test_delete_single():
    """Test deleting a single document"""
    with patch('tradingagents.searcher.vector_store.get_default_chromadb_client') as mock_get_client:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_get_client.return_value = mock_client
        
        with patch('tradingagents.searcher.vector_store.create_dashscope_embeddings') as mock_emb:
            mock_emb.return_value = MagicMock()
            
            store = VectorStore(collection_name="test")
            
            result = store.delete("doc1")
            
            assert result is True
            mock_collection.delete.assert_called_once_with(ids=["doc1"])
            
    print("✅ Delete single test passed")


def test_delete_multiple():
    """Test deleting multiple documents"""
    with patch('tradingagents.searcher.vector_store.get_default_chromadb_client') as mock_get_client:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_get_client.return_value = mock_client
        
        with patch('tradingagents.searcher.vector_store.create_dashscope_embeddings') as mock_emb:
            mock_emb.return_value = MagicMock()
            
            store = VectorStore(collection_name="test")
            
            result = store.delete(["doc1", "doc2", "doc3"])
            
            assert result is True
            mock_collection.delete.assert_called_once_with(ids=["doc1", "doc2", "doc3"])
            
    print("✅ Delete multiple test passed")


def test_delete_failure():
    """Test delete when collection raises error"""
    with patch('tradingagents.searcher.vector_store.get_default_chromadb_client') as mock_get_client:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.delete.side_effect = Exception("Delete error")
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_get_client.return_value = mock_client
        
        with patch('tradingagents.searcher.vector_store.create_dashscope_embeddings') as mock_emb:
            mock_emb.return_value = MagicMock()
            
            store = VectorStore(collection_name="test")
            
            result = store.delete("doc1")
            
            assert result is False
            
    print("✅ Delete failure test passed")


# Test get method
def test_get_document():
    """Test getting a document by ID"""
    with patch('tradingagents.searcher.vector_store.get_default_chromadb_client') as mock_get_client:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        
        mock_collection.get.return_value = {
            "ids": ["doc1"],
            "documents": ["content1"],
            "metadatas": [{"key": "value"}],
        }
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_get_client.return_value = mock_client
        
        with patch('tradingagents.searcher.vector_store.create_dashscope_embeddings') as mock_emb:
            mock_emb.return_value = MagicMock()
            
            store = VectorStore(collection_name="test")
            
            result = store.get("doc1")
            
            assert result is not None
            assert result.id == "doc1"
            assert result.content == "content1"
            assert result.metadata == {"key": "value"}
            
    print("✅ Get document test passed")


def test_get_nonexistent():
    """Test getting a non-existent document"""
    with patch('tradingagents.searcher.vector_store.get_default_chromadb_client') as mock_get_client:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        
        mock_collection.get.return_value = {"ids": []}
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_get_client.return_value = mock_client
        
        with patch('tradingagents.searcher.vector_store.create_dashscope_embeddings') as mock_emb:
            mock_emb.return_value = MagicMock()
            
            store = VectorStore(collection_name="test")
            
            result = store.get("nonexistent")
            
            assert result is None
            
    print("✅ Get nonexistent test passed")


# Test count method
def test_count():
    """Test counting documents"""
    with patch('tradingagents.searcher.vector_store.get_default_chromadb_client') as mock_get_client:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 42
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_get_client.return_value = mock_client
        
        with patch('tradingagents.searcher.vector_store.create_dashscope_embeddings') as mock_emb:
            mock_emb.return_value = MagicMock()
            
            store = VectorStore(collection_name="test")
            
            count = store.count()
            
            assert count == 42
            
    print("✅ Count test passed")


# Test clear method
def test_clear():
    """Test clearing collection"""
    with patch('tradingagents.searcher.vector_store.get_default_chromadb_client') as mock_get_client:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_get_client.return_value = mock_client
        
        with patch('tradingagents.searcher.vector_store.create_dashscope_embeddings') as mock_emb:
            mock_emb.return_value = MagicMock()
            
            store = VectorStore(collection_name="test")
            
            result = store.clear()
            
            assert result is True
            mock_client.delete_collection.assert_called_once_with(name="test")
            
    print("✅ Clear test passed")


def test_clear_failure():
    """Test clear when delete fails"""
    with patch('tradingagents.searcher.vector_store.get_default_chromadb_client') as mock_get_client:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.delete_collection.side_effect = Exception("Delete error")
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_get_client.return_value = mock_client
        
        with patch('tradingagents.searcher.vector_store.create_dashscope_embeddings') as mock_emb:
            mock_emb.return_value = MagicMock()
            
            store = VectorStore(collection_name="test")
            
            result = store.clear()
            
            assert result is False
            
    print("✅ Clear failure test passed")


# Test list_all method
def test_list_all():
    """Test listing all documents"""
    with patch('tradingagents.searcher.vector_store.get_default_chromadb_client') as mock_get_client:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        
        mock_collection.get.return_value = {
            "ids": ["doc1", "doc2"],
            "documents": ["content1", "content2"],
            "metadatas": [{"k1": "v1"}, {"k2": "v2"}],
        }
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_get_client.return_value = mock_client
        
        with patch('tradingagents.searcher.vector_store.create_dashscope_embeddings') as mock_emb:
            mock_emb.return_value = MagicMock()
            
            store = VectorStore(collection_name="test")
            
            results = store.list_all(limit=10)
            
            assert len(results) == 2
            assert results[0].id == "doc1"
            assert results[1].id == "doc2"
            
    print("✅ List all test passed")


# Test create_vector_store helper
def test_create_vector_store():
    """Test create_vector_store helper function"""
    with patch('tradingagents.searcher.vector_store.get_default_chromadb_client') as mock_get_client:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_get_client.return_value = mock_client
        
        with patch('tradingagents.searcher.vector_store.create_dashscope_embeddings') as mock_emb:
            mock_embeddings = MagicMock()
            mock_emb.return_value = mock_embeddings
            
            store = create_vector_store(
                collection_name="test",
                use_dashscope=True,
                persist_directory=None
            )
            
            assert store.collection_name == "test"
            mock_emb.assert_called_once()
            
    print("✅ Create vector store test passed")


def test_create_vector_store_openai():
    """Test create_vector_store with OpenAI embeddings"""
    with patch('tradingagents.searcher.vector_store.get_default_chromadb_client') as mock_get_client:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_get_client.return_value = mock_client
        
        with patch('tradingagents.searcher.vector_store.OpenAIEmbeddings') as mock_emb_class:
            mock_embeddings = MagicMock()
            mock_emb_class.return_value = mock_embeddings
            
            store = create_vector_store(
                collection_name="test",
                use_dashscope=False
            )
            
            assert store.collection_name == "test"
            mock_emb_class.assert_called_once()
            
    print("✅ Create vector store OpenAI test passed")


# Test default chroma persist dir
def test_default_chroma_persist_dir():
    """Test that DEFAULT_CHROMA_PERSIST_DIR is set correctly"""
    assert DEFAULT_CHROMA_PERSIST_DIR is not None
    assert "data" in DEFAULT_CHROMA_PERSIST_DIR
    assert "chromadb" in DEFAULT_CHROMA_PERSIST_DIR
    
    print(f"✅ Default persist dir: {DEFAULT_CHROMA_PERSIST_DIR}")


# Run all tests
if __name__ == "__main__":
    print("Running vector_store module tests...")
    print("=" * 50)
    
    print("\n1. Testing SearchResult:")
    test_search_result()
    
    print("\n2. Testing VectorStore initialization:")
    test_vector_store_init_default()
    test_vector_store_init_with_persist_directory()
    test_vector_store_init_memory_mode()
    
    print("\n3. Testing insert:")
    test_insert_single_document()
    test_insert_auto_generate_id()
    test_insert_empty_content()
    
    print("\n4. Testing add_documents:")
    test_add_documents_batch()
    test_add_documents_empty_list()
    
    print("\n5. Testing search:")
    test_search_basic()
    test_search_with_filter()
    test_search_empty_query()
    
    print("\n6. Testing delete:")
    test_delete_single()
    test_delete_multiple()
    test_delete_failure()
    
    print("\n7. Testing get:")
    test_get_document()
    test_get_nonexistent()
    
    print("\n8. Testing count and clear:")
    test_count()
    test_clear()
    test_clear_failure()
    
    print("\n9. Testing list_all:")
    test_list_all()
    
    print("\n10. Testing create_vector_store:")
    test_create_vector_store()
    test_create_vector_store_openai()
    
    print("\n11. Testing default config:")
    test_default_chroma_persist_dir()
    
    print("\n" + "=" * 50)
    print("All vector_store tests completed!")
