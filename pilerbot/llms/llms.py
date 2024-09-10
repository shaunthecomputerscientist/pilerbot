import os
from langchain_community.llms.huggingface_endpoint import HuggingFaceEndpoint
from langchain_community.chat_models.huggingface import ChatHuggingFace
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models.ollama import ChatOllama
from langchain_community.chat_models.anthropic import ChatAnthropic
from langchain_openai.chat_models import ChatOpenAI
from langchain_groq.chat_models import ChatGroq
from langchain_core.pydantic_v1 import BaseModel
from typing import Dict, List, Literal
from typing import Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage
import json
# GROQ_API_KEY="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"
from dotenv import load_dotenv
load_dotenv()
from langchain.output_parsers import PydanticOutputParser
# from pilerbot.langgraphworkflow import AnswerFormat



# from langchain_groq import ChatGroq
class GenerativeModel:
    def __init__(self, model_name: str, temperature: float, category: str,memory=True,prompttemplate=None):
        self.model_name = model_name
        self.temperature = temperature
        self.category = category
        self.model = self.get_llm()
        self.chat_history=[]
        self.memory=memory
        self.prompt=prompttemplate

    def get_llm(self):
        try:
            if "gemini" in self.category:
                llm = ChatGoogleGenerativeAI(
                    api_key=os.environ.get('GOOGLE_API_KEY'),
                    verbose=True,
                    model=self.model_name,
                    temperature=self.temperature
                )
            elif "huggingface" in self.category:
                llm = ChatHuggingFace(
                    llm=HuggingFaceEndpoint(repo_id=self.model_name,
                    huggingfacehub_api_token=os.environ.get('HUGGINGFACEHUB_API_TOKEN'),
                    temperature=self.temperature),

                    
                )
            elif "openai" in self.category:
                llm = ChatOpenAI(
                    model=self.model_name,
                    temperature=self.temperature,
                    api_key=os.environ.get('OPENAI_API_KEY')
                )
            elif "antrophic" in self.category:
                llm = ChatAnthropic(
                    model_name=self.model_name,
                    temperature=self.temperature,
                    anthropic_api_key=os.environ.get('ANTHROPIC_API_KEY')
                )
            elif "ollama" in self.category:
                llm = ChatOllama(
                    model=self.model_name,
                    temperature=self.temperature
                )
            elif "groq" in self.category:
                llm = ChatGroq(model_name=self.model_name,
                               temperature=self.temperature,
                               api_key=os.environ.get('GROQ_API_KEY'))
                
            else:
                raise ValueError(f"Unknown LLM category: {self.category}")
            return llm
        
        except Exception as e:
            raise e
    def generate_response(self,prompt,structured_output : Optional[BaseModel]=None):
        """Uses pipe and prompt template only when structure is provided"""
        self.chat_history.append({'role':'user','content':prompt})
        if structured_output is None:
            if self.memory:
                response=self.model.invoke(self.chat_history[[-3 if len(self.chat_history)>3 else -1][0]:])
            else:
                response=(self.model.invoke(prompt)).content
            self.chat_history.append({'role':'assistant','content':response})

        else:
            response_llm=self.model.with_structured_output(structured_output)
            # response_llm=self.model
            response_model = self.prompt | response_llm
            if self.memory:
                try:
                    response=response_model.invoke({"history":self.chat_history[[-2 if len(self.chat_history)>2 else -1][0]:],"question":prompt,"answer_schema":structured_output.schema_json()})

                except Exception as e:
                    print('LLM Error Occurred')
                    print(e)
                    return e
            else:
                response=  response_model.invoke({"history":'',"question":prompt,"answer_schema":structured_output.schema_json()})
            self.chat_history.append({'role':'assistant','content':response})
        print('------------------------------------------------------------')
        print(response)
        return str(response)
    
