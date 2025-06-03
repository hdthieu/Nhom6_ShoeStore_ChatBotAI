import os
from pinecone import Pinecone as PineconeSDK, ServerlessSpec
from langchain_pinecone import Pinecone
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.schema import Document
from db_loader import get_all_products
from dotenv import load_dotenv

load_dotenv()
def search_vector_with_filter(query, llm, filter_dict=None, top_k=20):
    from langchain.chains import RetrievalQA

    vectorstore = init_vector_store()

    retriever = vectorstore.as_retriever(search_kwargs={
        "k": top_k,
        "filter": filter_dict or {}
    })

    qa_chain = RetrievalQA.from_chain_type(llm=llm, retriever=retriever)
    response = qa_chain.run(query)
    return response

def init_vector_store():
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME") or "shoestore-index"

    if not PINECONE_API_KEY:
        raise ValueError("Missing PINECONE_API_KEY in environment variables.")

    pc = PineconeSDK(api_key=PINECONE_API_KEY)

    if PINECONE_INDEX_NAME not in pc.list_indexes().names():
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=768, 
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )

    index = pc.Index(PINECONE_INDEX_NAME)
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/msmarco-distilbert-base-v4")
    vectorstore = Pinecone(index=index, embedding=embeddings, text_key="text")

    df = get_all_products()
    documents = []
    for _, row in df.iterrows():
        content = f"Sản phẩm: {row['productName']}. Mô tả: {row['description']}. Giá: {row['price']}đ. Thương hiệu: {row['brand']}. Loại: {row['category']}."
        metadata = {
            "source": "SQL",
            "brand": row["brand"],
            "category": row["category"],
            "price": row["price"]
        }
        documents.append(Document(page_content=content, metadata=metadata))


    vectorstore.add_documents(documents)
    return vectorstore
