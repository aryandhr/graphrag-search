# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Neo4j-based Global Search Context Builder for GraphRAG."""

import logging
import random
from typing import Any, cast

import pandas as pd
import tiktoken
from neo4j import GraphDatabase

from graphrag.query.context_builder.builders import ContextBuilderResult
from graphrag.query.context_builder.conversation_history import ConversationHistory
from graphrag.query.structured_search.base import GlobalContextBuilder
from graphrag.query.llm.text_utils import num_tokens

log = logging.getLogger(__name__)

NO_COMMUNITY_RECORDS_WARNING: str = (
    "Warning: No community records added when building community context."
)


class Neo4jGlobalCommunityContext(GlobalContextBuilder):
    """Neo4j-based GlobalSearch community context builder."""

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        token_encoder: tiktoken.Encoding | None = None,
        random_state: int = 86,
        user_email: str = None,
    ):
        """Initialize the Neo4j context builder.
        
        Args:
            neo4j_uri: Neo4j database URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            token_encoder: Token encoder for counting tokens
            random_state: Random seed for reproducibility
            user_email: User email to filter data by
        """
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.token_encoder = token_encoder
        self.random_state = random_state
        self.user_email = user_email

    def close(self):
        """Close the Neo4j driver connection."""
        if self.driver:
            self.driver.close()

    async def build_context(
        self,
        query: str,
        conversation_history: ConversationHistory | None = None,
        use_community_summary: bool = True,
        column_delimiter: str = "|",
        shuffle_data: bool = True,
        include_community_rank: bool = False,
        min_community_rank: int = 0,
        community_rank_name: str = "rank",
        include_community_weight: bool = True,
        community_weight_name: str = "occurrence",
        normalize_community_weight: bool = True,
        max_context_tokens: int = 8000,
        context_name: str = "Reports",
        conversation_history_user_turns_only: bool = True,
        conversation_history_max_turns: int | None = 5,
        **kwargs: Any,
    ) -> ContextBuilderResult:
        """Prepare batches of community report data from Neo4j as context data for global search."""
        
        conversation_history_context = ""
        final_context_data = {}
        llm_calls, prompt_tokens, output_tokens = 0, 0, 0
        
        if conversation_history:
            # build conversation history context
            (
                conversation_history_context,
                conversation_history_context_data,
            ) = conversation_history.build_context(
                include_user_turns_only=conversation_history_user_turns_only,
                max_qa_turns=conversation_history_max_turns,
                column_delimiter=column_delimiter,
                max_context_tokens=max_context_tokens,
                recency_bias=False,
            )
            if conversation_history_context != "":
                final_context_data = conversation_history_context_data

        # Get community reports from Neo4j
        community_reports = self._get_community_reports_from_neo4j(
            query=query,
            include_community_rank=include_community_rank,
            min_community_rank=min_community_rank,
            include_community_weight=include_community_weight,
            community_weight_name=community_weight_name,
            normalize_community_weight=normalize_community_weight,
        )

        # Build context using the same logic as the original build_community_context
        community_context, community_context_data = self._build_community_context(
            community_reports=community_reports,
            use_community_summary=use_community_summary,
            column_delimiter=column_delimiter,
            shuffle_data=shuffle_data,
            include_community_rank=include_community_rank,
            community_rank_name=community_rank_name,
            include_community_weight=include_community_weight,
            community_weight_name=community_weight_name,
            max_context_tokens=max_context_tokens,
            context_name=context_name,
        )

        # Prepare context_prefix based on whether conversation_history_context exists
        context_prefix = (
            f"{conversation_history_context}\n\n"
            if conversation_history_context
            else ""
        )

        final_context = (
            [f"{context_prefix}{context}" for context in community_context]
            if isinstance(community_context, list)
            else f"{context_prefix}{community_context}"
        )

        # Update the final context data with the provided community_context_data
        final_context_data.update(community_context_data)

        return ContextBuilderResult(
            context_chunks=final_context,
            context_records=final_context_data,
            llm_calls=llm_calls,
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
        )

    def _get_community_reports_from_neo4j(
        self,
        query: str,
        include_community_rank: bool = False,
        min_community_rank: int = 0,
        include_community_weight: bool = True,
        community_weight_name: str = "occurrence",
        normalize_community_weight: bool = True,
    ) -> list[dict]:
        """Retrieve community reports from Neo4j database.
        
        This method queries the Neo4j database to get community reports that are
        relevant to the search query. It uses the following schema from the notebook:
        
        Nodes:
        - __Community__: Community nodes with properties like community (id), title, level, rank, etc.
        - __Entity__: Entity nodes connected to communities
        - __Chunk__: Text chunks connected to entities
        - Finding: Finding nodes (community reports) connected to communities
        
        Relationships:
        - HAS_FINDING: __Community__ -> Finding (community reports)
        - HAS_ENTITY: __Chunk__ -> __Entity__
        - IN_COMMUNITY: __Entity__ -> __Community__
        """
        
        # Extract query terms for relevance filtering
        query_terms = set(query.lower().split())
        
        with self.driver.session() as session:
            # Updated Cypher query to match GraphRAG schema more closely
            if self.user_email:
                cypher_query = """
                    MATCH (c:__Community__ {userEmail: $user_email})
                    OPTIONAL MATCH (c)-[:HAS_FINDING]->(finding:Finding)
                    OPTIONAL MATCH (e:__Entity__ {userEmail: $user_email})-[:IN_COMMUNITY]->(c)
                    OPTIONAL MATCH (chunk:__Chunk__ {userEmail: $user_email})-[:HAS_ENTITY]->(e)

                    WITH c, finding,
                        collect(DISTINCT e.name) as entity_names,
                        collect(DISTINCT e.description) as entity_descriptions,
                        collect(DISTINCT chunk.text) as chunk_texts,
                        collect(DISTINCT e.title) as entity_titles

                    RETURN {
                        id: c.community,
                        title: COALESCE(finding.summary, c.title),
                        summary: COALESCE(finding.summary, c.title, ""),
                        full_content: COALESCE(finding.full_content, finding.summary, c.title, ""),
                        entity_names: entity_names,
                        entity_descriptions: entity_descriptions,
                        chunk_texts: chunk_texts,
                        entity_titles: entity_titles,
                        finding_id: COALESCE(finding.id, ""),
                        level: COALESCE(c.level, 0),
                        rank: COALESCE(finding.rank, 0)
                    } as report
                    ORDER BY c.community
                """
                result = session.run(cypher_query, user_email=self.user_email)
            else:
                cypher_query = """
                    MATCH (c:__Community__)
                    OPTIONAL MATCH (c)-[:HAS_FINDING]->(finding:Finding)
                    OPTIONAL MATCH (e:__Entity__)-[:IN_COMMUNITY]->(c)
                    OPTIONAL MATCH (chunk:__Chunk__)-[:HAS_ENTITY]->(e)

                    WITH c, finding,
                        collect(DISTINCT e.name) as entity_names,
                        collect(DISTINCT e.description) as entity_descriptions,
                        collect(DISTINCT chunk.text) as chunk_texts,
                        collect(DISTINCT e.title) as entity_titles

                    RETURN {
                        id: c.community,
                        title: COALESCE(finding.summary, c.title),
                        summary: COALESCE(finding.summary, c.title, ""),
                        full_content: COALESCE(finding.full_content, finding.summary, c.title, ""),
                        entity_names: entity_names,
                        entity_descriptions: entity_descriptions,
                        chunk_texts: chunk_texts,
                        entity_titles: entity_titles,
                        finding_id: COALESCE(finding.id, ""),
                        level: COALESCE(c.level, 0),
                        rank: COALESCE(finding.rank, 0)
                    } as report
                    ORDER BY c.community
                """
                result = session.run(cypher_query)
            
            reports = [record["report"] for record in result]
            
            # Simple relevance filtering based on query terms
            if query_terms:
                relevant_reports = []
                for report in reports:
                    # Check if any query term appears in title, summary, or entity names
                    report_text = (
                        (report.get("title", "") + " " + 
                         report.get("summary", "") + " " + 
                         " ".join(report.get("entity_names", []))).lower()
                    )
                    
                    # Check for query term matches
                    if any(term in report_text for term in query_terms if len(term) > 2):
                        relevant_reports.append(report)
                
                # If we found relevant reports, use them; otherwise use all reports
                if relevant_reports:
                    reports = relevant_reports
            
            # Filter by minimum rank if specified
            if include_community_rank and min_community_rank > 0:
                reports = [
                    report for report in reports 
                    if report.get("rank") is not None and report["rank"] >= min_community_rank
                ]
            
            # Calculate community weights if requested
            if include_community_weight:
                reports = self._compute_community_weights_neo4j(
                    reports=reports,
                    weight_attribute=community_weight_name,
                    normalize=normalize_community_weight,
                )
            
            return reports

    def _compute_community_weights_neo4j(
        self,
        reports: list[dict],
        weight_attribute: str = "occurrence",
        normalize: bool = True,
    ) -> list[dict]:
        """Calculate community weights based on the number of entities and chunks in each community."""
        
        for report in reports:
            # Count unique entities and chunks in this community
            entity_count = len(set(report.get("entity_names", [])))
            chunk_count = len(set(report.get("chunk_texts", [])))
            
            # Weight based on both entity count and chunk count (similar to original GraphRAG)
            # This gives higher weight to communities with more entities and more content
            report[weight_attribute] = entity_count + (chunk_count * 0.1)
        
        if normalize and reports:
            # Normalize by max weight
            max_weight = max(report.get(weight_attribute, 0) for report in reports)
            if max_weight > 0:
                for report in reports:
                    report[weight_attribute] = report.get(weight_attribute, 0) / max_weight
        
        return reports

    def _build_community_context(
        self,
        community_reports: list[dict],
        use_community_summary: bool = True,
        column_delimiter: str = "|",
        shuffle_data: bool = True,
        include_community_rank: bool = False,
        community_rank_name: str = "rank",
        include_community_weight: bool = True,
        community_weight_name: str = "occurrence",
        max_context_tokens: int = 8000,
        context_name: str = "Reports",
    ) -> tuple[str | list[str], dict[str, pd.DataFrame]]:
        """Build community context from Neo4j reports using the same logic as the original."""
        
        def _is_included(report: dict) -> bool:
            # Include all reports that have some content
            return bool(report.get("summary") or report.get("full_content"))

        def _get_header() -> list[str]:
            header = ["id", "title"]
            if include_community_weight:
                header.append(community_weight_name)
            header.append("summary" if use_community_summary else "content")
            if include_community_rank:
                header.append(community_rank_name)
            return header

        def _report_context_text(report: dict) -> tuple[str, list[str]]:
            context: list[str] = [
                str(report.get("id", "")),
                str(report.get("title", "")),
            ]
            
            if include_community_weight:
                context.append(str(report.get(community_weight_name, 0)))
            
            # Use summary or full_content based on the flag
            content = report.get("summary", "") if use_community_summary else report.get("full_content", "")
            context.append(content)
            
            if include_community_rank:
                context.append(str(report.get("rank", 0)))
            
            result = column_delimiter.join(context) + "\n"
            return result, context

        selected_reports = [report for report in community_reports if _is_included(report)]

        if not selected_reports:
            log.warning(NO_COMMUNITY_RECORDS_WARNING)
            return ([], {})

        if shuffle_data:
            random.seed(self.random_state)
            random.shuffle(selected_reports)

        header = _get_header()
        
        all_context_text: list[str] = []
        all_context_records: list[pd.DataFrame] = []

        # batch variables
        batch_text: str = ""
        batch_tokens: int = 0
        batch_records: list[list[str]] = []

        def _init_batch() -> None:
            nonlocal batch_text, batch_tokens, batch_records
            batch_text = (
                f"-----{context_name}-----" + "\n" + column_delimiter.join(header) + "\n"
            )
            batch_tokens = num_tokens(batch_text, self.token_encoder)
            batch_records = []

        def _cut_batch() -> None:
            # convert the current context records to pandas dataframe and sort by weight and rank if exist
            record_df = self._convert_report_context_to_df(
                context_records=batch_records,
                header=header,
                weight_column=community_weight_name if include_community_weight else None,
                rank_column=community_rank_name if include_community_rank else None,
            )
            if len(record_df) == 0:
                return
            current_context_text = record_df.to_csv(index=False, sep=column_delimiter)
            if not all_context_text:
                current_context_text = f"-----{context_name}-----\n{current_context_text}"

            all_context_text.append(current_context_text)
            all_context_records.append(record_df)

        # initialize the first batch
        _init_batch()

        for i, report in enumerate(selected_reports):
            new_context_text, new_context = _report_context_text(report)
            new_tokens = num_tokens(new_context_text, self.token_encoder)

            if batch_tokens + new_tokens > max_context_tokens:
                # add the current batch to the context data and start a new batch
                _cut_batch()
                break  # Single batch mode for now

            # add current report to the current batch
            batch_text += new_context_text
            batch_tokens += new_tokens
            batch_records.append(new_context)

        # Extract the IDs from the current batch
        current_batch_ids = {record[0] for record in batch_records}

        # Extract the IDs from all previous batches in all_context_records
        existing_ids_sets = [set(record["id"].to_list()) for record in all_context_records]

        # Check if the current batch has been added
        if current_batch_ids not in existing_ids_sets:
            _cut_batch()

        if len(all_context_records) == 0:
            log.warning(NO_COMMUNITY_RECORDS_WARNING)
            return ([], {})
        
        log.info(f'all_context_records: {len(all_context_records)} records')

        return all_context_text, {
            context_name.lower(): pd.concat(all_context_records, ignore_index=True)
        }

    def _rank_report_context(
        self,
        report_df: pd.DataFrame,
        weight_column: str | None = "occurrence",
        rank_column: str | None = "rank",
    ) -> pd.DataFrame:
        """Sort report context by community weight and rank if exist."""
        rank_attributes: list[str] = []
        if weight_column and weight_column in report_df.columns:
            rank_attributes.append(weight_column)
            report_df[weight_column] = report_df[weight_column].astype(float)
        if rank_column and rank_column in report_df.columns:
            rank_attributes.append(rank_column)
            report_df[rank_column] = report_df[rank_column].astype(float)
        if len(rank_attributes) > 0:
            report_df.sort_values(by=rank_attributes, ascending=False, inplace=True)
        return report_df

    def _convert_report_context_to_df(
        self,
        context_records: list[list[str]],
        header: list[str],
        weight_column: str | None = None,
        rank_column: str | None = None,
    ) -> pd.DataFrame:
        """Convert report context records to pandas dataframe and sort by weight and rank if exist."""
        if len(context_records) == 0:
            return pd.DataFrame()

        record_df = pd.DataFrame(
            context_records,
            columns=cast("Any", header),
        )
        return self._rank_report_context(
            report_df=record_df,
            weight_column=weight_column,
            rank_column=rank_column,
        ) 