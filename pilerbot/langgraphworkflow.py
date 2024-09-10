from typing import Literal, TypedDict, Annotated, List, Union
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, PromptTemplate, SystemMessagePromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import ToolNode
from typing import List, Dict, Any, Literal, TypedDict, Union
from langchain_core.pydantic_v1 import BaseModel, Field
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from langchain.tools import Tool
from langgraph.prebuilt.tool_node import ToolNode
from langgraph.prebuilt.tool_executor import ToolExecutor, ToolInvocation
from langgraph.prebuilt import ToolNode
import re
import json
from pilerbot.llms.llms import GenerativeModel
import ast, os
from dotenv import load_dotenv
load_dotenv()

# class CalculatorTool(BaseModel):
#     expression: str = Field(..., description="Mathematical expression")
# class WebScraper(BaseModel):
#   urls : List[str]
#   query : str
# class Websearchtool(BaseModel):
#   query : str
# # Define the state
class State(TypedDict):
    messages: List[Dict[str, str]]
    current_tool: str
    tool_input: str
    tool_output: str
    answer: str
    satisfied: bool

class langgraph_agent():
    def __init__(self,llm_evaluate,llm_router, tool_mapping, AnswerFormat):
        self.llm_evaluate : GenerativeModel=llm_evaluate
        self.llm_router : GenerativeModel=llm_router
        self.app = self.agentworkflow()
        self.fields = ['answer','satisfied','tool','tool_input']
        self.tool_mapping : dict= tool_mapping
        self.pydanticmodel : BaseModel = AnswerFormat


    def _genericparser(self, text: str, fields):
        """
        Parses input text according to provided fields, handling various formats and edge cases.
        
        Parameters:
        text (str): The input string to parse.
        fields (list): List of field names to extract.
        
        Returns:
        dict: A dictionary containing the parsed data for the specified fields.
        """
        
        def clean_text(text):
            """Normalizes and cleans the text for parsing."""
            return text.strip().replace("\\'", "'").replace('\\"', '"')
        
        def parse_json_like(text):
            """Attempts to parse a JSON-like string, handling various quote styles and nested quotes."""
            def replace_quotes(s):
                state = {'in_string': False, 'quote_char': None}
                result = []
                i = 0
                while i < len(s):
                    if s[i] in ['"', "'"]:
                        if not state['in_string']:
                            state['in_string'] = True
                            state['quote_char'] = s[i]
                            result.append('"')
                        elif state['quote_char'] == s[i]:
                            state['in_string'] = False
                            result.append('"')
                        else:
                            result.append(s[i])
                    elif s[i] == '\\' and i + 1 < len(s):
                        result.append(s[i:i+2])
                        i += 1
                    else:
                        result.append(s[i])
                    i += 1
                return ''.join(result)

            try:
                # Replace quotes while respecting nested structures
                processed_text = replace_quotes(text)
                # Now safely parse the modified string
                return json.loads(processed_text)
            except json.JSONDecodeError:
                print('json decoder error')
                return None

        def extract_field_value(text, field):
            """Extracts a single field value from the text."""
            patterns = [
                rf'{field}\s*=\s*"((?:[^"\\]|\\.)*)"|{field}\s*=\s*\'((?:[^\'\\]|\\.)*)', # Quoted values
                rf'{field}\s*=\s*(\{{[^}}]*\}})', # JSON-like values
                rf'{field}\s*=\s*([^\s]+)' # Unquoted values
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    value = next((g for g in match.groups() if g is not None), None)
                    if value:
                        # Try parsing as JSON if it looks like a dictionary or list
                        if (value.startswith('{') and value.endswith('}')) or (value.startswith('[') and value.endswith(']')):
                            try:
                                return parse_json_like(value)
                            except:
                                pass
                        return value.strip("'\"")
            return None

        def extract_fields(text, fields):
            """
            Extracts values for the specified fields, handling various formats and edge cases.
            """
            text = clean_text(text)
            
            # First, try to parse the entire text as a JSON-like string
            parsed_json = parse_json_like(text)
            if parsed_json:
                return {field: parsed_json.get(field) for field in fields}
            
            # If not a JSON-like string, process as key-value pairs
            return {field: extract_field_value(text, field) for field in fields}
        
        return extract_fields(text, fields)
    
    def gettoolinput(self, tool_input_as_string, tool_name)->Union[Dict,str]:
        tool_input = self._genericparser(tool_input_as_string, list((self.tool_mapping[tool_name]).args_schema.schema()['properties'].keys()))
        return tool_input

    
    def router(self,state: State) -> State:
        messages = state["messages"]
        prompt = messages[-1] if messages else ""
        # print(prompt)
        response = self.llm_router.generate_response(prompt, structured_output=self.pydanticmodel)
        # parsed_response = AnswerFormat.parse_raw(response)
        parsed_response = self._genericparser(response,fields=self.fields)
        print("router",parsed_response, type(parsed_response))

        current_state = state
        if parsed_response['tool'].lower()=="none" or parsed_response['satisfied']=='True':
            current_state["answer"] = parsed_response['answer']
            current_state["messages"].append({"role": "assistant", "content": state['answer']})
            current_state["satisfied"] = parsed_response['satisfied'] == "True"
            current_state["current_tool"] = parsed_response['tool']
            return current_state


        current_state["current_tool"] = parsed_response['tool']
        current_state["answer"] = parsed_response['answer']
        current_state["satisfied"] = parsed_response['satisfied'] == "True"
        current_state['tool_input'] = self.gettoolinput(str(parsed_response['tool_input']),current_state['current_tool'])
        print("router",current_state['tool_input'])
        current_state["messages"].append({"role": "assistant", "content": state['answer']})


        return current_state

    def checkroutercondition(self,state):
        print('insidecheckconditionrouter')
        if state["satisfied"]=='True' or state["satisfied"]==True:
            print("END 1st condition")

            return "end"
        elif state['current_tool'].lower()=='none':
            print("ENd 2nd condition")
            return "end"
        elif state['current_tool'].lower()=='none' and not state['satisfied']:
            print("end third condition")
            return "end"
        print('False')
        return "False"

# Define the tool execution function
    def execute_tool(self,state: State) -> State:
        tool_name = state["current_tool"]
        tool_input = state["tool_input"]
        tool=self.tool_mapping[tool_name]

        print("executor",tool_input,type(tool_input))
        result = tool.invoke(input=tool_input)

        print("executor",result)

        state["tool_output"] = str(result)
        state["messages"].append({"role": "tool", "content": state["tool_output"]})
        return state

    # Define the evaluation function
    def evaluate(self,state: State) -> Dict[str, Any]:
        print('inside evaluate')
        messages = state["messages"]
        tool_output = state["tool_output"]
        if state["satisfied"]:
            print('inside evaluate end')
            return END

        prompt = f"<PREVIOUSLY USED TOOL>:{state['current_tool']} \n<TOOL OUTPUT>: {tool_output}\n <ORIGINAL QUESTION>: {messages[0]['content']}"
        # print(prompt)
        print("before llm call")
        response = self.llm_evaluate.generate_response(prompt, structured_output=self.pydanticmodel)
        print("after llm call",response)
        parsed_response = self._genericparser(response,fields=self.fields)
        print(parsed_response)
        current_state = state

        if parsed_response['tool'].lower()=="none" or parsed_response['satisfied']=='True':
            current_state["answer"] = parsed_response['answer']
            current_state["messages"].append({"role": "assistant", "content": state['answer']})
            current_state["satisfied"] = parsed_response['satisfied'] == "True"
            current_state["current_tool"] = parsed_response['tool']
            return current_state

        current_state["current_tool"] = parsed_response['tool']
        current_state["answer"] = parsed_response['answer']
        current_state["satisfied"] = parsed_response['satisfied'] == "True"
        current_state['tool_input'] = self.gettoolinput(str(parsed_response['tool_input']),current_state['current_tool'])
        print("evaluator",current_state['tool_input'])
        current_state['messages'].append({"role": "assistant", "content": state["answer"]})
        return current_state
    
    def agentworkflow(self):
        # Create the graph
        workflow = StateGraph(State)
        # Add nodes
        workflow.add_node("router", self.router)
        workflow.add_node("execute_tool", self.execute_tool)
        workflow.add_node("evaluate", self.evaluate)
        # Add edges
        workflow.add_edge(START,"router")
        # workflow.add_edge("router", "execute_tool")
        workflow.add_edge("execute_tool", "evaluate")
        # We now add a conditional edge


        workflow.add_conditional_edges(
            "router",
            self.checkroutercondition,
            {
                "end": END,
                "False": "execute_tool",
            },

        )
        workflow.add_conditional_edges(
            "evaluate",
            self.checkroutercondition,
            {
                # If `tools`, then we call the tool node.
                "end": END,
                # Otherwise we finish.
                "False": "execute_tool",
            }
        )

        workflow.set_entry_point("router")

        # Compile the graph
        app = workflow.compile()

        return app
    def initiate_agent(self,query:str):
        def clean_string(text: str):
            replacements = {
                ord("'"): '',      # Replace single quotes with double quotes
                ord("\\"): "",      # Remove backslashes
                ord("“"): '"',      # Optional: Replace smart quotes with regular quotes
                ord("”"): '"',
                ord('"'):""      # Optional: Replace smart quotes with regular quotes
                # Add other problematic characters to replace here if needed
            }
            
            return text.translate(replacements)

        new_query=clean_string(str(query))
        initial_state = State(
            messages=[{"role": "user", "content": new_query}],
            current_tool="",
            tool_input="",
            tool_output="",
            answer="",
            satisfied=False
        )
        response = self.app.invoke(initial_state)
        print(f'agent response {response}')
        return response["messages"][-1]['content']
    

def answermodel(tool_names: List[str],tools):
    class AnswerFormat(BaseModel):
        answer: str = Field(..., description="Generate answer here from all the data you have.")
        satisfied: Literal["True", "False"] = Field(..., description="Return <True> to finalize answer. Else return False. If <True> put tool as None.")
        tool: str = Field(..., description=f"Choose a tool from {[(tool.name, tool.args_schema.schema()['description']) for tool in tools]}. If not needed, set it to 'None'. If you know the answer, do not use tools.")
        tool_input: Union[Dict, str] = Field(..., description=f"Description of each tool's input : {[(tool.name,tool.args_schema.schema()['properties']) for tool in tools]}. Provide a dictionary for tool input or 'query':'None' if no input is needed.")

        @staticmethod
        def validate_tool_name(value: str):
            """Ensure the tool is either in the list or 'None'."""
            if value not in tool_names:
                raise ValueError(f"Invalid tool name: {value}. Must be one of {tool_names}.")
            return value

        @staticmethod
        def validate_tool_input(tool: str, tool_input: Union[Dict, str]):
            """Validate that tool_input is provided only when a tool is selected."""
            if tool != 'None' and not isinstance(tool_input, dict):
                raise ValueError(f"Tool input must be a dictionary when tool is {tool}.")
            return tool_input

    return AnswerFormat

def promptformatter(router_prompt,system_prompt):
        system_message_1 = router_prompt
        system_message_2 = system_prompt
        input_variables = ['question', 'history', 'answer_schema']
        template = """\nQUESTION: {question},\n
                        CHAT HISTORY: {history},
                        SCHEMA : {answer_schema}"""
        # Create a new HumanMessagePromptTemplate with the modified prompt
        human_message_template = HumanMessagePromptTemplate(prompt=PromptTemplate(input_variables=input_variables, template=template))
        system_message_template_1 = SystemMessagePromptTemplate(prompt=PromptTemplate(template=system_message_1))
        system_message_template_2 = SystemMessagePromptTemplate(prompt=PromptTemplate(template=system_message_2))
        router_prompt = ChatPromptTemplate.from_messages(
            [human_message_template],
            [system_message_template_1],
        )
        evaluator_prompt = ChatPromptTemplate.from_messages(
            [human_message_template],
            [system_message_template_2],
        )

        return evaluator_prompt, router_prompt

def agent_utilities(tools:list,system_prompt,router_prompt):
    tool_mapping={}
    for tool in tools:
        tool_mapping[tool.name]=tool
    tool_names=list(tool_mapping.keys())+['None']

    AnswerFormat = answermodel(tool_names=tool_names,tools=tools)
    llm_router = (os.environ.get('llm_router_model'),os.environ.get('llm_router_category'))
    llm_evaluate = (os.environ.get('llm_evaluate_model'),os.environ.get('llm_evaluate_category'))
    routermodel,routercategory=llm_router
    evaluate_model,evaluate_category=llm_evaluate
    piler_prompt,router_prompt = promptformatter(system_prompt=system_prompt,router_prompt=router_prompt)
    llm_router = GenerativeModel(model_name=routermodel, temperature=0.5, category=routercategory, prompttemplate=router_prompt)
    llm_evaluate = GenerativeModel(model_name=evaluate_model, temperature=0.5, category=evaluate_category, prompttemplate = piler_prompt)
    return llm_evaluate,llm_router, AnswerFormat, tool_mapping