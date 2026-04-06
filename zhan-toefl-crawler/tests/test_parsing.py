from zhan_toefl_crawler.crawler import clean_html_text, extract_correct_answer, extract_question_options


def test_extract_correct_answer():
    html = '<div class="left correctAnswer">正确答案：<span>BDE</span></div>'
    assert extract_correct_answer(html) == "BDE"


def test_extract_question_options_from_labels():
    html = """
    <label for="option1">A. First option</label>
    <label for="option2">B. Second option</label>
    """
    assert extract_question_options(html) == ["A. First option", "B. Second option"]


def test_clean_html_text_preserves_insert_markers():
    html = '<span class="insert-area" data-answer="C"></span>Some text<br/>Next line'
    assert clean_html_text(html, preserve_breaks=True) == "[C]Some text\nNext line"
