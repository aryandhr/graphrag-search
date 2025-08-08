import pandas as pd
import inspect
import decimal
import datetime
import uuid
from openai import OpenAI
import os
import numpy as np
from dotenv import load_dotenv

load_dotenv()

def make_json_serializable(obj):
    """Convert objects to JSON serializable format"""
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    elif isinstance(obj, pd.Series):
        return obj.to_dict()
    elif isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(v) for v in obj]
    else:
        return obj
    
def get_function_schema(function):
    """Get the schema for a function"""
    my_obj =  {
        "type": "function",
        "function": {
            "name": function.__name__,
            "description": function.__doc__,
        }
    }

    sig = inspect.signature(function)
    print("Parameters:")
    for name, param in sig.parameters.items():
        print(f"  {name}: {param}")
    print(my_obj)

def format_result(result):
    def convert(obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        elif isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, pd.DataFrame):
            return obj.to_dict('records')  # Convert DataFrame to list of dictionaries
        elif isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert(i) for i in obj]
        else:
            return obj
    return convert(result)

if __name__ == "__main__":
    print(get_function_schema(make_json_serializable))

def embed(text, model="text-embedding-3-small"):
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    if not openai_client:
        raise ValueError("OpenAI API key is not set")
    
    response = openai_client.embeddings.create(
        input=[text],
        model=model
    )
    return response.data[0].embedding

def cosine_similarity(a, b):
    if not a or not b:
        return 0.0
    if isinstance(a, list):
        a = np.array(a, dtype=np.float32)
    if isinstance(b, list):
        b = np.array(b, dtype=np.float32)
    if not isinstance(a, np.ndarray) or not isinstance(b, np.ndarray):
        raise ValueError("Input must be numpy arrays")
    
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def label_document_type(document_titles, structured_search_service):
    if not structured_search_service:
        raise ValueError("Structured search service is not set")
    if not document_titles:
        raise ValueError("Document titles are not set")
    
    table_names = set()
    document_types = {}

    if structured_search_service and hasattr(structured_search_service, "schema"):
        try:
            table_names = set(t.lower() for t in structured_search_service.schema.list_tables())
        except Exception as e:
            raise ValueError(f"Could not fetch table names from schema: {e}")
    
    for document_title in document_titles:
        if document_title.lower() in table_names:
            document_types[document_title] = "Structured"
        else:
            document_types[document_title] = "Unstructured"
    
    return document_types