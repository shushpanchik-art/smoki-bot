"""U6.2a: smoke story-промптов и env-ключей."""
import config
from ai import prompts


def test_story_weights_defaults():
    assert config.STORY_WEIGHT_JOKE == 15
    assert config.STORY_WEIGHT_NEWS == 25
    assert config.STORY_WEIGHT_NEW_PRODUCTS == 25
    assert config.STORY_WEIGHT_FACT == 30
    assert config.STORY_WEIGHT_WISH == 5
    total = (config.STORY_WEIGHT_JOKE + config.STORY_WEIGHT_NEWS +
             config.STORY_WEIGHT_NEW_PRODUCTS + config.STORY_WEIGHT_FACT +
             config.STORY_WEIGHT_WISH)
    assert total == 100


def test_story_per_day_ranges():
    assert config.STORY_CHANNEL_MIN_PER_DAY == 3
    assert config.STORY_CHANNEL_MAX_PER_DAY == 7
    assert config.STORY_FLOOD_MIN_PER_DAY == 5
    assert config.STORY_FLOOD_MAX_PER_DAY == 12
    assert config.STORY_APPROVE_TIMEOUT_MIN == 60


def test_story_themes_1_to_5():
    assert set(prompts.STORY_THEMES) == {1, 2, 3, 4, 5}


def test_story_text_prompt_no_calltoaction_rules():
    p = prompts.story_text_prompt(1)
    assert "@SMOKTOLK" in p
    assert "Stories" in p
    # промпт содержит правила цензуры
    assert "медсоветов" in p or "медицин" in p.lower()


def test_story_text_prompt_with_search():
    p = prompts.story_text_prompt(2, search_snippet="свежая новость X")
    assert "свежая новость X" in p


def test_story_flood_caption_prompt():
    p = prompts.story_flood_caption_prompt(4)
    assert "20-50 слов" in p


def test_story_image_prompt_vertical():
    p = prompts.story_image_prompt("neon vape shop at night")
    assert "9:16" in p
    assert "1080x1920" in p
    assert "RUSSIAN" in p
    assert "neon vape shop at night" in p
