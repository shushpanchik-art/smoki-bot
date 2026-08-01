from ai.prompts import saga_prompt, _saga_memory

ST = {
    "episode_in_arc": 2, "arc_number": 1,
    "arc_goal": "захватить рынок картриджей",
    "harmon_stage": "4-Поиск", "narration": "третье лицо",
    "planned_arc_length": 6,
    "characters_json": '{"main":[]}',
    "locations_json": "[]", "arc_synopsis_json": "[]",
}
SM = [
    {"episode_number": 1, "arc_number": 1, "summary": "Воронцов узнал о рейде"},
    {"episode_number": 2, "arc_number": 1, "summary": "Партнёр слил поставку"},
]


def test_first_episode():
    p = saga_prompt(None)
    assert "ПЕРВЫЙ ЭПИЗОД" in p
    assert "индустрии курения" in p
    assert "выбери форму повествования" in p.lower()
    assert "===META===" in p
    # при первом эпизоде state нет — harmon_stage не подставляется
    assert "1-Ты" in p


def test_regular_episode():
    p = saga_prompt(ST, SM)
    assert "третье лицо" in p
    assert "захватить рынок картриджей" in p
    assert "Воронцов узнал о рейде" in p
    assert "ПОСЛЕДНИЕ ЭПИЗОДЫ" in p


def test_force_finale():
    p = saga_prompt(ST, SM, force_finale=True)
    assert "ФИНАЛЬНЫЙ ЭПИЗОД АРКИ" in p
    assert "completed" in p
    assert "РОВНО ОДНУ" in p
    assert "pending_arc_seed" in p


def test_near_finale_warning():
    st = dict(ST, episode_in_arc=5, planned_arc_length=6)
    assert "близится к финалу" in saga_prompt(st, SM)


def test_memory_synopses():
    st = dict(ST, arc_synopsis_json='["Арка про табачную мафию рухнула"]')
    m = _saga_memory(st, SM)
    assert "СИНОПСИСЫ ЗАВЕРШЁННЫХ АРОК" in m
    assert "табачную мафию" in m


def test_memory_update_hints():
    m = _saga_memory(ST, SM)
    assert "обнови этот JSON и верни в meta.characters" in m
    assert "main<=3" in m


def test_memory_empty_state():
    assert "ПЕРВЫЙ ЭПИЗОД" in _saga_memory(None, None)


def test_char_limits_in_rules():
    p = saga_prompt(None)
    assert "не больше 3" in p.lower()
    assert "не больше 5" in p.lower()


def test_no_from_nowhere_rule():
    p = saga_prompt(None)
    assert "из ниоткуда" in p


def test_word_range():
    p = saga_prompt(None)
    assert "700-1000" in p


def test_quotes_rule():
    """Баг 6: правило про русские ёлочки в кавычках."""
    p = saga_prompt(None)
    assert "\u00ab...\u00bb" in p  # «...»
    assert "\u0451лочк" in p.lower() or "\u0435лочк" in p.lower()
    assert "12. \u041a\u0410\u0412\u042b\u0427\u041a\u0418" in p


def test_no_italic_brands_rule():
    """Баг 7: запрет курсива на брендах/марках."""
    p = saga_prompt(None)
    assert "13. \u041a\u0423\u0420\u0421\u0418\u0412" in p
    assert "iPhone" in p and "Porsche" in p
    assert "VapeCorp" in p and "\u0410\u043b\u044c\u0444\u0430" in p
    low = p.lower()
    assert "\u0437\u0430\u043f\u0440\u0435\u0449\u0435\u043d\u043e \u0432\u044b\u0434\u0435\u043b\u044f\u0442\u044c \u043a\u0443\u0440\u0441\u0438\u0432\u043e\u043c" in low


def test_link_to_previous_rule():
    """Баг 2: первый абзац продолжает прошлый эпизод."""
    p = saga_prompt(None)
    assert "14. \u0421\u0412\u042f\u0417\u042c \u0421 \u041f\u0420\u0415\u0414\u042b\u0414\u0423\u0429\u0418\u041c" in p
