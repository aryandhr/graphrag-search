import tiktoken

from graphrag.callbacks.query_callbacks import QueryCallbacks
from graphrag.config.models.graph_rag_config import GraphRagConfig
from graphrag.language_model.manager import ModelManager
from graphrag.language_model.providers.fnllm.utils import (
    get_openai_model_parameters_from_config,
)
from graphrag.query.structured_search.global_search.search import GlobalSearch
from graphrag.utils.api import load_search_prompt

from .neo4j_global_context import Neo4jGlobalCommunityContext


def get_neo4j_global_search_engine(
    config: GraphRagConfig,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    response_type: str,
    dynamic_community_selection: bool = False,
    map_system_prompt: str | None = None,
    reduce_system_prompt: str | None = None,
    general_knowledge_inclusion_prompt: str | None = None,
    callbacks: list[QueryCallbacks] | None = None,
    user_email: str = None,
) -> GlobalSearch:
    """Create a Neo4j-based global search engine.
    
    This function replaces the default get_global_search_engine to use
    Neo4j as the data source instead of the default parquet files.
    
    Args:
        config: GraphRAG configuration
        neo4j_uri: Neo4j database URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
        response_type: Type of response to generate
        dynamic_community_selection: Whether to use dynamic community selection
        map_system_prompt: Map system prompt
        reduce_system_prompt: Reduce system prompt
        general_knowledge_inclusion_prompt: Knowledge inclusion prompt
        callbacks: Query callbacks
        user_email: User email to filter data by
        
    Returns:
        GlobalSearch engine configured to use Neo4j
    """
    
    # Get model settings from config
    model_settings = config.get_language_model_config(
        config.global_search.chat_model_id
    )

    model = ModelManager().get_or_create_chat_model(
        name="neo4j_global_search",
        model_type=model_settings.type,
        config=model_settings,
    )

    model_params = get_openai_model_parameters_from_config(model_settings)

    # Get encoding based on specified encoding name
    token_encoder = tiktoken.get_encoding(model_settings.encoding_model)
    gs_config = config.global_search

    # Create Neo4j context builder
    context_builder = Neo4jGlobalCommunityContext(
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        token_encoder=token_encoder,
        user_email=user_email,
    )

    # Note: We don't need the dynamic community selection kwargs for Neo4j
    # since we're querying the database directly
    dynamic_community_selection_kwargs = {}
    if dynamic_community_selection:
        # For Neo4j, we could implement dynamic selection by modifying the Cypher query
        # For now, we'll use a simple approach
        dynamic_community_selection_kwargs.update({
            "model": model,
            "token_encoder": token_encoder,
            "keep_parent": gs_config.dynamic_search_keep_parent,
            "num_repeats": gs_config.dynamic_search_num_repeats,
            "use_summary": gs_config.dynamic_search_use_summary,
            "concurrent_coroutines": model_settings.concurrent_requests,
            "threshold": gs_config.dynamic_search_threshold,
            "max_level": gs_config.dynamic_search_max_level,
            "model_params": {**model_params},
        })

    return GlobalSearch(
        model=model,
        map_system_prompt=map_system_prompt,
        reduce_system_prompt=reduce_system_prompt,
        general_knowledge_inclusion_prompt=general_knowledge_inclusion_prompt,
        context_builder=context_builder,  # Use our Neo4j context builder
        token_encoder=token_encoder,
        max_data_tokens=gs_config.data_max_tokens,
        map_llm_params={**model_params},
        reduce_llm_params={**model_params},
        map_max_length=gs_config.map_max_length,
        reduce_max_length=gs_config.reduce_max_length,
        allow_general_knowledge=False,
        json_mode=False,
        context_builder_params={
            "use_community_summary": False,
            "shuffle_data": True,
            "include_community_rank": True,
            "min_community_rank": 0,
            "community_rank_name": "rank",
            "include_community_weight": True,
            "community_weight_name": "occurrence weight",
            "normalize_community_weight": True,
            "max_context_tokens": gs_config.max_context_tokens,
            "context_name": "Reports",
        },
        concurrent_coroutines=model_settings.concurrent_requests,
        response_type=response_type,
        callbacks=callbacks,
    ) 