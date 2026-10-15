@@
-def run_full_pipeline(file_bytes: bytes, filename: str = "document", retry_limit: int = 2) -> Dict[str, Any]:
-    text = extract_text_from_bytes(file_bytes, filename)
-    text = preprocess_text(text)
-    clauses = segment_clauses(text)
-    orig_facts = extract_legal_facts(clauses)
-    orig_graph = build_fact_graph(orig_facts)
-    constraints = extract_constraints(orig_facts)
-
-    simplified = None
-    gen_graph = None
-
-    for attempt in range(retry_limit + 1):
-        simplified = simplifier.simplify(text, constraints, attempt=attempt)
-        simp_clauses = segment_clauses(simplified)
-        gen_facts = extract_legal_facts(simp_clauses)
-        gen_graph = build_fact_graph(gen_facts)
-        mismatches = verify_graphs(orig_graph, gen_graph)
-        if not mismatches:
-            status = {"verified": True, "attempts": attempt + 1}
-            break
-        else:
-            status = {"verified": False, "attempts": attempt + 1, "mismatches": mismatches}
-            if attempt == retry_limit:
-                break
-
-    return {
-        "original_text": text[:5000],
-        "simplified_text": simplified,
-        "verification": status,
-        "original_graph": nx.node_link_data(orig_graph),
-        "generated_graph": nx.node_link_data(gen_graph)
-    }
+def run_full_pipeline(file_bytes: bytes, filename: str = "document", retry_limit: int = 2, progress_callback=None) -> Dict[str, Any]:
+    """Run the pipeline and optionally report progress via progress_callback(dict).
+    progress_callback receives updates like {"stage": "extraction", "progress": 10}
+    """
+    # Step 2: Text Extraction
+    if progress_callback:
+        progress_callback({"stage": "upload", "progress": 5})
+    text = extract_text_from_bytes(file_bytes, filename)
+    if progress_callback:
+        progress_callback({"stage": "extraction", "progress": 20})
+    # Step 3: Preprocess
+    text = preprocess_text(text)
+    # Step 4: Clause segmentation
+    clauses = segment_clauses(text)
+    if progress_callback:
+        progress_callback({"stage": "clause_segmentation", "progress": 35})
+    # Step 5: Extract facts from original
+    orig_facts = extract_legal_facts(clauses)
+    if progress_callback:
+        progress_callback({"stage": "fact_extraction", "progress": 45})
+    # Step 6: Original graph
+    orig_graph = build_fact_graph(orig_facts)
+    if progress_callback:
+        progress_callback({"stage": "graph_generation", "progress": 55})
+    # Step 7: constraints
+    constraints = extract_constraints(orig_facts)
+    if progress_callback:
+        progress_callback({"stage": "constraints", "progress": 65})
+
+    simplified = None
+    gen_graph = None
+
+    # Step 8-12: Simplification + verification loop
+    for attempt in range(retry_limit + 1):
+        if progress_callback:
+            progress_callback({"stage": "simplification", "progress": 70 + attempt * 5})
+        simplified = simplifier.simplify(text, constraints, attempt=attempt)
+        if progress_callback:
+            progress_callback({"stage": "post_simplification", "progress": 80})
+        simp_clauses = segment_clauses(simplified)
+        gen_facts = extract_legal_facts(simp_clauses)
+        gen_graph = build_fact_graph(gen_facts)
+        if progress_callback:
+            progress_callback({"stage": "verification", "progress": 90})
+        mismatches = verify_graphs(orig_graph, gen_graph)
+        if not mismatches:
+            status = {"verified": True, "attempts": attempt + 1}
+            break
+        else:
+            status = {"verified": False, "attempts": attempt + 1, "mismatches": mismatches}
+            if attempt == retry_limit:
+                break
+
+    if progress_callback:
+        progress_callback({"stage": "completed", "progress": 100})
+
+    return {
+        "original_text": text[:5000],
+        "simplified_text": simplified,
+        "verification": status,
+        "original_graph": nx.node_link_data(orig_graph),
+        "generated_graph": nx.node_link_data(gen_graph)
+    }
