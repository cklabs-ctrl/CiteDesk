import os
import json
from typing import Dict, Any, List, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

class TicketSorter:
    """
    Classifies incoming tickets into Category and Priority.
    Provides calibrated confidence scores and feature attribution tokens for explainability (FR-01).
    """
    
    def __init__(self, model_data_path: str = None):
        self.category_pipeline = None
        self.priority_pipeline = None
        self.category_classes = []
        self.priority_classes = []
        self.taxonomy_map = {}
        
        if model_data_path and os.path.exists(model_data_path):
            self.train(model_data_path)
            
    def train(self, train_split_path: str):
        with open(train_split_path, "r", encoding="utf-8") as f:
            records = json.load(f)
            
        texts = [f"{r['title']} {r['description']} {' '.join(r.get('applications', []))}" for r in records]
        categories = [r['category_code'] for r in records]
        priorities = [r['priority'] for r in records]
        
        # Taxonomy mapping
        for r in records:
            if r['category_code'] not in self.taxonomy_map:
                self.taxonomy_map[r['category_code']] = {
                    "name": r.get('category_name', r['category_code']),
                    "domain": r.get('domain', 'General IT'),
                    "assigned_team": r.get('assigned_team', 'IT Service Desk')
                }
                
        # 1. Category Classifier Pipeline
        self.category_pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(ngram_range=(1, 2), max_features=5000, sublinear_tf=True)),
            ('clf', LogisticRegression(max_iter=1000, C=3.0, random_state=42))
        ])
        self.category_pipeline.fit(texts, categories)
        self.category_classes = list(self.category_pipeline.classes_)
        
        # 2. Priority Classifier Pipeline
        self.priority_pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(ngram_range=(1, 2), max_features=3000)),
            ('clf', LogisticRegression(max_iter=1000, C=1.5, random_state=42))
        ])
        self.priority_pipeline.fit(texts, priorities)
        self.priority_classes = list(self.priority_pipeline.classes_)
        
    def predict(self, title: str, description: str, apps: List[str] = None) -> Dict[str, Any]:
        if not self.category_pipeline:
            raise ValueError("TicketSorter is not trained yet!")
            
        full_text = f"{title} {description} {' '.join(apps or [])}".strip()
        
        # Category prediction
        cat_probs = self.category_pipeline.predict_proba([full_text])[0]
        top_cat_idx = np.argmax(cat_probs)
        cat_code = self.category_classes[top_cat_idx]
        cat_confidence = float(cat_probs[top_cat_idx])
        
        # Priority prediction
        prio_probs = self.priority_pipeline.predict_proba([full_text])[0]
        top_prio_idx = np.argmax(prio_probs)
        priority = self.priority_classes[top_prio_idx]
        prio_confidence = float(prio_probs[top_prio_idx])
        
        # Feature attribution tokens: find top n-grams from vectorizer with highest positive weights
        attribution_tokens = self._get_attribution_tokens(full_text, cat_code)
        
        meta = self.taxonomy_map.get(cat_code, {})
        return {
            "category_code": cat_code,
            "category_name": meta.get("name", cat_code),
            "domain": meta.get("domain", "Enterprise IT"),
            "category_confidence": round(cat_confidence, 4),
            "priority": priority,
            "priority_confidence": round(prio_confidence, 4),
            "assigned_team": meta.get("assigned_team", "Tier 2 Service Desk"),
            "attribution_tokens": attribution_tokens,
            "top_categories": [
                {"code": self.category_classes[i], "confidence": round(float(cat_probs[i]), 4)}
                for i in np.argsort(cat_probs)[::-1][:3]
            ]
        }
        
    def _get_attribution_tokens(self, text: str, predicted_class: str, top_k: int = 5) -> List[str]:
        try:
            vec = self.category_pipeline.named_steps['tfidf']
            clf = self.category_pipeline.named_steps['clf']
            class_idx = list(clf.classes_).index(predicted_class)
            
            # Transform text to sparse vector
            X_sparse = vec.transform([text])
            feature_names = np.array(vec.get_feature_names_out())
            
            # Non-zero indices in input text
            nonzero_indices = X_sparse.nonzero()[1]
            if len(nonzero_indices) == 0:
                return []
                
            # Class coefficients for these features
            coefs = clf.coef_[class_idx, nonzero_indices]
            top_token_indices = nonzero_indices[np.argsort(coefs)[::-1][:top_k]]
            return [str(tok) for tok in feature_names[top_token_indices] if tok.strip()]
        except Exception:
            return []
