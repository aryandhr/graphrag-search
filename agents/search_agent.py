import os
import json
from datetime import datetime
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI
import logging
from service.schema import DatabaseSchema
from service.structured import StructuredService
from service.unstructured import UnstructuredService

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

REASONING_PROMPT_PATH = os.path.join(os.path.dirname(__file__), 'system_prompts', 'reasoning_prompt.txt')
with open(REASONING_PROMPT_PATH, 'r') as f:
    REASONING_PROMPT = f.read()

class PlanStep(BaseModel):
    reasoning: str
    expected_result: str

class Plan(BaseModel):
    steps: list[PlanStep]
    final_result: str | None

class ModelWithToolsResponse(BaseModel):
    tool_call: str | None
    tool_call_arguments: dict | None
    response: str | None

class SearchAgent:
    def __init__(self, query: str, unstructured_search_service: UnstructuredService, structured_search_service: StructuredService, user_email: str):
        self.unstructured_search_service = unstructured_search_service
        self.unstructured_search_service.initialize_neo4j_local_context(user_email)
        self.structured_search_service = structured_search_service
        
        self.user_email = user_email
        self.client = client

        self.query = query
        self.reasoning_model_history = [
            {"role": "system", "content": REASONING_PROMPT},
            {"role": "user", "content": self.query}
        ]

        self.max_plans = 10
        self.tools = []
        self.tool_classifications = {}
        
        self._load_tools()

    def _load_tools(self):
        """Load tools from the tools directory and classify them."""
        tools_dir = os.path.join(os.path.dirname(__file__), 'tools')
        
        for filename in os.listdir(tools_dir):
            if filename.endswith('.json'):
                tool_path = os.path.join(tools_dir, filename)
                try:
                    with open(tool_path, 'r') as f:
                        tool_def = json.load(f)
                    
                    # Store the tool classification
                    tool_name = tool_def.get('name')
                    tool_type = tool_def.get('tool_type')
                    
                    if tool_name:
                        self.tool_classifications[tool_name] = tool_type
                        self.tools.append(tool_def)
                        
                except (json.JSONDecodeError, FileNotFoundError) as e:
                    logging.warning(f"Failed to load tool from {filename}: {e}")

    def get_tool_type(self, tool_name: str) -> str:
        """Get the classification type for a given tool call."""
        return self.tool_classifications.get(tool_name)

    def _truncate_content(self, content: str, max_length: int = 2000) -> str:
        """Helper method to consistently truncate content to prevent token overflow."""
        if len(content) > max_length:
            return content[:max_length] + "... [truncated]"
        return content

    def update_reasoning_model_history(self, response, response_type: str) -> None:
        if response_type == "function_call":
            result_str = json.dumps(response)
            truncated_result = self._truncate_content(result_str)
            self.reasoning_model_history.append({"role": "assistant", "content": "Tool result: " + truncated_result})
        elif response_type == "message":
            response_str = str(response)
            truncated_response = self._truncate_content(response_str)
            self.reasoning_model_history.append({"role": "assistant", "content": truncated_response})

    def get_reasoning_model_history(self) -> str:
        return "\n".join([message["content"] for message in self.reasoning_model_history])

    async def unstructured_search(self, tool_name: str, tool_call_arguments: dict) -> str:
        if tool_name == "global_search":
            result = await self.unstructured_search_service.global_search(
                tool_call_arguments["query"], 
                tool_call_arguments["response_type"], 
                self.user_email
            )
        elif tool_name == "local_search":
            result = await self.unstructured_search_service.local_search(
                tool_call_arguments["query"], 
                tool_call_arguments["response_type"], 
                self.user_email
            )
        elif tool_name == "run_cypher_query":
            result = self.unstructured_search_service.run_cypher_query(tool_call_arguments["query"])
        else:
            result = {"error": f"Unknown function: {tool_name}"}
        return result
    
    def structured_search(self, tool_name: str, tool_call_arguments: dict) -> str:
        if tool_name == "get_all_tables":
            result = self.structured_search_service.list_tables()
        elif tool_name == "get_table_schema":
            result = self.structured_search_service.get_table_columns(tool_call_arguments["table_name"])
        elif tool_name == "run_sql_query":
            result = self.structured_search_service.custom_query(tool_call_arguments["query"])
        else:
            result = {"error": f"Unknown function: {tool_name}"}
        return result
    
    async def call_tool(self, tool_name: str, tool_call_arguments: dict) -> str:
        tool_type = self.get_tool_type(tool_name)
        
        if tool_type == "structured":
            return self.structured_search(tool_name, tool_call_arguments)
        elif tool_type == "unstructured":
            return await self.unstructured_search(tool_name, tool_call_arguments)
        else:
            return "No tool call"

    def reasoning_model(self):
        response = self.client.responses.create(
            model="o4-mini",
            reasoning={
                "effort": "medium",
                "summary": "detailed"
            },
            input=self.reasoning_model_history,
            tools=self.tools,
        )

        logger.info(f"Reasoning: {response.output}")

        summary = response.output[0]
        reasoning_response = response.output[1]

        return summary, reasoning_response
    
    async def run(self):
        for _ in range(self.max_plans):
            summary, reasoning_response = self.reasoning_model()

            if summary.summary:
                logger.info(f"Reasoning response: {summary.summary}")
            else:
                logger.info("No reasoning provided")

            logger.info(f"Reasoning output: {reasoning_response}")

            if reasoning_response.type == "function_call":
                tool_result = await self.call_tool(reasoning_response.name, json.loads(reasoning_response.arguments))
                logger.info(f"Tool result: {tool_result}")
                self.update_reasoning_model_history(tool_result, reasoning_response.type)

            elif reasoning_response.type == "message":
                logger.info(f"Reasoning response: {reasoning_response.content[0].text}")
                self.update_reasoning_model_history(reasoning_response.content[0].text, reasoning_response.type)

            evaluation = self.evaluate_sufficiency(self.get_reasoning_model_history())
            if evaluation.get("sufficient") and evaluation.get("final_answer"):
                logger.info("✅ Sufficient information gathered. Returning final answer.")
                return evaluation["final_answer"]


    def evaluate_sufficiency(self, reasoning_model_history: str) -> dict:
        """Evaluate if the gathered information is sufficient to answer the original query."""
        evaluation_prompt = f"""
        Original user query: "{self.query}"
        
        Information gathered so far: {reasoning_model_history}
        
        Evaluate if the gathered information is sufficient to provide a complete and accurate answer to the original user query.
        
        IMPORTANT CRITERIA:
        - General descriptions or explanations of how to query data are NOT sufficient for data retrieval requests
        - Only consider it sufficient if you have concrete data that directly answers the user's question
        
        Respond with JSON in this format:
        {{
            "sufficient": true/false,
            "reasoning": "explanation of why the information is or isn't sufficient",
            "final_answer": "if sufficient, provide a comprehensive answer to the original query, otherwise null"
        }}
        """
        
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at evaluating if information sufficiently answers user queries. Be strict - if the user asks for specific data, you must have actual data results, not just descriptions. Respond only with valid JSON."},
                {"role": "user", "content": evaluation_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        try:
            import json
            return json.loads(response.choices[0].message.content)
        except:
            return {"sufficient": False, "reasoning": "Failed to evaluate", "final_answer": None}

