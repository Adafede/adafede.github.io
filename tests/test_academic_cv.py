from scripts.site.academic_cv import publication_list, talk_list


def test_academic_cv_uses_quarto_publication_and_talk_metadata():
    publications = publication_list()
    talks = talk_list().splitlines()

    assert len(talks) == 21
    assert "Development of a Generic Method" in talks[-1]
    assert "**Adriano Rutz**$^{*}$" in publications
    assert "**Adriano Rutz**$^{\\dagger}$" in publications
    assert "Mehdi A. Beniddir$^{\\ddagger *}$" in publications
    assert "Justin J. J. van der Hooft" in publications
