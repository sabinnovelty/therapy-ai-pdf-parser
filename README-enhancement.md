Critical analysis of RAG architecture

Current architecture overview

Don't build a single monolithic RAG pipeline. Build a Semantic Router that directs traffic to specialized "Agents" or "Tools."

Stack:
Framework: LlamaIndex (v0.10+)
Vector DB: ChromaDB (PersistentClient)
Embeddings: OpenAI text-embedding-3-small
LLM: OpenAI gpt-4o-mini
PDF Parser: OpenAI Assistants API with file_search
Chunking: SentenceSplitter (1024 chars, 100 overlap)

Critical issues and limitations
1. PDF parsing — expensive and inefficient
Current approach:
Uses OpenAI Assistants API for every PDF
Creates/deletes assistants/threads per document
High latency (60–120s per document)
High cost (~$0.10–$0.30 per document)
Issues:
Overkill for simple text extraction
No caching of parsed content
No support for other formats (DOCX, HTML, etc.)
Single document → single Document object (no pre-chunking)
Recommendation:
# Better alternatives:1. **PyMuPDF (fitz)** - Fast, free, handles tables well2. **pdfplumber** - Excellent for tables and structured data3. **Unstructured.io** - Enterprise-grade, handles complex layouts4. **LlamaParse** - LlamaIndex's own parser (free tier available)



2. Chunking strategy — too simplistic
Current:
Fixed 1024-character chunks with 100 overlap
No semantic awareness
No respect for document structure (headers, sections, tables)
Issues:
Healthcare documents have structured sections
Tables may be split across chunks
No hierarchical chunking (parent-child relationships)
Recommendation:
# Use semantic chunking:from llama_index.core.node_parser import SemanticSplitterNodeParser# OR hierarchical chunking:from llama_index.core.node_parser import HierarchicalNodeParser# OR document-aware chunking:from llama_index.core.node_parser import MarkdownNodeParser  # if converting to markdown


3. Retrieval — basic and inefficient
Current:
Simple similarity search (similarity_top_k=5)
Post-filtering for plan_id (inefficient)
No reranking
No hybrid search (keyword + semantic)
Issues:
ChromaDB OR filter limitation forces post-filtering
No query expansion or rewriting
Fixed top-k may miss relevant docs
No diversity in results
Recommendation:
# Implement:1. **Reranking**: Cohere Rerank, Jina Reranker, or Cross-Encoder2. **Hybrid Search**: BM25 + Vector (ChromaDB supports this)3. **Query Expansion**: Generate multiple query variations4. **Reciprocal Rank Fusion**: Combine multiple retrieval strategies


4. Multi-tenancy filtering — inefficient
Current:
Filters by tenant_id, then post-filters by plan_id
ChromaDB doesn't support OR filters natively
May retrieve irrelevant docs before filtering
Issues:
Wastes compute on irrelevant embeddings
No pre-filtering optimization
Plan_id filtering happens after retrieval
Recommendation:
# Better approaches:1. **Separate collections per tenant** (if scale allows)2. **Composite metadata keys**: tenant_id + plan_id as single filter3. **Use Weaviate/Pinecone** - Better metadata filtering support4. **Pre-filter at query time** with better metadata structure


5. Answer generation — limited
Current:
Single-pass generation
No citation tracking
Arbitrary 10-sentence limit
No confidence scoring
Issues:
No verification of answer quality
No source attribution in answer
Truncation may cut important info
Recommendation:
# Implement:1. **Citation tracking**: Use LlamaIndex's citation features2. **Answer verification**: Cross-check with multiple sources3. **Confidence scoring**: Based on source similarity scores4. **Multi-step reasoning**: For complex queries



6. Vector database — scalability concerns
Current:
ChromaDB PersistentClient (local file-based)
Single collection for all tenants
No replication or backup strategy
Issues:
Not suitable for production scale
No horizontal scaling
Single point of failure
No cloud deployment option
Recommendation:
# Consider:1. **ChromaDB Server** - For multi-instance deployment2. **Pinecone** - Managed, scalable, better metadata filtering3. **Weaviate** - Self-hosted or cloud, excellent filtering4. **Qdrant** - High performance, good metadata support5. **Milvus** - Enterprise-grade, highly scalable


Recommended tool stack
Tier 1: Production-ready (recommended)
PDF Parsing:
LlamaParse (free tier: 1000 pages/month) or PyMuPDF
Unstructured.io (for complex documents)
Vector Database:
Pinecone (managed, excellent metadata filtering) or Weaviate Cloud
Qdrant Cloud (self-hosted option available)
Embeddings:
Keep text-embedding-3-small (cost-effective)
Consider Cohere Embed v3 (better for retrieval)
Reranking:
Cohere Rerank v3 or Jina Reranker v2
Chunking:
SemanticSplitterNodeParser or HierarchicalNodeParser
Tier 2: Cost-optimized
PDF Parsing:
PyMuPDF (fitz) — free, fast, good quality
Vector Database:
ChromaDB Server (self-hosted, better than PersistentClient)
Embeddings:
text-embedding-3-small (current choice is good)
Reranking:
Cross-Encoder models (self-hosted, free)
Tier 3: Enterprise
PDF Parsing:
Unstructured.io or Docugami
Vector Database:
Milvus or Weaviate Enterprise
Embeddings:
OpenAI text-embedding-3-large or Voyage AI
Reranking:
Cohere Rerank Enterprise



Architecture improvements
1. Enhanced retrieval pipeline
# Proposed retrieval flow:1. Query Rewriting/Expansion2. Hybrid Search (BM25 + Vector)3. Metadata Pre-filtering (tenant_id + plan_id)4. Reranking (top 20 → top 5)5. Answer Generation with Citations6. Answer Verification

2. Better chunking strategy
# For healthcare documents:1. Parse PDF → Markdown (preserve structure)2. Hierarchical chunking (sections → subsections)3. Table extraction → separate chunks4. Metadata enrichment (section titles, document type)

3. Caching layer
# Add caching for:1. Parsed PDF content (avoid re-parsing)2. Embeddings (if same content re-ingested)3. Query results (for common queries)4. LLM responses (with TTL)

4. Monitoring and evaluation
# Add:1. Retrieval metrics (precision, recall, MRR)2. Answer quality scores3. Latency tracking4. Cost tracking per query5. A/B testing framework

Specific code improvements
1. Replace PDF parser
# Use PyMuPDF instead:import fitz  # PyMuPDFasync def parse_pdf_to_docs(file_path: str, plan_id: str) -> List[Document]:    doc = fitz.open(file_path)    text_content = ""    for page in doc:        text_content += page.get_text("markdown")  # Preserves structure    doc.close()        # Now you can use MarkdownNodeParser for better chunking    document = Document(text=text_content, metadata={...})    return [document]

2. Implement reranking
from llama_index.postprocessor import CohereRerankreranker = CohereRerank(api_key=os.getenv("COHERE_API_KEY"), top_n=5)query_engine = index.as_query_engine(    similarity_top_k=20,  # Retrieve more    node_postprocessors=[reranker],  # Rerank to top 5    filters=filters_tenant)

3. Better metadata filtering
# Use composite filtering:filters = MetadataFilters(filters=[    ExactMatchFilter(key="tenant_id", value=tenant_id),    # Use AND logic: (plan_id="GLOBAL" OR plan_id=plan_id)    # This requires querying twice or using better DB])

4. Hybrid search (ChromaDB supports this)
# Enable keyword search alongside vector searchquery_engine = index.as_query_engine(    similarity_top_k=5,    filters=filters_tenant,    # Add keyword search if ChromaDB collection supports it)
Cost optimization
Current costs (estimated):
PDF Parsing: ~$0.20/document (Assistants API)
Embeddings: ~$0.0001/document (text-embedding-3-small)
LLM: ~$0.001/query (gpt-4o-mini)
With improvements:

PDF Parsing: $0 (PyMuPDF) or ~$0.01 (LlamaParse)
Embeddings: Same
LLM: Same
Reranking: ~$0.0001/query (Cohere)
Savings: ~95% on ingestion costs

Security considerations
Data isolation: Ensure tenant_id filtering is secure
Input validation: Sanitize file uploads
Rate limiting: Prevent abuse
Audit logging: Track all queries and uploads
Encryption: Encrypt stored documents and vectors
Next steps

Immediate (Week 1):
Replace OpenAI PDF parser with PyMuPDF
Add semantic chunking
Implement basic reranking

Short-term (Month 1):
Migrate to Pinecone/Weaviate for better filtering
Add hybrid search
Implement caching layer

Long-term (Quarter 1):
Add evaluation framework
Implement query expansion
Add monitoring dashboard
