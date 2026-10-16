@@
-def run_full_pipeline(file_bytes: bytes, filename: str = "document", retry_limit: int = 2, progress_callback=None) -> Dict[str, Any]:
+def run_full_pipeline(file_bytes: bytes, filename: str = "document", retry_limit: int = 2, progress_callback=None) -> Dict[str, Any]:
@@
-    for attempt in range(retry_limit + 1):
-        if progress_callback:
-            progress_callback({"stage": "simplification", "progress": 70 + attempt * 5})
-        simplified = simplifier.simplify(text, constraints, attempt=attempt)
-        if progress_callback:
-            progress_callback({"stage": "post_simplification", "progress": 80})
-        simp_clauses = segment_clauses(simplified)
-        gen_facts = extract_legal_facts(simp_clauses)
-        gen_graph = build_fact_graph(gen_facts)
-        if progress_callback:
-            progress_callback({"stage": "verification", "progress": 90})
-        mismatches = verify_graphs(orig_graph, gen_graph)
-        if not mismatches:
-            status = {"verified": True, "attempts": attempt + 1}
-            break
-        else:
-            status = {"verified": False, "attempts": attempt + 1, "mismatches": mismatches}
-            if attempt == retry_limit:
-                break
+    for attempt in range(retry_limit + 1):
+        # Simplify clause-by-clause for much better performance on CPU
+        if progress_callback:
+            progress_callback({"stage": "simplification", "progress": 70 + attempt * 5})
+
+        simplified_clauses = []
+        total_clauses = len(clauses) if clauses else 1
+        import time
+        clause_start = time.time()
+        for i, clause in enumerate(clauses):
+            # update per-clause progress
+            if progress_callback:
+                pct = 70 + int(20 * (i + 1) / total_clauses)
+                progress_callback({"stage": "simplification_clause", "progress": pct})
+            simp = simplifier.simplify(
+                clause,
+                constraints,
+                attempt=attempt,
+                party_overrides=None,
+                exclude_test_instructions=True
+            )
+            simplified_clauses.append(simp)
+        simplified = "\n\n".join(simplified_clauses)
+        if progress_callback:
+            progress_callback({"stage": "post_simplification", "progress": 80})
+
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
*** End Patch
