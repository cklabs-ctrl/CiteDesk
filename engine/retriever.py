import os
import json
import re
from typing import Dict, Any, List, Optional
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class TicketRetriever:
    """
    Retrieves Top-K similar historical incidents with explainable match rationale,
    distractor/lookalike identification, and faceted filtering (FR-02, FR-07).
    """
    
    def __init__(self, corpus_path: str = None):
        self.corpus: List[Dict[str, Any]] = []
        self.vectorizer = None
        self.tfidf_matrix = None
        
        if corpus_path and os.path.exists(corpus_path):
            self.load_corpus(corpus_path)
            
    def load_corpus(self, corpus_path: str):
        with open(corpus_path, "r", encoding="utf-8") as f:
            self.corpus = json.load(f)
            
        corpus_texts = []
        for r in self.corpus:
            apps = " ".join(r.get("applications", []))
            errors = " ".join(r.get("observed_errors", []))
            full_repr = f"{r['title']} {r['description']} {apps} {errors} {r.get('root_cause', '')}"
            corpus_texts.append(full_repr)
            
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=10000,
            sublinear_tf=True
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus_texts)
        
    def search_similar(
        self,
        query_title: str,
        query_desc: str,
        apps: List[str] = None,
        top_k: int = 5,
        category_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if self.tfidf_matrix is None:
            raise ValueError("Retriever corpus is not loaded!")
            
        q_text = f"{query_title} {query_desc} {' '.join(apps or [])}".strip()
        q_vec = self.vectorizer.transform([q_text])
        
        sim_scores = cosine_similarity(q_vec, self.tfidf_matrix)[0]
        ranked_indices = np.argsort(sim_scores)[::-1]
        
        results = []
        for idx in ranked_indices:
            rec = self.corpus[idx]
            if category_filter and rec['category_code'] != category_filter:
                continue
                
            score = float(sim_scores[idx])
            if len(results) >= top_k:
                break
                
            rationale = self._generate_match_rationale(q_text, rec, score)
            
            results.append({
                "record_id": rec["record_id"],
                "similarity_score": round(score, 4),
                "category_code": rec["category_code"],
                "category_name": rec["category_name"],
                "title": rec["title"],
                "description": rec["description"][:200] + ("..." if len(rec["description"]) > 200 else ""),
                "priority": rec["priority"],
                "root_cause": rec["root_cause"],
                "resolution_steps": rec["resolution_steps"],
                "observed_errors": rec.get("observed_errors", []),
                "agent_questions": rec.get("agent_questions", []),
                "is_restricted": rec.get("is_restricted", False),
                "match_rationale": rationale,
                "is_lookalike_distractor": False
            })
            
        self._flag_lookalikes(results)
        return results
        
    def _generate_match_rationale(self, query: str, matched_rec: Dict[str, Any], score: float) -> str:
        q_lower = query.lower()
        shared_terms = []
        
        for err in matched_rec.get("observed_errors", []):
            if err.lower() in q_lower:
                shared_terms.append(f"same error code '{err}'")
                
        for app in matched_rec.get("applications", []):
            if app.lower() in q_lower:
                shared_terms.append(f"shared application '{app}'")
                
        if shared_terms:
            return f"High alignment on {', '.join(shared_terms)} (score: {round(score, 2)})"
        elif score > 0.40:
            return f"Strong symptom overlap with historical incident {matched_rec['record_id']}"
        elif score > 0.20:
            return f"Moderate symptom similarity to {matched_rec['record_id']}"
        else:
            return f"Low semantic correlation (score: {round(score, 2)})"

    def _flag_lookalikes(self, candidates: List[Dict[str, Any]]):
        if len(candidates) < 2:
            return
            
        lead_category = candidates[0]['category_code']
        for cand in candidates[1:]:
            if cand['category_code'] != lead_category and cand['similarity_score'] > 0.15:
                cand['is_lookalike_distractor'] = True
                cand['distractor_warning'] = (
                    f"Lookalike Alert: Shares keywords but belongs to '{cand['category_name']}' "
                    f"instead of primary diagnosis '{candidates[0]['category_name']}'."
                )

    def filter_tickets(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        platform: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Multi-word token search & faceted filter across 745 incidents (FR-07).
        Scores each record by keyword relevance and returns ranked list.
        """
        query_terms = [t.lower() for t in re.findall(r'\b\w+\b', query or "") if len(t) > 1]
        scored_results = []
        
        for r in self.corpus:
            # Category filter
            if category and r['category_code'] != category:
                continue
            # Priority filter
            if priority and r['priority'].lower() != priority.lower():
                continue
            # Platform filter
            if platform and platform.lower() not in r.get('platform', '').lower():
                continue
                
            # If no query terms, match everything with score 1.0
            if not query_terms:
                scored_results.append((1.0, r))
                continue
                
            # Searchable content
            searchable_text = (
                f"{r['record_id']} {r['category_code']} {r['category_name']} "
                f"{r['title']} {r['description']} "
                f"{' '.join(r.get('applications', []))} "
                f"{' '.join(r.get('observed_errors', []))} "
                f"{r.get('root_cause', '')}"
            ).lower()
            
            # Exact match boost on record_id or category code
            score = 0.0
            if query and query.strip().lower() in searchable_text:
                score += 5.0
                
            # Token match scoring
            matched_count = 0
            for term in query_terms:
                if term in searchable_text:
                    matched_count += 1
                    score += 1.0
                    
            if matched_count > 0:
                score += (matched_count / len(query_terms)) * 3.0
                scored_results.append((score, r))
                
        # Sort by relevance score descending
        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_results[:limit]]
