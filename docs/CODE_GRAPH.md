# Code graphs with graphify

A **code graph** is a map of a codebase: every module, class and function is a
*node*, and every import, call or "uses" is an *edge*. Reading the map tells you
which pieces are central, how code clusters into areas, and where two projects
quietly duplicate each other. This guide covers how the graphs for this
workspace (and the projects around it) are built, how to question them, and
what to watch out for.

Contents:

1. [Why a graph](#1-why-a-graph)
2. [Build a code-only graph (free, local)](#2-build-a-code-only-graph-free-local)
3. [Connect several workspaces](#3-connect-several-workspaces)
4. [Ask the graph questions](#4-ask-the-graph-questions)
5. [Reading the results honestly](#5-reading-the-results-honestly)
6. [Security and privacy](#6-security-and-privacy)
7. [What the first graphs found](#7-what-the-first-graphs-found)
8. [Exercises](#8-exercises)
9. [References](#references)

---

## 1. Why a graph

| Question | Without a graph | With one |
| --- | --- | --- |
| "What uses `AdsPower`?" | grep, then open every hit | `graphify explain "AdsPower"` lists every caller with file:line |
| "Which code is central?" | gut feeling | **god nodes**: the most-connected nodes |
| "How is this project organised?" | read the folders | **communities**: clusters found by the graph itself |
| "Do two projects duplicate each other?" | remember | merge their graphs and look for same-named modules |

For an AI assistant the graph also saves tokens: answering from a scoped
subgraph is far cheaper than reading the files.

## 2. Build a code-only graph (free, local)

[graphify](https://github.com/Graphify-Labs/graphify) parses source code with
**tree-sitter**: a real parser per language, run on your machine. No AI model is
involved and nothing leaves the computer, so a code-only graph costs no tokens.

```powershell
uv tool install graphifyy    # the PyPI name has two y's; the command is `graphify`
cd <folder to map>
graphify update .            # AST-only build or refresh: graphify-out/graph.json + GRAPH_REPORT.md
graphify export html         # graphify-out/graph.html, open in a browser
```

From Claude Code, `/graphify .` runs the full pipeline. Its **semantic** pass
(docs, PDFs, images) is the only part that uses an AI model, and so the only
part that costs tokens. On a large folder of Markdown that can be a lot, so this
workspace's graphs were built **code-only**: AST extraction, clustering, a
report, community names, and the HTML view.

| Output | What it is |
| --- | --- |
| `graph.json` | the nodes and edges (the data everything else reads) |
| `GRAPH_REPORT.md` | god nodes, surprising connections, communities, suggested questions |
| `graph.html` | interactive view |
| `manifest.json` | file hashes, so `graphify update` only re-reads changed files |

## 3. Connect several workspaces

Each workspace gets its own graph, built at the workspace's top folder. Then the
graphs are merged one level up, so one query can cross projects:

```powershell
cd <Coding_Proj>
graphify merge-graphs Side_Projects_For_Fun\graphify-out\graph.json Mr_Factory\graphify-out\graph.json --out graphify-out\graph.json
```

Every node in the merged graph keeps a `repo` attribute saying where it came
from. Rebuild the per-workspace graphs first, then re-merge, whenever the code
has changed a lot.

## 4. Ask the graph questions

```powershell
graphify query "how does the batch creator pick proxies?"   # broad: a scoped subgraph
graphify explain "AdsPower"                                  # one node: every connection, file:line
graphify path "BatchCreator" "LocalApi"                      # shortest path between two nodes
```

If a name exists in several files, graphify asks you to pick:
`graphify explain "<path>::Script"` or use the full node id it prints.

## 5. Reading the results honestly

Every edge is labelled with how it was found:

| Label | Meaning | Trust |
| --- | --- | --- |
| `EXTRACTED` | read directly from the code (an import, a call) | high |
| `INFERRED` | guessed from names and context | check it |
| `AMBIGUOUS` | unclear | treat as a hint |

Things found live while building these graphs:

- **Name collisions create false bridges.** The standard library's
  `pathlib.Path` and a project class also named `Path` were merged into one
  node, which then "connected" a dozen unrelated communities. When a bridge
  looks too good, run `graphify explain` on it and check the files.
- **"Dangling" edges are normal in a code-only graph.** Calls into libraries
  (`os`, `json`, `testing.T`) point at nodes that have no source file in the
  workspace. Hundreds of them are expected; they are not damage.
- **Data files yield no symbols.** `pyproject.toml`, `go.mod` and similar are
  listed but contribute no functions. That is a warning, not an error.
- **A low cohesion score** (e.g. 0.05) means a community's parts are loosely
  connected. It is a hint to look at, not proof that the code should be split.

## 6. Security and privacy

- **Never commit `graphify-out/`.** It records absolute paths (your user folder
  is in `.graphify_root` and `.graphify_python`), and a graph of a private repo
  describes its private code. Every repo's `.gitignore` lists `graphify-out/`.
  Graphs for several repos are built in parent folders that are not repos at
  all.
- graphify also maps the **keys inside JSON files**. Before graphing a folder,
  check that it holds no credential, cookie or account-data JSON. The
  detection step reports any files it skipped as sensitive.
- What graphify itself does (from its security policy, reviewed before
  installing): no shell commands, no `eval` of source code, no network listener
  by default, no stored keys; the semantic pass only sends content to a model if
  you configure one.

## 7. What the first graphs found

The first merged graph (two workspaces, about 5,000 nodes) showed:

- **The same small tools rewritten in many projects:** a Markdown link
  checker in 7 projects, a security scanner in 6, a check-all gate in 3. They
  are candidates for one shared package in this workspace, written once,
  tested once, and installed everywhere.
- **Two copies of an AdsPower API client outside this workspace,** next to
  `packages/adspower`. Only one of the copies had the safety rules
  `packages/adspower` uses: talk to loopback only, never route through a
  system proxy, never resolve AdsPower's address through public DNS. The other
  copy has since been fixed. This is the practical risk of duplication: **a
  security fix lands in one copy and not the others.**

## 8. Exercises

1. Run `graphify explain "BatchCreator"` and list which of its edges are `EXTRACTED` and which are `INFERRED`. Check two inferred ones by reading the code.
2. Find the name collision behind the `Path` bridge with `graphify explain`. Which two files does it actually join?
3. After changing a file, run `graphify update .` and compare `GRAPH_REPORT.md` before and after.

**Self-check:** why is it safe to build a graph of a private repo, but not to commit its `graphify-out/`?

## References

**Official**
- graphify: [README](https://github.com/Graphify-Labs/graphify), [SECURITY.md](https://github.com/Graphify-Labs/graphify/blob/main/SECURITY.md), [how it works](https://github.com/Graphify-Labs/graphify/blob/main/docs/how-it-works.md), PyPI [`graphifyy`](https://pypi.org/project/graphifyy/)
- [tree-sitter](https://tree-sitter.github.io/tree-sitter/): the parser graphify uses for code
- [uv tools](https://docs.astral.sh/uv/concepts/tools/): how `uv tool install` isolates a CLI
- NetworkX: [community detection (Louvain)](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.community.louvain.louvain_communities.html), [betweenness centrality](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.centrality.betweenness_centrality.html)

**Other**
- [Code property graphs](https://en.wikipedia.org/wiki/Code_property_graph) (the idea of code as a graph)
- [Don't repeat yourself](https://en.wikipedia.org/wiki/Don%27t_repeat_yourself)

### Further learning
- [Network Science, Albert-László Barabási](http://networksciencebook.com/) (free book): degree, hubs, communities
