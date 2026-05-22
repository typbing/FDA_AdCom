from fda_adcom.fda_monitor import (
    extract_documents_from_html,
    is_relevant_document,
    is_relevant_page,
)


def test_relevant_document_accepts_briefing_media_download() -> None:
    assert is_relevant_document(
        "March 22, 2023 Meeting- FDA Briefing Document",
        "https://www.fda.gov/media/166326/download",
    )


def test_relevant_document_rejects_roster_and_transcript() -> None:
    assert not is_relevant_document(
        "March 22, 2023 Meeting- Final Meeting Roster",
        "https://www.fda.gov/media/166390/download",
    )
    assert not is_relevant_document(
        "March 22, 2023 Meeting- Transcript",
        "https://www.fda.gov/media/168221/download",
    )


def test_relevant_page_accepts_meeting_materials_and_announcement() -> None:
    assert is_relevant_page(
        "https://www.fda.gov/advisory-committees/peripheral-and-central-nervous-system-drugs-advisory-committee/2023-meeting-materials-peripheral-and-central-nervous-system-drugs-advisory-committee"
    )
    assert is_relevant_page(
        "https://www.fda.gov/advisory-committees/advisory-committee-calendar/march-22-2023-meeting-announcement"
    )


def test_extract_documents_from_html_filters_to_actionable_pdfs() -> None:
    html = """
    <a href="/media/166326/download">March 22, 2023 Meeting- FDA Briefing Document</a>
    <a href="/media/166327/download">March 22, 2023 Meeting- Biogen Briefing Document</a>
    <a href="/media/166391/download">March 22, 2023 Meeting- Final Questions</a>
    <a href="/media/166390/download">March 22, 2023 Meeting- Final Meeting Roster</a>
    <a href="/media/168221/download">March 22, 2023 Meeting- Transcript</a>
    """
    docs = extract_documents_from_html(
        html,
        "https://www.fda.gov/advisory-committees/advisory-committee-calendar/example",
        "2026-05-21T00:00:00+00:00",
    )
    assert [doc.title for doc in docs] == [
        "March 22, 2023 Meeting- FDA Briefing Document",
        "March 22, 2023 Meeting- Biogen Briefing Document",
        "March 22, 2023 Meeting- Final Questions",
    ]
