"""
reference_cluster_engine.py
===========================
Pure-NumPy Cosine Distance K-Means reference image clustering engine.
Categorizes campaign reference images into logo_refs, drink_refs, product_refs, and store_refs.
Detects dominant cluster matching for target query embeddings to prevent dilution.
"""

from __future__ import annotations
import numpy as np

class ReferenceClusterEngine:
    """
    Groups campaign references into visual semantic categories and maps query embeddings
    to the most relevant category.
    """

    CATEGORIES = {
        "logo_refs": ["logo", "brand", "badge", "sign", "symbol", "icon", "wordmark", "emblem", "vector"],
        "drink_refs": ["drink", "cup", "coffee", "mug", "beverage", "tea", "straw", "glass", "liquid", "cold", "hot", "latte", "espresso", "cappuccino"],
        "product_refs": ["product", "merch", "bottle", "can", "bag", "package", "box", "item", "tumbler", "packaging"],
        "store_refs": ["store", "interior", "cafe", "shop", "counter", "background", "ambient", "building", "table", "seat", "room", "facade", "outdoor", "street"]
    }

    @classmethod
    def _assign_category_label(cls, member_names: list[str], avg_similarity: float) -> str:
        """
        Assign one of the four standard categories based on filename keywords or visual characteristics.
        """
        counts = {cat: 0 for cat in cls.CATEGORIES}
        
        for name in member_names:
            name_lower = name.lower()
            for cat, keywords in cls.CATEGORIES.items():
                if any(kw in name_lower for kw in keywords):
                    counts[cat] += 1

        # Find the category with maximum keyword hits
        max_cat = max(counts, key=counts.get)
        if counts[max_cat] > 0:
            return max_cat

        # Fallback to visual profile if no filename keyword matches
        if avg_similarity > 0.88:
            return "logo_refs"
        elif avg_similarity > 0.78:
            return "drink_refs"  # Default drink / product focus
        else:
            return "store_refs"

    @classmethod
    def cluster_reference_set(
        cls,
        embeddings: np.ndarray,
        names: list[str],
        max_clusters: int = 4
    ) -> list[dict]:
        """
        Cluster campaign reference image embeddings using K-Means with Cosine distance.
        Assigns standard category labels to each cluster.
        """
        num_refs = len(embeddings)
        if num_refs == 0:
            return []

        # Determine K dynamically
        k = min(max_clusters, num_refs)
        if k <= 1:
            centroid = embeddings.mean(axis=0)
            centroid = centroid / np.linalg.norm(centroid)
            sims = embeddings @ centroid
            avg_sim = float(np.mean(sims))
            var = float(np.std(sims)) if len(sims) > 1 else 0.0
            label = cls._assign_category_label(names, avg_sim)
            
            return [{
                "centroid": centroid,
                "member_indices": list(range(num_refs)),
                "member_names": names,
                "label": label,
                "variance": var,
                "avg_similarity": avg_sim
            }]

        # K-Means++ initialization based on Cosine Distance (1 - dot_product)
        centers = [embeddings[0]]
        for _ in range(1, k):
            dists = []
            for center in centers:
                dists.append(1.0 - (embeddings @ center))
            min_dists = np.min(dists, axis=0)
            next_idx = np.argmax(min_dists)
            centers.append(embeddings[next_idx])
        
        centers = np.array(centers)
        assignments = np.zeros(num_refs, dtype=int)
        
        # Iteratively optimize clusters
        for _ in range(25):
            sims = embeddings @ centers.T  # (num_refs, k)
            new_assignments = np.argmax(sims, axis=1)
            
            if np.array_equal(assignments, new_assignments):
                break
            assignments = new_assignments
            
            for j in range(k):
                mask = assignments == j
                if np.any(mask):
                    mean_emb = embeddings[mask].mean(axis=0)
                    centers[j] = mean_emb / np.linalg.norm(mean_emb)

        # Build output structure and label clusters
        clusters = []
        for j in range(k):
            mask = assignments == j
            if not np.any(mask):
                continue
                
            member_indices = np.where(mask)[0].tolist()
            member_names = [names[i] for i in member_indices]
            
            cluster_embeddings = embeddings[mask]
            centroid = centers[j]
            cluster_sims = cluster_embeddings @ centroid
            avg_sim = float(np.mean(cluster_sims))
            var = float(np.std(cluster_sims)) if len(cluster_sims) > 1 else 0.0
            
            label = cls._assign_category_label(member_names, avg_sim)

            clusters.append({
                "centroid": centroid,
                "member_indices": member_indices,
                "member_names": member_names,
                "label": label,
                "variance": var,
                "avg_similarity": avg_sim
            })

        return clusters

    @classmethod
    def detect_dominant_cluster(cls, query_embedding: np.ndarray, clusters: list[dict]) -> dict:
        """
        Identify the dominant reference cluster matching the query embedding.
        
        Returns:
            dict containing:
                dominant_cluster (str): Name of the cluster (logo_refs, drink_refs, etc.)
                cluster_similarity (float): Cosine similarity to the centroid of this cluster
                cluster_confidence (str): Confidence level (HIGH, MEDIUM, LOW)
                member_names (list[str]): Names of reference files in this cluster
                member_indices (list[int]): Indices of references in the bank
                centroid (np.ndarray): Centroid of the cluster
        """
        if not clusters:
            return {
                "dominant_cluster": "store_refs",
                "cluster_similarity": 0.0,
                "cluster_confidence": "LOW",
                "member_names": [],
                "member_indices": [],
                "centroid": np.zeros(1)
            }

        best_sim = -1.0
        best_cluster = clusters[0]
        
        for cluster in clusters:
            sim = float(query_embedding @ cluster["centroid"])
            if sim > best_sim:
                best_sim = sim
                best_cluster = cluster

        # Map similarity to categorical confidence
        if best_sim >= 0.80:
            confidence = "HIGH"
        elif best_sim >= 0.70:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        return {
            "dominant_cluster": best_cluster["label"],
            "cluster_similarity": round(best_sim, 4),
            "cluster_confidence": confidence,
            "member_names": best_cluster["member_names"],
            "member_indices": best_cluster["member_indices"],
            "centroid": best_cluster["centroid"]
        }
