import html
import json
import textwrap
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

GRAPH_FILE = Path(__file__).parent / "data" / "graph.json"
COLORS = {
    "Intent": "#F4C95D",
    "Device": "#5BB8A8",
    "Vendor": "#7B8CDE",
    "KBArticle": "#A0AEC0",
    "Question": "#78A9E6",
    "Answer": "#9ACD84",
    "Resolution": "#F28C75",
}
SHAPES = {
    "Intent": "star",
    "Device": "hexagon",
    "Vendor": "dot",
    "KBArticle": "database",
    "Question": "box",
    "Answer": "ellipse",
    "Resolution": "box",
}


def load_graph():
    if not GRAPH_FILE.exists():
        st.error("data/graph.json is missing. Save the article as data/article.html, then run clean_article.py and build_graph.py.")
        st.stop()
    try:
        return json.loads(GRAPH_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        st.error(f"data/graph.json is not valid JSON: {error}")
        st.stop()


def graph_for_device(graph, device, show_context=False):
    nodes_by_id = {node["id"]: node for node in graph["nodes"]}
    device_node = next(node for node in graph["nodes"] if node["type"] == "Device" and node["name"] == device)
    visible_ids = {device_node["id"], "INT_BATTERY"}
    if show_context:
        visible_ids.add("VENDOR_DELL")
        visible_ids.update(node["id"] for node in graph["nodes"] if node["type"] == "KBArticle")
    visible_ids.update(
        node["id"] for node in graph["nodes"]
        if node.get("props", {}).get("device") == device
    )
    edges = [edge for edge in graph["edges"] if edge["from"] in visible_ids and edge["to"] in visible_ids]
    nodes = [node for node in graph["nodes"] if node["id"] in visible_ids]
    return nodes, edges


def wrapped_label(value, width=28, max_lines=4):
    lines = textwrap.wrap(str(value), width=width, break_long_words=True, break_on_hyphens=False)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .") + "…"
    return "\n".join(lines) or str(value)


def node_tooltip(node):
    props = node.get("props", {})
    details = "<br/>".join(
        f"<b>{html.escape(str(key))}</b>: {html.escape(json.dumps(value, ensure_ascii=False))}"
        for key, value in props.items()
    )
    return (
        '<div style="max-width:420px;white-space:normal;line-height:1.5">'
        f"<strong>{html.escape(node['name'])}</strong><br/>{details}</div>"
    )


def render_graph(nodes, edges):
    network = Network(height="820px", width="100%", directed=True, bgcolor="#F7F9FC", font_color="#182230")
    network.set_options("""
    {
      "layout": {"hierarchical": {"enabled": true, "direction": "UD", "sortMethod": "directed", "levelSeparation": 190, "nodeSpacing": 230, "treeSpacing": 250, "blockShifting": true, "edgeMinimization": true, "parentCentralization": true}},
      "physics": {"enabled": false},
      "interaction": {"hover": true, "hoverConnectedEdges": true, "selectConnectedEdges": true, "multiselect": true, "navigationButtons": true, "keyboard": true, "dragNodes": true, "dragView": true, "zoomView": true},
      "nodes": {"font": {"size": 17, "face": "Arial", "color": "#182230"}, "scaling": {"min": 18, "max": 26}, "borderWidth": 2, "borderWidthSelected": 4},
      "edges": {"arrows": {"to": {"enabled": true, "scaleFactor": 0.7}}, "smooth": {"type": "cubicBezier", "forceDirection": "vertical", "roundness": 0.3}, "font": {"size": 12, "face": "Arial", "background": "#F7F9FC", "strokeWidth": 0}, "selectionWidth": 2, "hoverWidth": 2}
    }
    """)
    for node in nodes:
        node_type = node["type"]
        color = COLORS.get(node_type, "#CBD5E1")
        network.add_node(
            node["id"],
            label=html.escape(wrapped_label(node["name"])),
            title=node_tooltip(node),
            color={"background": color, "border": color, "highlight": {"background": color, "border": "#172B4D"}, "hover": {"background": color, "border": "#172B4D"}},
            shape=SHAPES.get(node_type, "box"),
            margin=14,
            widthConstraint={"maximum": 270},
            font={"size": 17, "face": "Arial", "color": "#182230"},
        )
    for edge in edges:
        edge_type = edge["type"]
        props = edge.get("props", {})
        label = props.get("label", "") if edge_type == "HAS_ANSWER" else "If not fixed" if edge_type == "IF_NOT_FIXED" else ""
        edge_title = edge_type + (" · inferred" if props.get("inferred") else "")
        network.add_edge(
            edge["from"],
            edge["to"],
            label=html.escape(label),
            title=html.escape(edge_title),
            dashes=edge_type == "IF_NOT_FIXED",
            color="#D18A2E" if edge_type == "IF_NOT_FIXED" else "#8291A5",
            arrows="to",
        )
    return network.generate_html(notebook=False, local=False)


def values(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def show_node_details(node):
    props = node.get("props", {})
    left, right = st.columns([1, 2], gap="large")
    with left:
        st.caption(f"{node['type']} · {node['id']}")
        st.markdown(f"### {node['name']}")
        if props.get("indicates"):
            st.info(props["indicates"])
        if props.get("tool"):
            st.caption(f"Tool: {props['tool']}")
    with right:
        for heading, key in (("Instructions", "instructions"), ("Checklist", "checklist"), ("Commands", "commands")):
            items = values(props.get(key))
            if items:
                st.markdown(f"**{heading}**")
                for item in items:
                    if key == "commands":
                        st.code(str(item), language="text")
                    else:
                        st.markdown(f"- {item}")
        if props.get("note"):
            st.warning(props["note"])
    titles = values(props.get("resource_titles"))
    urls = values(props.get("resource_urls"))
    resources = [(titles[index] if index < len(titles) else url, url) for index, url in enumerate(urls) if url]
    if resources:
        st.markdown("**Resources**")
        columns = st.columns(min(3, len(resources)))
        for index, (title, url) in enumerate(resources):
            with columns[index % len(columns)]:
                st.link_button(str(title or "Open resource"), str(url), use_container_width=True)
    with st.expander("All node properties"):
        st.json(props)


def main():
    st.set_page_config(page_title="Dell Battery Troubleshooting", layout="wide", initial_sidebar_state="expanded")
    st.markdown("""
    <style>
      .block-container {padding-top: 2rem; padding-bottom: 2rem; max-width: 1600px;}
      [data-testid="stMetric"] {background: #F7F9FC; border: 1px solid #E2E8F0; padding: 14px 16px; border-radius: 12px;}
      [data-testid="stMetricLabel"] {color: #536273;}
    </style>
    """, unsafe_allow_html=True)
    st.title("Dell Battery Troubleshooting")
    st.caption("Explore the decision flow for a device. Select a node below the graph to inspect its instructions, notes, commands, and resources.")

    graph = load_graph()
    devices = sorted(node["name"] for node in graph["nodes"] if node["type"] == "Device")
    if not devices:
        st.error("No Device nodes are present in data/graph.json.")
        st.stop()

    with st.sidebar:
        st.header("Explore the graph")
        selected_device = st.selectbox("Dell device", devices, index=devices.index("Latitude") if "Latitude" in devices else 0)
        show_context = st.checkbox("Show vendor and article nodes", value=False)
        st.caption("Scroll to zoom, drag to pan, and hover over nodes for full details.")

    nodes, edges = graph_for_device(graph, selected_device, show_context)
    path_nodes = [node for node in nodes if node["type"] in {"Question", "Answer", "Resolution"}]
    counts = {node_type: sum(node["type"] == node_type for node in path_nodes) for node_type in ("Question", "Answer", "Resolution")}
    metric_columns = st.columns(3)
    metric_columns[0].metric("Decision points", counts["Question"])
    metric_columns[1].metric("Answer branches", counts["Answer"])
    metric_columns[2].metric("Fixes / outcomes", counts["Resolution"])

    legend_types = ["Intent", "Device", "Question", "Answer", "Resolution"]
    if show_context:
        legend_types.extend(["Vendor", "KBArticle"])
    legend_columns = st.columns(len(legend_types))
    for column, node_type in zip(legend_columns, legend_types):
        with column:
            st.markdown(
                f'<span style="display:inline-block;width:11px;height:11px;border-radius:50%;background:{COLORS[node_type]};margin-right:7px"></span>{node_type}',
                unsafe_allow_html=True,
            )

    st.subheader(f"{selected_device} decision flow")
    st.caption("Answer labels appear on the connecting arrows. Dashed amber arrows mean ‘If not fixed’. Select a node to highlight it, then inspect its details below.")
    components.html(render_graph(nodes, edges), height=840, scrolling=True)

    st.divider()
    st.subheader("Inspect a node")
    ordered_nodes = sorted(nodes, key=lambda node: (node["type"], node["name"].casefold(), node["id"]))
    nodes_by_id = {node["id"]: node for node in ordered_nodes}
    selected_id = st.selectbox(
        "Choose a graph node",
        list(nodes_by_id),
        format_func=lambda node_id: f"{nodes_by_id[node_id]['type']} · {nodes_by_id[node_id]['name']}",
    )
    show_node_details(nodes_by_id[selected_id])


if __name__ == "__main__":
    main()
