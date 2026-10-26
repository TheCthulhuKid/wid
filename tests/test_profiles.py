from wid.profiles import PROFILES, Genre


def test_core_profile():
    core = PROFILES[Genre.CORE]
    assert core.attributes == ("Athleticism", "Composure", "Reasoning")
    assert core.uses_items
    assert not any((core.has_powers, core.has_tech, core.has_rerolls))


def test_genre_labels_and_capabilities():
    expected = {
        Genre.HECKBOY: (("Aberrance", "Ferocity", "Savvy"), True, False, False, True),
        Genre.SECOND_CONTACT: (("Science", "Culture", "Muscle"), False, True, False, False),
        Genre.OLDHEART: (("Depravity", "Hospitality", "Fitness"), False, False, True, True),
        Genre.BALL_SEASON: (("Propriety", "Stoutness", "Yearning"), False, False, False, True),
        Genre.THIS_ISNT_HAPPENING: (
            ("Instincts", "Endurance", "Charity"),
            False,
            False,
            False,
            True,
        ),
    }
    assert set(PROFILES) == set(Genre)
    for genre, values in expected.items():
        profile = PROFILES[genre]
        assert (
            profile.attributes,
            profile.has_powers,
            profile.has_tech,
            profile.has_rerolls,
            profile.uses_items,
        ) == values
