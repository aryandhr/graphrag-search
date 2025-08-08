import tiktoken
import asyncio
import nest_asyncio

from graphrag.callbacks.query_callbacks import QueryCallbacks
from graphrag.config.models.graph_rag_config import GraphRagConfig
from graphrag.language_model.manager import ModelManager
from graphrag.language_model.providers.fnllm.utils import (
    get_openai_model_parameters_from_config,
)
from graphrag.query.structured_search.local_search.search import LocalSearch
from graphrag.utils.api import load_search_prompt

from .neo4j_local_context import Neo4jLocalContext

class SyncContextBuilderWrapper:
    def __init__(self, async_context_builder):
        self._wrapped = async_context_builder
        self.token_encoder = getattr(async_context_builder, 'token_encoder', None)

    def build_context(self, *args, **kwargs):
        result = self._wrapped.build_context(*args, **kwargs)
        if asyncio.iscoroutine(result):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                nest_asyncio.apply()
                return loop.run_until_complete(result)
            else:
                return asyncio.run(result)
        return result

def get_neo4j_local_search_engine(
    config: GraphRagConfig,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    response_type: str,
    system_prompt: str | None = None,
    callbacks: list[QueryCallbacks] | None = None,
    user_email: str = None,
) -> LocalSearch:
    """Create a Neo4j-based local search engine.
    
    This function creates a local search engine that uses Neo4j as the data source
    instead of the default parquet files.
    
    Args:
        config: GraphRAG configuration
        neo4j_uri: Neo4j database URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
        response_type: Type of response to generate
        system_prompt: System prompt for the search
        callbacks: Query callbacks
        user_email: User email to filter data by
        
    Returns:
        LocalSearch engine configured to use Neo4j
    """
    
    # Get model settings from config
    model_settings = config.get_language_model_config(
        config.local_search.chat_model_id
    )

    model = ModelManager().get_or_create_chat_model(
        name="neo4j_local_search",
        model_type=model_settings.type,
        config=model_settings,
    )

    model_params = get_openai_model_parameters_from_config(model_settings)

    # Get encoding based on specified encoding name
    token_encoder = tiktoken.get_encoding(model_settings.encoding_model)
    ls_config = config.local_search

    # Create Neo4j context builder
    context_builder = Neo4jLocalContext(
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        user_email=user_email,
    )
    sync_context_builder = SyncContextBuilderWrapper(context_builder)

    return LocalSearch(
        model=model,
        context_builder=sync_context_builder,  # Use our sync wrapper
        token_encoder=token_encoder,
        system_prompt=system_prompt,
        response_type=response_type,
        callbacks=callbacks,
        model_params={**model_params},
        context_builder_params={
            "shuffle_data": True,
            "max_context_tokens": ls_config.max_context_tokens if hasattr(ls_config, 'max_context_tokens') else 8000,
            "context_name": "Chunks",
        },
    ) 