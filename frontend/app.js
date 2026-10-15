document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("form");
  const fileInput = document.getElementById("file");
  const status = document.getElementById("status");
  const results = document.getElementById("results");
  const original = document.getElementById("original");
  const simplified = document.getElementById("simplified");
  const verification = document.getElementById("verification");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!fileInput.files.length) {
      alert("Choose a file first.");
      return;
    }

    const file = fileInput.files[0];
    const fd = new FormData();
    fd.append("file", file);

    status.innerText = "Uploading and simplifying...";
    try {
      const response = await fetch("/simplify", {
        method: "POST",
        body: fd
      });

      if (!response.ok) {
        const txt = await response.text();
        throw new Error(txt || "Server error");
      }

      const data = await response.json();
      status.innerText = "Done";
      results.style.display = "block";
      original.innerText = data.original_text || "";
      simplified.innerText = data.simplified_text || "";
      verification.innerText = JSON.stringify(data.verification, null, 2);

      renderGraph("orig-graph", data.original_graph);
      renderGraph("gen-graph", data.generated_graph);
    } catch (err) {
      status.innerText = "Error: " + err.message;
    }
  });

  function renderGraph(containerId, graphJson) {
    const container = document.getElementById(containerId);
    if (!graphJson || !graphJson.nodes || !graphJson.links) {
      container.innerHTML = "";
      return;
    }

    const nodes = new vis.DataSet(
      graphJson.nodes.map((n) => ({
        id: n.id,
        label: n.type === "clause" ? (n.text || "clause").slice(0, 40) : (n.text || n.id),
        group: n.type || "node"
      }))
    );

    const edges = new vis.DataSet(
      graphJson.links.map((l) => ({
        from: l.source,
        to: l.target,
        label: l.relation || ""
      }))
    );

    const data = { nodes, edges };
    const options = {
      groups: {
        party: { color: { background: "#FFD966" } },
        clause: { color: { background: "#B4C7E7" } },
        obligation: { color: { background: "#F4CCCC" } },
        amount: { color: { background: "#C9DAF8" } },
        deadline: { color: { background: "#D9EAD3" } }
      },
      edges: {
        arrows: { to: { enabled: true } },
        font: { align: "top" }
      },
      layout: { improvedLayout: true },
      physics: { stabilization: true }
    };

    new vis.Network(container, data, options);
  }
});
