from langchain_community.document_loaders.web_base import WebBaseLoader
from typing import List
import os
from pilerbot.vectorstore.vstore import VectorStore
from langchain_community.utilities.arxiv import ArxivAPIWrapper
from langchain_community.tools.arxiv.tool import ArxivQueryRun
from langchain_community.tools.wikipedia.tool import WikipediaQueryRun
from langchain_community.utilities.wikipedia import WikipediaAPIWrapper
from datetime import datetime
from langchain_community.utilities.duckduckgo_search import DuckDuckGoSearchAPIWrapper
from langchain.tools import tool
from pydantic import Field, BaseModel
from langchain_community.utilities.bing_search import BingSearchAPIWrapper
from langchain_community.utilities.tavily_search import TavilySearchAPIWrapper



VECTORSTORE = os.path.join('pilerbot','Database','vectorstore')



import google.generativeai as genai
from pathlib import Path


class BingSchema(BaseModel):
    """schema For Bing Search"""
    snippet : str = Field(description='snippet of result')
    title : str= Field(description='title of result')
    link : str = Field(description='url of article')

class Vision:
    def __init__(self, model):
        self.config_file = os.path.join('pilerbot','Database', 'images')
        self.model=model



    def _input_image_setup(self,file_loc):
        if not (img := Path(file_loc)).exists():
            raise FileNotFoundError(f"Could not find image: {img}")
        image_parts = [
            {
                "mime_type": "image/png",
                "data": Path(file_loc).read_bytes()
                }
            ]
        return image_parts
    def _answer_image(self,context_or_sentence, image_content):
        input_prompt = """You are an image analyzer who takes in mathematical image converts them to latex equations. If there are no questions related to equations explain the problem or concept in the image."""
        model = genai.GenerativeModel(model_name=self.model)
        prompt_parts = [input_prompt,image_content[0],context_or_sentence]
        response = model.generate_content(prompt_parts)
        # response=model.generate_content([context_or_sentence,image_content],)

        # print(response)
        response.resolve()
        return response.text

    def vision_workfow(self,query : str )->str:

        for img in os.listdir(self.config_file):

            file_path=os.path.join(self.config_file,img)
        image_content=self._input_image_setup(file_path)
        result = self._answer_image(query,image_content=image_content)
        for img in os.listdir(self.config_file):
            os.remove(os.path.join(self.config_file,img))
        return result


def _create_vstore_on_webdocs(urls:List):

    docs=[WebBaseLoader(url).load() for url in urls]
    docs_list = [item for sublist in docs for item in sublist]
    vstoreobj=VectorStore(VECTORSTORE,docs_list)
    vstoreobj.makevectorembeddings()
    return vstoreobj

@tool('WebScraper', return_direct=False)

def retriever_on_web_data(urls:List, query):
    """If you have url, this tool can scrape the data and return."""
    if len(urls)<1:
        return "No link provided"
    
    elif len(urls)==1:
        return WebBaseLoader(urls[0]).load()
    vectorstoreobj = _create_vstore_on_webdocs(urls=urls)
    bm25=vectorstoreobj.makeretriever()[0]
    similarity=vectorstoreobj.makeretriever()[1]
    return [bm25.invoke(query),similarity.invoke(query)]


@tool('Arxiv', return_direct=False)

def arxiv(query: str)->str:
    "Only provides research papers based on query."
    arxiv_wrapper=ArxivAPIWrapper(top_k_results=2, doc_content_chars_max=20000)
    arxiv=ArxivQueryRun(api_wrapper=arxiv_wrapper)
    return arxiv.run(query)


@tool('Wikipedia', return_direct=False)
def wikipedia(query: str)->str:
    "A wrapper around Wikipedia."

    api_wrapper=WikipediaAPIWrapper(top_k_results=2, doc_content_chars_max=2000)
    wiki=WikipediaQueryRun(api_wrapper=api_wrapper)
    return wiki.run(query)

@tool('Calculator',return_direct=False)
def Calculator(expression : str):
    """Calculator takes variable `expression` as mathematical string and evaluates it for answer."""
    try:
        return eval(expression)
    except Exception as e:
        return e

# @tool('Visionn',return_direct=True)
def Vision_Model(model=None,query=None):

    """{model : str, query : str}\n analyzes image for answering."""

    if model is None:
        model="gemini-1.5-pro"
    visionobj=Vision(model=model)
    return visionobj.vision_workfow(query=query)


@tool("CurrentTime", return_direct=False)
def current_time(query : str = "What is current time?") -> str:
    """Returns the current time in a readable format."""
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")  # Format: YYYY-MM-DD HH:MM:SS



@tool("GenericSearch",return_direct=False)

def search_tool(query: str, max_results: int = 1):
    """Perform internet search. Max result = 1 gives 3 results"""
    ddg=DuckDuckGoSearchAPIWrapper()
    tavily=TavilySearchAPIWrapper(tavily_api_key=os.environ.get('TAVILY_API_KEY'))
    bing=BingSearchAPIWrapper(bing_subscription_key=os.environ.get('BING_API_KEY'),bing_search_url="https://api.bing.microsoft.com/v7.0/search")
    if max_results>3:
        max_results=1

    results={f'{i+1}':"" for i in range(max_results*2)}
    fields=['\ntitle','\nsources','\nmain_content']
    for key in results:
        results[key]={field:"" for field in fields}

    result_ddgs_news=ddg._ddgs_news(query=query, max_results=max_results)
    # result_tavily=tavily.results(query=query, max_results=max_results)
    result_bing=bing.results(query=query, num_results=max_results)
    count=0
    for i in range(len(result_bing)):
        current_ele_bing=BingSchema.parse_raw(str(result_bing[i]).replace("'",'"')).dict()
        count=count+1
        results[f'{count}']['\ntitle']=current_ele_bing['title']+'\n'
        results[f'{count}']['\nsources']=current_ele_bing['link']+'\n'
        results[f'{count}']['main_content']=current_ele_bing['snippet']+'\n'

    # for ele in result_tavily:
    #     count=count+1
    #     results[f'{count}']['\nsources']=ele['url']+'\n'
    #     results[f'{count}']['\nmain_content']=ele['content']+'\n'
    
    for ele in result_ddgs_news:
        count=count+1
        results[f'{count}']['\nsources']=ele['url']+'\n'
        results[f'{count}']['\nmain_content']=ele['body']+'\n'
        results[f'{count}']['\ntitle']=ele['title']+'\n'


    return results