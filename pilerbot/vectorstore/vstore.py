from langchain_community.document_loaders.directory import DirectoryLoader
from langchain_community.document_loaders.json_loader import JSONLoader
from langchain_community.document_loaders.merge import MergedDataLoader
from langchain_community.vectorstores.faiss import FAISS
from langchain_community.embeddings.google_palm import GooglePalmEmbeddings
# from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_community.embeddings.huggingface import HuggingFaceInferenceAPIEmbeddings,HuggingFaceEmbeddings,HuggingFaceInstructEmbeddings,HuggingFaceBgeEmbeddings

# from langchain_community.embeddings.voyageai import VoyageEmbeddings
# from langchain_community.embeddings.openai import OpenAIEmbeddings
from langchain_community.embeddings.gpt4all import GPT4AllEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.retrievers import BM25Retriever
import string
import time
from concurrent.futures import ThreadPoolExecutor
import math
import json
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import tempfile
from langchain_core.documents import Document
from typing import List
from dotenv import load_dotenv
load_dotenv()
import os

class VectorStore():
    def __init__(self, directory=None, documents:List[Document]=None):
        self.directory=directory
        self.vector_stores = None
        self.retriever = None
        self.documents=documents


         
    def makevectorembeddings(self):
        """Takes in list of documents"""

        # embedding_list=[HuggingFaceHubEmbeddings(huggingfacehub_api_token=st.secrets['HUGGINGFACEHUB_API_TOKEN']['api_token']),
        #                 GooglePalmEmbeddings(google_api_key=st.secrets['GOOGLE_GEMINI_API']['api_key']),
        #                 GPT4AllEmbeddings(model_name="all-MiniLM-L6-v2.gguf2.f16.gguf"),
        #                 HuggingFaceInferenceAPIEmbeddings(api_key=st.secrets['HUGGINGFACEHUB_API_TOKEN']['api_token'],model_name="BAAI/bge-base-en-v1.5")]
        embedding_list=[GooglePalmEmbeddings(google_api_key=os.environ.get('GOOGLE_GEMINI_API')),
                        HuggingFaceInferenceAPIEmbeddings(api_key=os.environ.get('HUGGINGFACEHUB_API_TOKEN'),model="jina-embeddings-v2-base-en")]
        
        text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            chunk_size=250,
            chunk_overlap=100,
            # length_function=len
        )
        chunks = text_splitter.split_documents(documents=self.documents)
        print('making vector embeddings')
        self.vector_stores=Chroma.from_documents(documents=chunks, embedding=embedding_list[1], collection_name=f"{time.time()}")
        print('made vector embeddings')
        return self.vector_stores
    def makeretriever(self):
        bm25_retriever=BM25Retriever.from_documents(self.documents)
        similarity_retriver=self.vector_stores.as_retriever(search_type="similarity_score_threshold",
        search_kwargs={'score_threshold': 0.5})
        self.retriever=(bm25_retriever,similarity_retriver)
        return self.retriever


