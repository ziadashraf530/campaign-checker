"""
embedding_analysis.py
======================
Evaluates the internal consistency and cohesion of campaign reference sets,
calculating intra-set variance, silhouette coefficients against competitor assets,
and identifying outlier reference images that might pollute the matching centroid.
Also groups reference campaign images into distinct visual categories using K-Means.
"""

from __future__ import annotations
import numpy as np

class EmbeddingAnalyzer:
    """
    Analyzes reference sets to detect cluster cohesion, identify outliers,
    and group them into visual categories to prevent embedding dilution.
    """

    @classmethod
    def cluster_references(
        cls,
        embeddings: np.ndarray,
        names: list[str],
        max_clusters: int = 3
    ) -> list[dict]:
        """
        Group campaign reference images into distinct visual categories
        using a robust pure-NumPy Cosine-distance K-Means.
        
        Returns:
            list[dict]: A list of clusters, each containing:
                centroid: np.ndarray
                member_indices: list[int]
                member_names: list[str]
                label: str
                variance: float
                avg_similarity: float
        """
        num_refs = len(embeddings)
        if num_refs == 0:
            return []

        k = min(max_clusters, num_refs)
        if k <= 1:
            centroid = embeddings.mean(axis=0)
            centroid = centroid / np.linalg.norm(centroid)
            sims = embeddings @ centroid
            avg_sim = float(np.mean(sims))
            var = float(np.std(sims))
            
            # Simple category label for single cluster
            if avg_sim > 0.88:
                label = "Brand Logo & Focus"
            elif avg_sim > 0.78:
                label = "Product & Drink Close-ups"
            else:
                label = "Ambient / Interior Scenes"

            return [{
                "centroid": centroid,
                "member_indices": list(range(num_refs)),
                "member_names": names,
                "label": label,
                "variance": var,
                "avg_similarity": avg_sim
            }]

        # K-Means++ initialization based on Cosine Distance (1 - dot_product)
        # Select first center randomly or using first index
        centers = [embeddings[0]]
        for _ in range(1, k):
            # Compute distance of all points to already selected centers
            dists = []
            for center in centers:
                dists.append(1.0 - (embeddings @ center))
            min_dists = np.min(dists, axis=0)
            # Pick center with maximum distance
            next_idx = np.argmax(min_dists)
            centers.append(embeddings[next_idx])
        
        centers = np.array(centers)
        assignments = np.zeros(num_refs, dtype=int)
        
        # Optimize clusters
        for _ in range(20):
            # Compute similarity to all centers
            sims = embeddings @ centers.T # (num_refs, k)
            new_assignments = np.argmax(sims, axis=1)
            
            # If no change in assignments, stop
            if np.array_equal(assignments, new_assignments):
                break
            assignments = new_assignments
            
            # Recompute centers
            for j in range(k):
                mask = assignments == j
                if np.any(mask):
                    mean_emb = embeddings[mask].mean(axis=0)
                    centers[j] = mean_emb / np.linalg.norm(mean_emb)

        # Build return structure
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
            
            # Dynamic Label Assignment based on visual cohesion profile
            if avg_sim > 0.88:
                label = f"Brand Logo & Focus (Cluster {j+1})"
            elif avg_sim > 0.78:
                label = f"Product & Drink Close-ups (Cluster {j+1})"
            else:
                label = f"Ambient / Interior Scenes (Cluster {j+1})"

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
    def evaluate_campaign_cohesion(
        cls,
        pos_embeddings: np.ndarray,
        pos_names: list[str],
        neg_embeddings: np.ndarray | None = None
    ) -> dict:
        """
        Evaluate reference bank quality, detect outliers, and generate recommendations.
        """
        if pos_embeddings is None or len(pos_embeddings) == 0:
            return {
                "cluster_quality": "WEAK",
                "intra_similarity_mean": 0.0,
                "intra_similarity_std": 0.0,
                "silhouette_score": 0.0,
                "outliers": [],
                "recommendations": ["No positive references loaded."]
            }

        num_refs = len(pos_embeddings)
        
        # 1. Compute pairwise similarity matrix for positives
        # Because embeddings are normalized, dot product = cosine similarity
        pairwise_sims = pos_embeddings @ pos_embeddings.T
        
        # Extract upper triangle (excluding diagonal) to get unique pairs
        if num_refs > 1:
            triu_indices = np.triu_indices(num_refs, k=1)
            pair_similarities = pairwise_sims[triu_indices]
            intra_mean = float(np.mean(pair_similarities))
            intra_std = float(np.std(pair_similarities))
        else:
            intra_mean = 1.0
            intra_std = 0.0

        # 2. Identify outlier references
        # Calculate similarity of each reference to the global centroid
        centroid = pos_embeddings.mean(axis=0)
        centroid = centroid / np.linalg.norm(centroid)
        centroid_sims = pos_embeddings @ centroid
        
        outliers = []
        for idx, sim in enumerate(centroid_sims):
            # Threshold: any reference image with similarity to centroid < 0.68 is an outlier
            if sim < 0.68:
                outliers.append(pos_names[idx])
                
        # 3. Silhouette Cohesion Score against hard negatives
        silhouette_score = 1.0
        if neg_embeddings is not None and len(neg_embeddings) > 0:
            # Distance = 1.0 - cosine_similarity
            # For each positive point:
            # a = mean distance to other positives
            # b = mean distance to negatives
            # s = (b - a) / max(a, b)
            s_scores = []
            for i in range(num_refs):
                # distance to positives
                pos_dists = 1.0 - pairwise_sims[i]
                # exclude self (distance = 0)
                a = pos_dists[np.arange(num_refs) != i].mean() if num_refs > 1 else 0.0
                
                # distance to negatives
                neg_dists = 1.0 - (pos_embeddings[i] @ neg_embeddings.T)
                b = neg_dists.mean()
                
                s = (b - a) / max(a, b) if max(a, b) > 0 else 0.0
                s_scores.append(s)
            silhouette_score = float(np.mean(s_scores))
        else:
            # If no negatives exist, represent cohesion via pairwise similarity
            # Scale from [0.5, 1.0] -> [0.0, 1.0]
            silhouette_score = float(np.clip((intra_mean - 0.5) * 2.0, 0.0, 1.0))

        # 4. Determine overall quality
        if silhouette_score > 0.65 and len(outliers) == 0:
            cluster_quality = "EXCELLENT"
        elif silhouette_score > 0.40 and len(outliers) <= 1:
            cluster_quality = "GOOD"
        else:
            cluster_quality = "WEAK"

        # 5. Generate action-oriented recommendations
        recommendations = []
        if cluster_quality == "EXCELLENT":
            recommendations.append("Campaign references are highly cohesive. Decision boundaries will be narrow and robust.")
        elif cluster_quality == "GOOD":
            recommendations.append("Campaign reference set has nominal cohesion. Solid overall visual representation.")
            if outliers:
                recommendations.append(f"Consider removing outlier image '{outliers[0]}' to reduce ambient background overlap.")
        else:
            recommendations.append("Weak reference set! The campaign images are visually disparate (lifestyle/varying styles).")
            if outliers:
                recommendations.append(f"CRITICAL: We recommend replacing outlier images: {', '.join(outliers)}.")
            if num_refs < 3:
                recommendations.append("Increase reference set size to 3+ images to generate a more stable campaign centroid.")

        return {
            "cluster_quality": cluster_quality,
            "intra_similarity_mean": round(intra_mean, 4),
            "intra_similarity_std": round(intra_std, 4),
            "silhouette_score": round(silhouette_score, 4),
            "outliers": outliers,
            "recommendations": recommendations
        }
