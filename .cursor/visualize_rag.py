#!/usr/bin/env python3
"""
Visualize the RAG embedding space stored in .cursor/rag_db.

Usage:
    python .cursor/visualize_rag.py                   # UMAP (default)
    python .cursor/visualize_rag.py --method tsne     # t-SNE
    python .cursor/visualize_rag.py --method pca      # PCA
    python .cursor/visualize_rag.py -o my_plot.png    # custom output path
    python .cursor/visualize_rag.py --top-n 500       # limit to 500 chunks
    python .cursor/visualize_rag.py --labels 15       # annotate 15 points
"""

import argparse
from pathlib import Path

import chromadb
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VECTOR_DB = PROJECT_ROOT / ".cursor" / "rag_db"
COLLECTION_NAME = "rag-ai-scientist"

SOURCE_TYPE_COLORS = {
    "paper":          "#1f77b4",
    "analysis_note":  "#ff7f0e",
    "code":           "#2ca02c",
    "documentation":  "#d62728",
    "curated_note":   "#9467bd",
    "other":          "#8c564b",
}


def load_collection(db_path: Path, collection_name: str):
    client = chromadb.PersistentClient(path=str(db_path))
    names = [c.name for c in client.list_collections()]
    if collection_name not in names:
        if len(names) == 1:
            collection_name = names[0]
            print(f"  Using only available collection: {collection_name}")
        else:
            raise SystemExit(
                f"Collection '{collection_name}' not found. Available: {names}"
            )
    col = client.get_collection(collection_name)
    results = col.get(include=["embeddings", "documents", "metadatas"])
    return results


def reduce_dimensions(embeddings: np.ndarray, method: str, seed: int = 42):
    if method == "umap":
        import umap
        reducer = umap.UMAP(n_components=2, random_state=seed, metric="cosine")
    elif method == "tsne":
        from sklearn.manifold import TSNE
        perp = min(30, max(5, len(embeddings) // 4))
        reducer = TSNE(n_components=2, random_state=seed, perplexity=perp)
    elif method == "pca":
        from sklearn.decomposition import PCA
        reducer = PCA(n_components=2, random_state=seed)
    else:
        raise ValueError(f"Unknown method: {method}")

    return reducer.fit_transform(embeddings)


def plot_embeddings(
    coords: np.ndarray,
    metadatas: list[dict],
    documents: list[str],
    method: str,
    n_labels: int,
    output: Path,
):
    source_types = [m.get("source_type", "other") for m in metadatas]
    unique_types = sorted(set(source_types))

    fig, ax = plt.subplots(figsize=(13, 9))

    for st in unique_types:
        mask = np.array([s == st for s in source_types])
        color = SOURCE_TYPE_COLORS.get(st, "#999999")
        ax.scatter(
            coords[mask, 0], coords[mask, 1],
            label=st, color=color, alpha=0.55, s=28, edgecolors="white", linewidths=0.3,
        )

    if n_labels > 0:
        indices = np.random.default_rng(0).choice(len(documents), size=min(n_labels, len(documents)), replace=False)
        for i in indices:
            snippet = (documents[i] or "")[:50].replace("\n", " ")
            ax.annotate(
                snippet, coords[i],
                fontsize=5, alpha=0.7,
                arrowprops=dict(arrowstyle="-", alpha=0.3, lw=0.4),
            )

    ax.set_title(f"RAG Embedding Space ({method.upper()} projection)", fontsize=14)
    ax.set_xlabel("Component 1")
    ax.set_ylabel("Component 2")
    ax.legend(title="source_type", fontsize=8, title_fontsize=9, loc="best", framealpha=0.8)

    fig.tight_layout()
    fig.savefig(output, dpi=180)
    print(f"Saved → {output}")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Visualize RAG embedding space")
    parser.add_argument(
        "--db", type=Path, default=VECTOR_DB,
        help=f"Path to ChromaDB directory (default: {VECTOR_DB})",
    )
    parser.add_argument(
        "--collection", default=COLLECTION_NAME,
        help=f"Collection name (default: {COLLECTION_NAME})",
    )
    parser.add_argument(
        "--method", choices=["umap", "tsne", "pca"], default="umap",
        help="Dimensionality reduction method (default: umap)",
    )
    parser.add_argument(
        "--top-n", type=int, default=0,
        help="Limit to N random chunks (0 = all)",
    )
    parser.add_argument(
        "--labels", type=int, default=10,
        help="Number of points to annotate with text snippets (default: 10)",
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Output image path (default: embeddings_<method>.png in repo root)",
    )
    args = parser.parse_args()

    if args.output is None:
        args.output = PROJECT_ROOT / f"embeddings_{args.method}.png"

    print(f"Loading ChromaDB from {args.db} ...")
    results = load_collection(args.db, args.collection)

    embeddings = np.array(results["embeddings"])
    documents = results["documents"]
    metadatas = results["metadatas"]
    print(f"  {len(embeddings)} vectors, {embeddings.shape[1]} dimensions")

    if args.top_n > 0 and args.top_n < len(embeddings):
        idx = np.random.default_rng(42).choice(len(embeddings), size=args.top_n, replace=False)
        embeddings = embeddings[idx]
        documents = [documents[i] for i in idx]
        metadatas = [metadatas[i] for i in idx]
        print(f"  Sampled down to {args.top_n} vectors")

    print(f"Reducing to 2D with {args.method.upper()} ...")
    coords = reduce_dimensions(embeddings, args.method)

    plot_embeddings(coords, metadatas, documents, args.method, args.labels, args.output)


if __name__ == "__main__":
    main()
