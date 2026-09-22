"""Characterization tests pinning the FeatureModel → DiagnosisModel transform.

``FmToDiagPysat`` turns a flamapy ``FeatureModel`` into a ``DiagnosisModel`` (SAT
variable catalog + constraint clause maps + the next free assumption id). These
values MUST stay byte-identical across the redesign — the whole system's
diagnoses depend on the exact feature→id assignment, which flamapy derives from
its tree-traversal order (NOT alphabetical). No test pinned this before; these
lock it against silent drift.

The fixture is ``arcade-game.uvl`` (65 features) — small enough to pin the full
name→id catalog inline, which is the strongest possible characterization of the
traversal-order invariant.
"""
from flamapy.metamodels.fm_metamodel.transformations import UVLReader

from explanation.transformations.fm_to_diag_pysat import FmToDiagPysat
from explanation.transformations.dimacs_to_diag_pysat import DimacsToDiagPysat
from tests.resource_paths import DATA_DIR, RESOURCES_DIR, CNF_PROD

_ARCADE_FM = str(DATA_DIR / "fms" / "arcade-game.uvl")
_INCOMPLETE_CATALOG_CNF = str(RESOURCES_DIR / "incomplete_catalog.cnf")

# Feature names in SAT-variable-id order (id == index + 1). This is the
# flamapy tree-traversal order; ArcadeGame is the root (id 1).
EXPECTED_FEATURES_IN_ID_ORDER = [
    "ArcadeGame", "UseCases", "CheckPreviousBestScore", "SaveScore", "SaveGame",
    "ExitGame", "InstallGame", "UninstallGame", "ListGame", "PlayGame",
    "PlayGame_1", "PlayBrickles", "PlayPong", "PlayBowling", "Initialization",
    "AnimationLoop", "ClassDiagram", "GameSprite", "SpritePair", "Rectangle",
    "Size", "Point", "GameSprite_3", "MovableSprite", "StationarySprite",
    "Velocity", "MovableSprite_2", "Paddle", "Puck", "BowlingBall",
    "BowlingPin", "TopPaddle", "BottomPaddle", "Wall", "Leftpong",
    "Rightpont", "Leftbrickles", "Rightbrickles", "StationarySprite_2", "Brick",
    "BrickPile", "Ceilingbrickles", "Floorbrickles", "Lane", "Gutter",
    "Edge", "EndofAlley", "RackofPins", "ScoreBoard", "Floorpong",
    "Ceilingpong", "DividingLine", "Pucksupply", "Board", "PongBoard",
    "BricklesBoard", "BowlingBoard", "Menu", "Pong", "Brickles",
    "Bowling", "GameMenu", "PongGameMenu", "BricklesGameMenu", "BowlingGameMenu",
]

_N_FEATURES = len(EXPECTED_FEATURES_IN_ID_ORDER)  # 65


def _transform(create_negation: bool):
    fm = UVLReader(_ARCADE_FM).transform()
    return FmToDiagPysat(fm, create_negation=create_negation).transform()


def test_feature_id_catalog_matches_tree_traversal_order():
    model = _transform(create_negation=True)
    expected = {name: i + 1 for i, name in enumerate(EXPECTED_FEATURES_IN_ID_ORDER)}
    assert dict(model.variables) == expected


def test_name_to_id_is_a_bijection_with_id_to_name():
    model = _transform(create_negation=True)
    assert len(model.variables) == _N_FEATURES
    # variables (name→id) and features (id→name) are mutual inverses.
    assert {v: k for k, v in model.variables.items()} == dict(model.features)


def test_constraint_maps_populated_with_negated_forms():
    model = _transform(create_negation=True)
    assert len(model.constraint_map) == 71
    # With negation requested, every constraint gets a NOT(...) counterpart.
    assert len(model.negated_constraint_map) == 71
    assert all(k.startswith("NOT(") for k in model.negated_constraint_map)


def test_next_available_id_reserves_tseitin_range_when_negating():
    model = _transform(create_negation=True)
    # Tseitin vars are allocated after the 65 feature vars, pushing the next
    # free assumption id to 156.
    assert model.next_available_id == 156


def test_next_available_id_is_feature_count_plus_one_without_negation():
    model = _transform(create_negation=False)
    assert len(model.negated_constraint_map) == 0
    assert model.next_available_id == _N_FEATURES + 1  # 66


# --- DIMACS transform: next_available_id must clear every clause variable ------

def test_dimacs_next_available_id_clears_every_clause_variable():
    """``next_available_id`` must sit strictly above every variable that appears in
    a clause. Task preparation allocates assumption/Tseitin ids starting there; if
    it lands on a real variable the diagnosis is silently wrong. The ``c`` catalog
    can be incomplete — a clause may use a variable no ``c`` line declares — so the
    floor must come from the ``p cnf <nvars>`` header, not ``len(catalog)``.

    Fixture: 2 ``c`` lines, but ``p cnf 5`` and clause ``4 -5 0`` uses variable 5.
    """
    model = DimacsToDiagPysat(_INCOMPLETE_CATALOG_CNF, create_negation=False).transform()
    max_clause_var = 5  # highest variable used in any clause of the fixture
    assert model.next_available_id > max_clause_var


def test_dimacs_next_available_id_unchanged_for_complete_catalog():
    """Behaviour-inert guard: with a complete catalog (``len(catalog) == nvars``),
    ``max(nvars, len(catalog)) + 1`` equals ``len(catalog) + 1`` — the id floor
    changes nothing on the real fixtures (only rescues an incomplete catalog)."""
    model = DimacsToDiagPysat(str(CNF_PROD), create_negation=False).transform()
    assert model.next_available_id == len(model.variables) + 1
