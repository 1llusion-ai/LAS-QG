import uuid
from typing import Optional, Any, Callable


class Neo4jClient:
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "password",
    ):
        try:
            from neo4j import GraphDatabase
        except ImportError:
            raise ImportError("neo4j 包未安装，请运行: pip install neo4j")

        self.uri = uri
        self.username = username
        self.password = password
        self._driver = None

    def _get_driver(self):
        if self._driver is None:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )
        return self._driver

    def close(self):
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def clear_graph(self, document_id: str = None) -> bool:
        driver = self._get_driver()
        with driver.session() as session:
            if document_id:
                cypher = """
                MATCH (n)
                WHERE n.doc_title = $document_id
                DETACH DELETE n
                """
                session.run(cypher, document_id=document_id)
            else:
                cypher = "MATCH (n) DETACH DELETE n"
                session.run(cypher)
        return True

    def create_vector_index(self, index_name: str = "chunk_vector", dimension: int = 1024) -> bool:
        driver = self._get_driver()
        with driver.session() as session:
            try:
                cypher = f"""
                CREATE VECTOR INDEX {index_name} IF NOT EXISTS
                FOR (c:Chunk) ON (c.embedding)
                OPTIONS {{indexConfig: {{
                    `vector.dimensions`: {dimension},
                    `vector.similarity_function`: 'cosine'
                }}}}
                """
                session.run(cypher)
                return True
            except Exception as e:
                print(f"创建向量索引失败: {e}")
                return False

    def save_kg_with_embedding(
        self,
        cypher_data: list,
        embed_func: Callable[[str], list[float]],
    ) -> dict:
        driver = self._get_driver()
        stats = {
            "chunks_created": 0,
            "entities_created": 0,
            "relations_created": 0,
            "mentions_created": 0,
            "embeddings_generated": 0,
            "errors": [],
        }

        chunk_list = []
        entity_set = set()
        relations_list = []
        chunk_entity_map = {}

        for item in cypher_data:
            try:
                if item.get("type") == "chunk":
                    chunk_key = item.get("chunk_key", "")
                    chunk_list.append({
                        "chunk_key": chunk_key,
                        "chunk_id": item.get("chunk_id", 0),
                        "doc_title": item.get("doc_title", ""),
                        "article": item.get("article", ""),
                        "source_text": item.get("source_text", ""),
                    })
                    chunk_entity_map[chunk_key] = set()

                elif item.get("type") == "entity":
                    entity_set.add(item.get("name", ""))

                elif item.get("type") == "relation":
                    chunk_key = f"{item.get('doc_title', '')}_{item.get('chunk_id', 0)}"
                    head = item.get("head", "")
                    tail = item.get("tail", "")
                    relations_list.append({
                        "head": head,
                        "tail": tail,
                        "relation_text": item.get("relation_text", ""),
                        "doc_title": item.get("doc_title", ""),
                        "article": item.get("article", ""),
                        "chunk_id": item.get("chunk_id", 0),
                        "chunk_key": chunk_key,
                    })
                    if chunk_key in chunk_entity_map:
                        chunk_entity_map[chunk_key].add(head)
                        chunk_entity_map[chunk_key].add(tail)

            except Exception as e:
                stats["errors"].append(f"处理数据时出错: {e}")

        with driver.session() as session:
            for chunk in chunk_list:
                try:
                    source_text = chunk.get("source_text", "")
                    embedding = None
                    if source_text and embed_func:
                        embedding = embed_func(source_text)
                        stats["embeddings_generated"] += 1

                    cypher = """
                    MERGE (c:Chunk {chunk_key: $chunk_key})
                    SET c.chunk_id = $chunk_id,
                        c.doc_title = $doc_title,
                        c.article = $article,
                        c.source_text = $source_text
                    """
                    params = {
                        "chunk_key": chunk.get("chunk_key", ""),
                        "chunk_id": chunk.get("chunk_id", 0),
                        "doc_title": chunk.get("doc_title", ""),
                        "article": chunk.get("article", ""),
                        "source_text": source_text,
                    }
                    if embedding:
                        cypher += ", c.embedding = $embedding"
                        params["embedding"] = embedding

                    session.run(cypher, **params)
                    stats["chunks_created"] += 1
                except Exception as e:
                    stats["errors"].append(f"创建Chunk失败: {e}")

            for entity_name in entity_set:
                try:
                    cypher = "MERGE (e:Entity {name: $name})"
                    session.run(cypher, name=entity_name)
                    stats["entities_created"] += 1
                except Exception as e:
                    stats["errors"].append(f"创建实体失败: {e}")

            for rel in relations_list:
                try:
                    cypher = """
                    MATCH (h:Entity {name: $head})
                    MATCH (t:Entity {name: $tail})
                    MERGE (h)-[r:RELATION]->(t)
                    SET r.relation_text = $relation_text,
                        r.doc_title = $doc_title,
                        r.article = $article,
                        r.chunk_id = $chunk_id
                    """
                    session.run(cypher, **rel)
                    stats["relations_created"] += 1
                except Exception as e:
                    stats["errors"].append(f"创建关系失败: {e}")

            for chunk_key, entities in chunk_entity_map.items():
                for entity_name in entities:
                    try:
                        cypher = """
                        MATCH (c:Chunk {chunk_key: $chunk_key})
                        MATCH (e:Entity {name: $entity_name})
                        MERGE (c)-[m:MENTIONS]->(e)
                        """
                        session.run(cypher, chunk_key=chunk_key, entity_name=entity_name)
                        stats["mentions_created"] += 1
                    except Exception as e:
                        stats["errors"].append(f"创建MENTIONS边失败: {e}")

        return stats

    def save_kg(self, cypher_data: list) -> dict:
        driver = self._get_driver()
        stats = {
            "chunks_created": 0,
            "entities_created": 0,
            "relations_created": 0,
            "mentions_created": 0,
            "errors": [],
        }

        chunk_list = []
        entity_set = set()
        relations_list = []
        chunk_entity_map = {}

        for item in cypher_data:
            try:
                if item.get("type") == "chunk":
                    chunk_key = item.get("chunk_key", "")
                    chunk_list.append({
                        "chunk_key": chunk_key,
                        "chunk_id": item.get("chunk_id", 0),
                        "doc_title": item.get("doc_title", ""),
                        "article": item.get("article", ""),
                        "source_text": item.get("source_text", ""),
                    })
                    chunk_entity_map[chunk_key] = set()

                elif item.get("type") == "entity":
                    entity_set.add(item.get("name", ""))

                elif item.get("type") == "relation":
                    chunk_key = f"{item.get('doc_title', '')}_{item.get('chunk_id', 0)}"
                    head = item.get("head", "")
                    tail = item.get("tail", "")
                    relations_list.append({
                        "head": head,
                        "tail": tail,
                        "relation_text": item.get("relation_text", ""),
                        "doc_title": item.get("doc_title", ""),
                        "article": item.get("article", ""),
                        "chunk_id": item.get("chunk_id", 0),
                    })
                    if chunk_key in chunk_entity_map:
                        chunk_entity_map[chunk_key].add(head)
                        chunk_entity_map[chunk_key].add(tail)

            except Exception as e:
                stats["errors"].append(f"处理数据时出错: {e}")

        with driver.session() as session:
            for chunk in chunk_list:
                try:
                    cypher = """
                    MERGE (c:Chunk {chunk_key: $chunk_key})
                    SET c.chunk_id = $chunk_id,
                        c.doc_title = $doc_title,
                        c.article = $article,
                        c.source_text = $source_text
                    """
                    session.run(cypher, **chunk)
                    stats["chunks_created"] += 1
                except Exception as e:
                    stats["errors"].append(f"创建Chunk失败: {e}")

            for entity_name in entity_set:
                try:
                    cypher = "MERGE (e:Entity {name: $name})"
                    session.run(cypher, name=entity_name)
                    stats["entities_created"] += 1
                except Exception as e:
                    stats["errors"].append(f"创建实体失败: {e}")

            for rel in relations_list:
                try:
                    cypher = """
                    MATCH (h:Entity {name: $head})
                    MATCH (t:Entity {name: $tail})
                    MERGE (h)-[r:RELATION]->(t)
                    SET r.relation_text = $relation_text,
                        r.doc_title = $doc_title,
                        r.article = $article,
                        r.chunk_id = $chunk_id
                    """
                    session.run(cypher, **rel)
                    stats["relations_created"] += 1
                except Exception as e:
                    stats["errors"].append(f"创建关系失败: {e}")

            for chunk_key, entities in chunk_entity_map.items():
                for entity_name in entities:
                    try:
                        cypher = """
                        MATCH (c:Chunk {chunk_key: $chunk_key})
                        MATCH (e:Entity {name: $entity_name})
                        MERGE (c)-[m:MENTIONS]->(e)
                        """
                        session.run(cypher, chunk_key=chunk_key, entity_name=entity_name)
                        stats["mentions_created"] += 1
                    except Exception as e:
                        stats["errors"].append(f"创建MENTIONS边失败: {e}")

        return stats

    def get_kg(self, document_id: str = None) -> list:
        driver = self._get_driver()
        results = []

        with driver.session() as session:
            if document_id:
                cypher = """
                MATCH (h)-[r:RELATION]->(t)
                WHERE r.doc_title = $document_id
                RETURN h.name as head, t.name as tail, r.relation_text as relation_text,
                       r.doc_title as doc_title, r.article as article, r.chunk_id as chunk_id
                """
                cursor = session.run(cypher, document_id=document_id)
            else:
                cypher = """
                MATCH (h)-[r:RELATION]->(t)
                RETURN h.name as head, t.name as tail, r.relation_text as relation_text,
                       r.doc_title as doc_title, r.article as article, r.chunk_id as chunk_id
                """
                cursor = session.run(cypher)

            for record in cursor:
                results.append({
                    "head": record.get("head", ""),
                    "tail": record.get("tail", ""),
                    "relation_text": record.get("relation_text", ""),
                    "doc_title": record.get("doc_title", ""),
                    "article": record.get("article", ""),
                    "chunk_id": record.get("chunk_id", 0),
                })

        return results

    def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list:
        driver = self._get_driver()
        results = []

        with driver.session() as session:
            cypher = """
            MATCH (c:Chunk)
            WHERE c.embedding IS NOT NULL
            WITH c, gds.similarity.cosine(c.embedding, $query_embedding) AS similarity
            RETURN c.chunk_key AS chunk_key, c.chunk_id AS chunk_id,
                   c.doc_title AS doc_title, c.article AS article,
                   c.source_text AS source_text, similarity
            ORDER BY similarity DESC
            LIMIT $top_k
            """
            try:
                cursor = session.run(cypher, query_embedding=query_embedding, top_k=top_k)
                for record in cursor:
                    results.append({
                        "chunk_key": record.get("chunk_key", ""),
                        "chunk_id": record.get("chunk_id", 0),
                        "doc_title": record.get("doc_title", ""),
                        "article": record.get("article", ""),
                        "source_text": record.get("source_text", ""),
                        "similarity": record.get("similarity", 0),
                    })
            except Exception as e:
                print(f"向量搜索失败: {e}")

        return results

    def expand_subgraph(self, chunk_key: str, hops: int = 1) -> dict:
        driver = self._get_driver()
        results = {
            "chunk": None,
            "entities": [],
            "relations": []
        }

        with driver.session() as session:
            cypher = """
            MATCH (c:Chunk {chunk_key: $chunk_key})
            OPTIONAL MATCH (e:Entity)-[r:RELATION]->(e2:Entity)
            WHERE r.chunk_id = c.chunk_id
            RETURN c, collect(DISTINCT e) AS entities, collect(DISTINCT r) AS relations
            """
            try:
                cursor = session.run(cypher, chunk_key=chunk_key)
                record = cursor.single()

                if record:
                    chunk_data = record.get("c")
                    if chunk_data:
                        results["chunk"] = {
                            "chunk_key": chunk_data.get("chunk_key", ""),
                            "chunk_id": chunk_data.get("chunk_id", 0),
                            "doc_title": chunk_data.get("doc_title", ""),
                            "article": chunk_data.get("article", ""),
                            "source_text": chunk_data.get("source_text", ""),
                        }

                    for e in record.get("entities", []):
                        if e:
                            results["entities"].append({
                                "name": e.get("name", ""),
                            })

                    for r in record.get("relations", []):
                        if r:
                            results["relations"].append({
                                "head": r.get("start_node").get("name", ""),
                                "tail": r.get("end_node").get("name", ""),
                                "relation_text": r.get("relation_text", ""),
                                "article": r.get("article", ""),
                            })
            except Exception as e:
                print(f"子图扩展失败: {e}")

        return results

    def get_stats(self) -> dict:
        driver = self._get_driver()
        stats = {"chunks": 0, "entities": 0, "relations": 0}

        with driver.session() as session:
            chunk_count = session.run("MATCH (c:Chunk) RETURN count(c) as count")
            stats["chunks"] = chunk_count.single().get("count", 0)

            entity_count = session.run("MATCH (e:Entity) RETURN count(e) as count")
            stats["entities"] = entity_count.single().get("count", 0)

            rel_count = session.run("MATCH ()-[r:RELATION]->() RETURN count(r) as count")
            stats["relations"] = rel_count.single().get("count", 0)

        return stats


def get_neo4j_client(
    uri: str = None,
    username: str = None,
    password: str = None,
) -> Neo4jClient:
    import os

    uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
    username = username or os.getenv("NEO4J_USERNAME", "neo4j")
    password = password or os.getenv("NEO4J_PASSWORD", "password")

    return Neo4jClient(uri=uri, username=username, password=password)
