"""peer_review.services — consensus engine + reviewer assigner.

Public API surface
------------------
* :func:`consensus_engine.compute_consensus`
* :func:`consensus_engine.escalate_to_qa`
* :func:`consensus_engine.timeout_sweep`
* :func:`reviewer_assigner.assign_reviewers`
* :func:`reviewer_assigner.is_pair_in_cooldown`
"""

from peer_review.services import consensus_engine, reviewer_assigner  # noqa: F401

__all__ = ['consensus_engine', 'reviewer_assigner']
