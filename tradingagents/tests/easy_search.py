from tradingagents.searcher import VectorStore

store = VectorStore(collection_name="stock_basic")
a = store.search('000001', top_k=10)