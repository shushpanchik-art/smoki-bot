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
    assert "600-1000" in p
