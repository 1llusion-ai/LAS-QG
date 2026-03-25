import streamlit as st
from pathlib import Path
from datetime import datetime
import tempfile
import hashlib
import json
import os

from src.pipeline.parser import parse_document, detect_doc_type
from src.pipeline.cleaner import clean_text
from src.pipeline.chunker import chunk_document
from src.pipeline.extractor import extract_rules
from src.core.neo4j_client import get_neo4j_client
from src.core.config import get_global_config
from src.core.llm import SiliconFlowClient
from src.schemas.types import DifficultyLevel, DocumentChunk
from src.agents.question_agent import QuestionAgent


HASH_FILE = Path("data/uploaded_hashes.json")


def calculate_file_hash(file_content: bytes) -> str:
    return hashlib.md5(file_content).hexdigest()


def load_uploaded_hashes() -> set:
    if HASH_FILE.exists():
        with open(HASH_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_uploaded_hash(file_hash: str):
    hashes = load_uploaded_hashes()
    hashes.add(file_hash)
    HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HASH_FILE, "w", encoding="utf-8") as f:
        json.dump(list(hashes), f)


def is_file_uploaded(file_hash: str) -> bool:
    return file_hash in load_uploaded_hashes()


def validate_file(uploaded_file) -> tuple[bool, str]:
    if uploaded_file is None:
        return False, "请选择文件"

    if uploaded_file.size == 0:
        return False, "文件为空，请上传非空文件"

    if uploaded_file.size < 10:
        return False, "文件内容过少，请检查文件是否有效"

    file_content = uploaded_file.getvalue()
    if len(file_content.strip()) == 0:
        return False, "文件内容为空，请上传包含内容的文件"

    return True, ""


def init_llm():
    config = get_global_config()
    llm_config = config.llm

    api_key = os.getenv("SILICONFLOW_API_KEY") or llm_config.api_key
    base_url = llm_config.base_url or "https://api.siliconflow.cn/v1"

    if not api_key:
        st.error("未配置 API Key")
        return None

    try:
        return SiliconFlowClient(
            api_key=api_key,
            base_url=base_url,
            model=llm_config.model,
        )
    except Exception as e:
        st.error(f"LLM 初始化失败: {str(e)}")
        return None


def render_document_processing_section():
    st.header("📄 文档清洗切块与KG抽取")
    st.markdown("上传 txt、docx、pdf 文件，进行解析、清洗、切块和规则知识图谱抽取")

    config = get_global_config()

    col1, col2 = st.columns([2, 1])
    with col1:
        uploaded_file = st.file_uploader(
            "选择文档文件",
            type=["txt", "docx", "pdf"],
            key="doc_uploader",
            help="支持格式：TXT、DOCX、PDF",
        )
    with col2:
        st.write("&nbsp;")
        st.write("&nbsp;")
        with st.expander("切块设置"):
            chunk_size = st.number_input(
                "块大小（字符数）",
                min_value=100,
                max_value=2000,
                value=config.chunk.chunk_size,
                step=50,
                key="doc_chunk_size",
            )
            overlap = st.number_input(
                "重叠大小（字符数）",
                min_value=0,
                max_value=500,
                value=config.chunk.overlap,
                step=10,
                key="doc_overlap",
            )

    if uploaded_file is not None:
        is_valid, error_msg = validate_file(uploaded_file)
        if not is_valid:
            st.error(error_msg)
            return

        file_hash = calculate_file_hash(uploaded_file.getvalue())
        file_type = Path(uploaded_file.name).suffix.lower()

        if is_file_uploaded(file_hash):
            st.warning(f"⚠️ 文件 '{uploaded_file.name}' 已上传过，将覆盖之前的数据")

        st.success(f"文件已上传：{uploaded_file.name}")
        st.info(f"文件类型：{file_type}")

        doc_col1, doc_col2 = st.columns(2)
        with doc_col1:
            st.write("**文件名：**", uploaded_file.name)
        with doc_col2:
            st.write("**文件大小：**", f"{uploaded_file.size / 1024:.2f} KB")

        doc_tab1, doc_tab2, doc_tab3 = st.tabs(["📖 解析与清洗", "✂️ 切块", "🔍 KG抽取"])

        with doc_tab1:
            if st.button("解析并清洗文档", key="btn_parse_clean"):
                with st.spinner("正在解析和清洗文档..."):
                    try:
                        with tempfile.NamedTemporaryFile(
                            delete=False, suffix=file_type
                        ) as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_path = tmp_file.name

                        document = parse_document(tmp_path)
                        document.filename = uploaded_file.name
                        cleaned_content = clean_text(document.content)

                        if len(cleaned_content.strip()) == 0:
                            st.error("清洗后内容为空，请检查文档内容")
                            return

                        save_uploaded_hash(file_hash)

                        st.session_state["doc_document"] = document
                        st.session_state["doc_cleaned_content"] = cleaned_content

                        st.success("文档解析和清洗完成！")

                        with st.expander("查看原始内容（前1000字符）"):
                            st.text(document.content[:1000])

                        with st.expander("查看清洗后内容（前1000字符）"):
                            st.text(cleaned_content[:1000])

                        st.info(f"原始内容长度：{len(document.content)} 字符")
                        st.info(f"清洗后长度：{len(cleaned_content)} 字符")

                    except Exception as e:
                        st.error(f"处理文档时出错：{str(e)}")

        with doc_tab2:
            if "doc_cleaned_content" in st.session_state:
                if st.button("切块", key="btn_chunk"):
                    with st.spinner("正在切块..."):
                        try:
                            document = st.session_state["doc_document"]
                            document.content = st.session_state["doc_cleaned_content"]

                            chunks = chunk_document(document, chunk_size, overlap)
                            st.session_state["doc_chunks"] = chunks

                            st.success(f"切块完成！共 {len(chunks)} 个块")

                            for i, chunk in enumerate(chunks[:5]):
                                article_no = chunk.metadata.get("article_no", "")
                                with st.expander(f"块 {i+1}（{len(chunk.content)} 字符）- {article_no}"):
                                    st.text(chunk.content)

                            if len(chunks) > 5:
                                st.info(f"还有 {len(chunks) - 5} 个块未显示")

                        except Exception as e:
                            st.error(f"切块时出错：{str(e)}")
            else:
                st.info("请先完成文档解析和清洗")

        with doc_tab3:
            if "doc_chunks" in st.session_state:
                if st.button("抽取规则知识图谱", key="btn_extract_kg"):
                    try:
                        llm = init_llm()
                        if llm is None:
                            return

                        document = st.session_state["doc_document"]
                        chunks = st.session_state["doc_chunks"]

                        export_dir = Path("data/exports")
                        export_dir.mkdir(parents=True, exist_ok=True)
                        export_file = export_dir / f"kg_{document.id}.txt"
                        json_file = export_dir / f"kg_{document.id}.json"

                        all_rules = []

                        with open(export_file, "w", encoding="utf-8") as f:
                            f.write(f"规则知识图谱导出\n")
                            f.write(f"文档ID: {document.id}\n")
                            f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write(f"总块数: {len(chunks)}\n")
                            f.write(f"{'='*60}\n\n")

                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        def write_chunk_progress(current: int, total: int, chunk: "DocumentChunk", result: dict):
                            article_no = chunk.metadata.get("article_no", "未知")
                            status_text.text(f"正在处理 chunk {current}/{total}，来源：{article_no}")

                            all_rules.extend(result.get('rules', []))

                            with open(export_file, "a", encoding="utf-8") as f:
                                f.write(f"\n{'='*60}\n")
                                f.write(f"Chunk {current}/{total} - 来源: {article_no}\n")
                                f.write(f"{'='*60}\n\n")

                                f.write(f"【三元组】{len(result.get('rules', []))} 个\n")
                                for r in result.get('rules', []):
                                    f.write(json.dumps({
                                        "head": r.get("head", ""),
                                        "relation": r.get("relation", ""),
                                        "tail": r.get("tail", ""),
                                        "doc_title": r.get("doc_title", ""),
                                        "article": r.get("article", ""),
                                        "chunk_id": r.get("chunk_id", 0),
                                        "source_text": r.get("source_text", "")
                                    }, ensure_ascii=False, indent=2))
                                    f.write("\n\n")

                            progress_bar.progress(current / total)

                        with st.spinner("正在抽取规则知识图谱..."):
                            doc_title = Path(document.filename).stem
                            rule_kg = extract_rules(
                                document.id, 
                                chunks, 
                                llm, 
                                progress_callback=write_chunk_progress, 
                                doc_title=doc_title
                            )

                        with open(json_file, "w", encoding="utf-8") as f:
                            json.dump({"document_id": document.id, "rules": all_rules}, f, ensure_ascii=False, indent=2)

                        st.session_state["doc_rule_kg"] = rule_kg
                        st.session_state["doc_kg_json_file"] = str(json_file)

                        progress_bar.empty()
                        status_text.empty()
                        st.success(f"已导出到: {export_file}")
                        st.info(f"共抽取：{len(rule_kg.rules)} 条三元组")

                        with st.spinner("正在存入 Neo4j 知识图谱..."):
                            try:
                                neo4j_client = get_neo4j_client()
                                neo4j_client.create_vector_index()
                                neo4j_client.create_fulltext_index()

                                cypher_data = []
                                for i, chunk in enumerate(chunks):
                                    chunk_key = f"{doc_title}_{i}"
                                    cypher_data.append({
                                        "type": "chunk",
                                        "chunk_key": chunk_key,
                                        "chunk_id": i,
                                        "doc_title": doc_title,
                                        "article": chunk.metadata.get("article_no", ""),
                                        "source_text": chunk.content,
                                    })

                                for rule in rule_kg.rules:
                                    cypher_data.append({
                                        "type": "entity",
                                        "name": rule.head,
                                    })
                                    cypher_data.append({
                                        "type": "entity",
                                        "name": rule.tail,
                                    })
                                    cypher_data.append({
                                        "type": "relation",
                                        "head": rule.head,
                                        "tail": rule.tail,
                                        "relation_text": rule.relation,
                                        "doc_title": rule.doc_title,
                                        "article": rule.article,
                                        "chunk_id": rule.chunk_id,
                                    })

                                stats = neo4j_client.save_kg_with_embedding(
                                    cypher_data,
                                    embed_func=llm.embed if llm else None,
                                )

                                st.success(f"已存入 Neo4j 知识图谱")
                                st.info(f"Chunks: {stats.get('chunks_created', 0)}, "
                                       f"实体: {stats.get('entities_created', 0)}, "
                                       f"关系: {stats.get('relations_created', 0)}, "
                                       f"Embeddings: {stats.get('embeddings_generated', 0)}")

                                if stats.get("errors"):
                                    with st.expander("⚠️ 存储警告"):
                                        for err in stats["errors"][:5]:
                                            st.warning(err)

                            except Exception as e:
                                st.warning(f"存入 Neo4j 失败: {str(e)}")
                                st.info("三元组已导出到本地文件，可稍后手动导入")

                    except Exception as e:
                        st.error(f"抽取规则知识图谱时出错：{str(e)}")
            else:
                st.info("请先完成切块")


def render_question_generation_section():
    st.header("🎯 问题生成")
    st.markdown("基于知识图谱生成低空安全相关问题")

    col1, col2, col3 = st.columns(3)
    with col1:
        difficulty = st.selectbox(
            "难度级别",
            options=["easy", "medium", "hard"],
            format_func=lambda x: {"easy": "简单", "medium": "中等", "hard": "困难"}[x],
            index=2,
            key="q_difficulty"
        )
    with col2:
        question_type = st.selectbox(
            "题目类型",
            options=["choice", "judgment"],
            format_func=lambda x: {"choice": "选择题", "judgment": "判断题"}[x],
            index=0,
            key="q_type"
        )
    with col3:
        num_questions = st.number_input(
            "题目数量",
            min_value=1,
            max_value=10,
            value=1,
            step=1,
            key="q_num"
        )

    user_query = st.text_area(
        "问题描述/要求（留空则随机出题）",
        placeholder="例如：请生成关于无人机飞行许可的问题，或留空随机出题",
        height=100,
        key="q_query"
    )

    if st.button("生成问题", key="btn_generate"):
        query = user_query.strip() if user_query.strip() else "随机出题"

        llm = init_llm()
        if llm is None:
            return

        try:
            neo4j_client = get_neo4j_client()
        except Exception as e:
            st.error(f"Neo4j 连接失败: {str(e)}")
            return

        agent = QuestionAgent(llm=llm, neo4j_client=neo4j_client)

        with st.spinner("正在生成问题..."):
            try:
                result = agent.run(
                    user_query=query,
                    difficulty=difficulty,
                    question_type=question_type,
                    num_questions=num_questions
                )

                st.session_state["agent_result"] = result

            except Exception as e:
                st.error(f"问题生成失败: {str(e)}")
                return

    if "agent_result" in st.session_state:
        result = st.session_state["agent_result"]

        st.subheader("📊 执行结果")
        status = result.get("status", "unknown")
        status_map = {
            "success": ("✅ 成功", "green"),
            "completed": ("✅ 完成", "green"),
            "evaluated": ("📝 已评估", "blue"),
            "error": ("❌ 错误", "red")
        }
        status_text, status_color = status_map.get(status, (status, "gray"))
        st.markdown(f"**状态**: :{status_color}[{status_text}]")

        if result.get("error"):
            st.error(f"错误信息: {result['error']}")

        questions = result.get("questions", [])
        if questions:
            st.subheader(f"📝 生成的问题 ({len(questions)} 道)")

            for i, q in enumerate(questions, 1):
                with st.expander(f"问题 {i}", expanded=(i == 1)):
                    st.markdown(f"**题目**: {q.get('question_text', 'N/A')}")

                    options = q.get("options", [])
                    if options:
                        st.markdown("**选项**:")
                        for j, opt in enumerate(options):
                            st.markdown(f"  {chr(65+j)}. {opt}")

                    st.markdown(f"**答案**: {q.get('answer', 'N/A')}")
                    st.markdown(f"**解释**: {q.get('explanation', 'N/A')}")

                    source_entities = q.get("source_entities", [])
                    if source_entities:
                        st.markdown(f"**相关实体**: {', '.join(source_entities)}")

                    source_relations = q.get("source_relations", [])
                    if source_relations:
                        st.markdown(f"**相关关系**: {', '.join(source_relations)}")

        evaluation = result.get("evaluation")
        if evaluation:
            st.subheader("📋 评估结果")
            is_approved = evaluation.get("is_approved", False)
            if is_approved:
                st.success("✅ 问题质量通过评估")
            else:
                issues = evaluation.get("issues", [])
                suggestions = evaluation.get("suggestions", [])
                if issues:
                    st.warning("⚠️ 存在问题:")
                    for issue in issues:
                        st.markdown(f"  - {issue}")
                if suggestions:
                    st.info("💡 改进建议:")
                    for suggestion in suggestions:
                        st.markdown(f"  - {suggestion}")

        with st.expander("🔍 检索详情"):
            chunks = result.get("chunks", [])
            if chunks:
                st.markdown(f"**检索到的文档块 ({len(chunks)} 个)**:")
                for i, chunk in enumerate(chunks[:3], 1):
                    st.markdown(f"  {i}. {chunk.get('doc_title', 'N/A')} - {chunk.get('article', 'N/A')}")

            subgraph = result.get("subgraph", {})
            if subgraph:
                entities = subgraph.get("entities", [])
                relations = subgraph.get("relations", [])
                st.markdown(f"**子图信息**:")
                st.markdown(f"  - 实体数量: {len(entities)}")
                st.markdown(f"  - 关系数量: {len(relations)}")


def main():
    st.set_page_config(page_title="低空安全题库生成器", page_icon="📚")
    st.title("📚 低空安全题库生成器")

    config = get_global_config()

    api_key = os.getenv("SILICONFLOW_API_KEY") or config.llm.api_key
    if not api_key:
        st.error("请设置 SILICONFLOW_API_KEY 环境变量")
        return

    tab1, tab2 = st.tabs(["📄 文档处理", "🎯 问题生成"])

    with tab1:
        render_document_processing_section()

    with tab2:
        render_question_generation_section()

    st.sidebar.divider()
    st.sidebar.header("已上传文件记录")
    uploaded_hashes = load_uploaded_hashes()
    if uploaded_hashes:
        st.sidebar.text(f"共 {len(uploaded_hashes)} 个文件")
    else:
        st.sidebar.text("暂无上传记录")


if __name__ == "__main__":
    main()
