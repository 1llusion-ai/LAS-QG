import streamlit as st
from pathlib import Path
from datetime import datetime
import tempfile
import hashlib
import json
import os

from src.parsers.document_parser import parse_document, detect_doc_type
from src.cleaner.text_cleaner import clean_text
from src.cleaner.text_chunker import chunk_document
from src.kg.rule_extractor import extract_rule_kg
from src.kg.kg_builder import build_rule_kg
from src.kg.txt_parser import parse_kg_txt
from src.config import get_global_config
from src.generation.llm_client import SiliconFlowClient
from src.schemas.types import DifficultyLevel, DocumentChunk
import streamlit.components.v1 as components


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


def visualize_kg(rule_kg):
    st.success("三元组抽取完成！")

    st.metric("三元组数量", len(rule_kg.rules))

    if rule_kg.rules:
        for rule in rule_kg.rules:
            with st.expander(f"🔗 {rule.head} → {rule.relation} → {rule.tail}"):
                st.write(f"**head：** {rule.head}")
                st.write(f"**relation：** {rule.relation}")
                st.write(f"**tail：** {rule.tail}")
                st.write(f"**doc_title：** {rule.doc_title or '无'}")
                st.write(f"**article：** {rule.article or '无'}")
                st.write(f"**chunk_id：** {rule.chunk_id}")
                st.write(f"**source_text：** {rule.source_text or '无'}")
    else:
        st.info("暂无三元组")


def visualize_graph(rule_kg):
    st.markdown("### 知识图谱可视化")

    graph = build_rule_kg(rule_kg.rules)
    stats = {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges()
    }

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("节点数", stats["nodes"])
    with col2:
        st.metric("边数", stats["edges"])
    with col3:
        st.metric("规则数", len(rule_kg.rules))

    node_colors = {
        "rule": "#FF6B6B",
        "subject": "#4ECDC4",
        "action": "#45B7D1",
        "object": "#96CEB4",
        "modality": "#FFEAA7",
        "condition": "#DDA0DD",
        "scope": "#98D8C8",
        "purpose": "#F7DC6F"
    }

    st.markdown("#### 节点类型图例")
    legend_cols = st.columns(4)
    for i, (node_type, color) in enumerate(node_colors.items()):
        with legend_cols[i % 4]:
            st.markdown(f"<span style='color:{color};font-size:20px'>●</span> {node_type}", unsafe_allow_html=True)

    if graph.number_of_nodes() == 0:
        st.info("图谱为空")
        return

    from pyvis.network import Network
    import tempfile

    net = Network(height="500px", width="100%", bgcolor="#ffffff", font_color="black", notebook=False)
    net.barnes_hut(gravity=-2000, central_gravity=0.3, spring_length=120)

    for node, data in graph.nodes(data=True):
        node_type = data.get("node_type", "unknown")
        label = data.get("label", node)
        color = node_colors.get(node_type, "#CCCCCC")
        net.add_node(node, label=label, color=color, title=f"{node_type}: {label}")

    for u, v, data in graph.edges(data=True):
        edge_type = data.get("edge_type", "")
        net.add_edge(u, v, title=edge_type, label=edge_type)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
        net.save_graph(f.name)
        html_content = open(f.name, "r", encoding="utf-8").read()

    st.markdown("#### 交互式图谱（可拖拽、缩放）")
    components.html(html_content, height=520, scrolling=True)


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
                            rule_kg = extract_rule_kg(document.id, chunks, llm, progress_callback=write_chunk_progress, doc_title=doc_title)

                        with open(json_file, "w", encoding="utf-8") as f:
                            json.dump({"document_id": document.id, "rules": all_rules}, f, ensure_ascii=False, indent=2)

                        st.session_state["doc_rule_kg"] = rule_kg
                        st.session_state["doc_kg_json_file"] = str(json_file)

                        progress_bar.empty()
                        status_text.empty()
                        st.success(f"已导出到: {export_file}")
                        st.info(f"共抽取：{len(rule_kg.rules)} 条规则")
                        visualize_kg(rule_kg)

                    except Exception as e:
                        st.error(f"抽取规则知识图谱时出错：{str(e)}")
            else:
                st.info("请先完成切块")

    if "doc_rule_kg" in st.session_state:
        st.divider()
        st.subheader("已抽取的规则")
        visualize_kg(st.session_state["doc_rule_kg"])


def render_kg_construction_section():
    st.header("🕸️ KG构图（从TXT）")
    st.markdown("上传包含规则知识的 TXT 文件，直接构建知识图谱")

    kg_file = st.file_uploader(
        "选择KG规则文件",
        type=["txt"],
        key="kg_uploader",
        help="上传格式化的KG规则TXT文件",
    )

    if kg_file is not None:
        is_valid, error_msg = validate_file(kg_file)
        if not is_valid:
            st.error(error_msg)
            return

        st.success(f"文件已上传：{kg_file.name}")

        kg_col1, kg_col2 = st.columns(2)
        with kg_col1:
            st.write("**文件名：**", kg_file.name)
        with kg_col2:
            st.write("**文件大小：**", f"{kg_file.size / 1024:.2f} KB")

        if st.button("解析并构建知识图谱", key="btn_build_kg"):
            with st.spinner("正在解析和构建知识图谱..."):
                try:
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".txt"
                    ) as tmp_file:
                        tmp_file.write(kg_file.getvalue())
                        tmp_path = tmp_file.name

                    rules = parse_kg_txt(tmp_path)

                    if not rules:
                        st.warning("未能解析出规则，请检查文件格式")
                        return

                    rule_kg = type('RuleKG', (), {
                        'document_id': Path(kg_file.name).stem,
                        'rules': [type('Rule', (), r)() for r in rules]
                    })()

                    st.session_state["kg_rule_kg"] = rule_kg
                    st.info(f"已解析 {len(rules)} 条规则")

                    visualize_graph(rule_kg)

                except Exception as e:
                    st.error(f"构建知识图谱时出错：{str(e)}")

    if "kg_rule_kg" not in st.session_state:
        st.info("请上传 KG 规则文件并构建知识图谱")


def main():
    st.set_page_config(page_title="低空安全题库生成器")
    st.title("低空安全题库生成器")

    config = get_global_config()

    api_key = os.getenv("SILICONFLOW_API_KEY") or config.llm.api_key
    if not api_key:
        st.error("请设置 SILICONFLOW_API_KEY 环境变量")
        return

    render_document_processing_section()

    st.divider()
    st.markdown("---")

    render_kg_construction_section()

    st.sidebar.divider()
    st.sidebar.header("已上传文件记录")
    uploaded_hashes = load_uploaded_hashes()
    if uploaded_hashes:
        st.sidebar.text(f"共 {len(uploaded_hashes)} 个文件")
    else:
        st.sidebar.text("暂无上传记录")


if __name__ == "__main__":
    main()
