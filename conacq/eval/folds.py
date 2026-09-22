"""
Fold I/O for shared cross-validation.

Generate, save, and load pre-generated CV folds so both ConGen
and QuAcq evaluation use identical train/test splits.
"""

import json
import random
import logging
from dataclasses import dataclass, field

from conacq.atomic_io import write_json_atomic
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime


@dataclass
class FoldData:
    """Pre-generated cross-validation fold assignments."""
    n_folds: int
    seed: int
    positive_folds: List[List[int]]  # indices into E+
    negative_folds: List[List[int]]  # indices into E-
    shuffle_seeds: List[int]  # per-fold B shuffle seeds
    metadata: Dict = field(default_factory=dict)


def generate_folds(
        n_positive: int,
        n_negative: int,
        n_folds: int,
        seed: int
) -> FoldData:
    """
    Generate n-fold split indices for E+ and E-.

    Args:
        n_positive: Number of positive examples
        n_negative: Number of negative examples
        n_folds: Number of folds
        seed: Random seed for reproducibility

    Returns:
        FoldData with fold assignments and per-fold shuffle seeds
    """
    rng = random.Random(seed)

    # Shuffle indices for positive and negative examples
    pos_indices = list(range(n_positive))
    neg_indices = list(range(n_negative))
    rng.shuffle(pos_indices)
    rng.shuffle(neg_indices)

    # Distribute into folds (round-robin)
    pos_folds = [[] for _ in range(n_folds)]
    for i, idx in enumerate(pos_indices):
        pos_folds[i % n_folds].append(idx)

    neg_folds = [[] for _ in range(n_folds)]
    for i, idx in enumerate(neg_indices):
        neg_folds[i % n_folds].append(idx)

    # Generate per-fold B shuffle seeds
    shuffle_seeds = [rng.randint(0, 2**31 - 1) for _ in range(n_folds)]

    return FoldData(
        n_folds=n_folds,
        seed=seed,
        positive_folds=pos_folds,
        negative_folds=neg_folds,
        shuffle_seeds=shuffle_seeds,
        metadata={
            'n_pos': n_positive,
            'n_neg': n_negative,
            'created': datetime.now().isoformat()
        }
    )


def save_folds(fold_data: FoldData, filepath: str) -> None:
    """Save fold data to JSON file."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    data = {
        'n_folds': fold_data.n_folds,
        'seed': fold_data.seed,
        'positive_folds': fold_data.positive_folds,
        'negative_folds': fold_data.negative_folds,
        'shuffle_seeds': fold_data.shuffle_seeds,
        'metadata': fold_data.metadata
    }

    write_json_atomic(filepath, data)

    logging.info('Saved %d folds to %s', fold_data.n_folds, filepath)


def load_folds(filepath: str) -> FoldData:
    """Load fold data from JSON file."""
    with open(filepath, 'r') as f:
        data = json.load(f)

    return FoldData(
        n_folds=data['n_folds'],
        seed=data['seed'],
        positive_folds=data['positive_folds'],
        negative_folds=data['negative_folds'],
        shuffle_seeds=data['shuffle_seeds'],
        metadata=data.get('metadata', {})
    )


def apply_folds(
        fold_data: FoldData,
        positive_examples: List,
        negative_examples: List,
        fold_idx: int
) -> Tuple[List, List, List, List]:
    """
    Apply fold assignments to get train/test splits.

    Args:
        fold_data: Pre-generated fold assignments
        positive_examples: Full list of E+
        negative_examples: Full list of E-
        fold_idx: Which fold to use as test set

    Returns:
        (train_pos, train_neg, test_pos, test_neg)
    """
    # Test set: current fold
    test_pos = [positive_examples[i] for i in fold_data.positive_folds[fold_idx]]
    test_neg = [negative_examples[i] for i in fold_data.negative_folds[fold_idx]]

    # Train set: all other folds
    train_pos = []
    train_neg = []
    for i in range(fold_data.n_folds):
        if i != fold_idx:
            train_pos.extend(positive_examples[j] for j in fold_data.positive_folds[i])
            train_neg.extend(negative_examples[j] for j in fold_data.negative_folds[i])

    return train_pos, train_neg, test_pos, test_neg
