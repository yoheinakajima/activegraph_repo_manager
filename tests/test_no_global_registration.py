import importlib


def test_pack_import_has_no_registration_side_effects() -> None:
    pack_module = importlib.import_module("activegraph_repo_manager.pack")
    pack = getattr(pack_module, "pack")
    assert pack.name == "activegraph_repo_manager"
    assert isinstance(pack.relations, tuple)
    assert isinstance(pack.behavior_modules, tuple)
    assert isinstance(pack.tool_modules, tuple)
