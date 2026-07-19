"""M6 — contra demotion + archive-not-delete on the graph."""

from forge.graph import Graph, load_graph, save_graph


def labeled_graph(pos, neg, tactic="role-framing", dim="engine", value="chatgpt"):
    graph = Graph(taxonomy_version="v1")
    for _ in range(pos):
        graph.add_label(tactic, dim, value)
    for _ in range(neg):
        graph.add_label(tactic, dim, value, positive=False)
    return graph


class TestContraAndArchive:
    def test_sustained_negatives_are_contra(self):
        graph = labeled_graph(0, 10)
        edge = graph.edges[("role-framing", "engine", "chatgpt")]
        assert edge.contra

    def test_positive_edge_is_not_contra(self):
        graph = labeled_graph(10, 0)
        assert not graph.edges[("role-framing", "engine", "chatgpt")].contra

    def test_below_k_min_never_contra(self):
        graph = labeled_graph(0, 4)
        assert not graph.edges[("role-framing", "engine", "chatgpt")].contra

    def test_archive_contra_archives_not_deletes(self):
        graph = labeled_graph(0, 10)
        archived = graph.archive_contra()
        assert len(archived) == 1
        edge = graph.edges[("role-framing", "engine", "chatgpt")]
        assert edge.status == "archived"  # still present — never deleted

    def test_archived_edge_never_required(self):
        # promoted then flooded with negatives and archived: must drop out
        graph = labeled_graph(20, 0)
        assert "role-framing" in graph.required_tactics({"engine": "chatgpt"})
        for _ in range(200):
            graph.add_label("role-framing", "engine", "chatgpt", positive=False)
        graph.archive_contra()
        assert graph.required_tactics({"engine": "chatgpt"}) == {}


class TestPersistenceV2:
    def test_status_and_reviewed_round_trip(self, tmp_path):
        graph = labeled_graph(0, 10)
        graph.reviewed.add(("abc123", "chatgpt", "alex"))
        graph.archive_contra()
        path = tmp_path / "graph.json"
        save_graph(graph, path)
        loaded = load_graph(path)
        assert loaded.reviewed == {("abc123", "chatgpt", "alex")}
        assert loaded.edges[("role-framing", "engine", "chatgpt")].status == "archived"

    def test_loads_m4_files_without_new_fields(self, tmp_path):
        graph = labeled_graph(3, 0)
        path = tmp_path / "graph.json"
        save_graph(graph, path)
        import json

        data = json.loads(path.read_text())
        for e in data["edges"]:
            e.pop("status", None)
        data.pop("reviewed", None)
        path.write_text(json.dumps(data))
        loaded = load_graph(path)
        assert loaded.reviewed == set()
        assert loaded.edges[("role-framing", "engine", "chatgpt")].status == "active"
