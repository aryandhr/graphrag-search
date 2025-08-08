from collections.abc import AsyncGenerator
from typing import Any

from pydantic import validate_call

from graphrag.callbacks.noop_query_callbacks import NoopQueryCallbacks
from graphrag.callbacks.query_callbacks import QueryCallbacks
from graphrag.config.models.graph_rag_config import GraphRagConfig
from graphrag.logger.print_progress import PrintProgressLogger
from graphrag.utils.api import load_search_prompt

from .neo4j_global_search_factory import get_neo4j_global_search_engine

logger = PrintProgressLogger("")


@validate_call(config={"arbitrary_types_allowed": True})
async def neo4j_global_search(
    config: GraphRagConfig,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    community_level: int | None,
    dynamic_community_selection: bool,
    response_type: str,
    query: str,
    callbacks: list[QueryCallbacks] | None = None,
    user_email: str = None,
) -> tuple[
    str | dict[str, Any] | list[dict[str, Any]],
    str | list[dict] | dict[str, dict],
]:
    """Perform a global search using Neo4j as the data source.

    Parameters
    ----------
    - config (GraphRagConfig): A graphrag configuration (from settings.yaml)
    - neo4j_uri (str): Neo4j database URI
    - neo4j_user (str): Neo4j username
    - neo4j_password (str): Neo4j password
    - community_level (int): The community level to search at (not used in Neo4j version)
    - dynamic_community_selection (bool): Enable dynamic community selection
    - response_type (str): The type of response to return.
    - query (str): The user query to search for.
    - callbacks (list[QueryCallbacks]): Query callbacks
    - user_email (str): User email to filter data by

    Returns
    -------
    tuple: (response, context_data)
    """
    callbacks = callbacks or []
    full_response = ""
    context_data = {}

    def on_context(context: Any) -> None:
        nonlocal context_data
        context_data = context

    local_callbacks = NoopQueryCallbacks()
    local_callbacks.on_context = on_context
    callbacks.append(local_callbacks)

    async for chunk in neo4j_global_search_streaming(
        config=config,
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        community_level=community_level,
        dynamic_community_selection=dynamic_community_selection,
        response_type=response_type,
        query=query,
        callbacks=callbacks,
        user_email=user_email,
    ):
        full_response += chunk
    return full_response, context_data


@validate_call(config={"arbitrary_types_allowed": True})
def neo4j_global_search_streaming(
    config: GraphRagConfig,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    community_level: int | None,
    dynamic_community_selection: bool,
    response_type: str,
    query: str,
    callbacks: list[QueryCallbacks] | None = None,
    user_email: str = None,
) -> AsyncGenerator:
    """Perform a global search using Neo4j and return results via a generator.

    Parameters
    ----------
    - config (GraphRagConfig): A graphrag configuration (from settings.yaml)
    - neo4j_uri (str): Neo4j database URI
    - neo4j_user (str): Neo4j username
    - neo4j_password (str): Neo4j password
    - community_level (int): The community level to search at (not used in Neo4j version)
    - dynamic_community_selection (bool): Enable dynamic community selection
    - response_type (str): The type of response to return.
    - query (str): The user query to search for.
    - callbacks (list[QueryCallbacks]): Query callbacks
    - user_email (str): User email to filter data by

    Returns
    -------
    AsyncGenerator: Streaming response chunks
    """
    
    # Load prompts from config
    map_prompt = load_search_prompt(config.root_dir, config.global_search.map_prompt)
    reduce_prompt = load_search_prompt(
        config.root_dir, config.global_search.reduce_prompt
    )
    knowledge_prompt = load_search_prompt(
        config.root_dir, config.global_search.knowledge_prompt
    )

    # Create Neo4j-based search engine
    search_engine = get_neo4j_global_search_engine(
        config=config,
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        response_type=response_type,
        dynamic_community_selection=dynamic_community_selection,
        map_system_prompt=map_prompt,
        reduce_system_prompt=reduce_prompt,
        general_knowledge_inclusion_prompt=knowledge_prompt,
        callbacks=callbacks,
        user_email=user_email,
    )
    
    return search_engine.stream_search(query=query) 