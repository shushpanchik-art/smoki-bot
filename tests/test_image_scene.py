"""U5: image-prompt строится из сцены, извлечённой из тела статьи."""
from ai import prompts


def test_scene_prompt_contains_body():
    body = "Кальян на углях: как выбрать чашу и табак."
    p = prompts.image_scene_prompt(body)
    assert "ARTICLE:" in p
    assert body[:20] in p
    assert "English" in p


def test_prompt_from_scene_keeps_constraints():
    scene = "A dim lounge with a brass hookah glowing amber, moody teal palette."
    topic = "кальян"
    p = prompts.image_prompt_from_scene(scene, topic)
    assert "NO TEXT" in p
    assert "FILL THE ENTIRE FRAME" in p
    assert topic in p
    assert scene[:30] in p


def test_prompt_from_scene_trims_long_scene():
    scene = "x" * 1000
    p = prompts.image_prompt_from_scene(scene, "тест")
    # сцена усечена до 300 символов
    assert "x" * 301 not in p
