import json
import pytest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.analyzer import extract_and_validate_jd_reqs, generate_report
from app.services.pdf_service import create_tailored_pdf, extract_text_from_pdf


def test_multiline_pdf(tmp_path):
    with patch('app.services.pdf_service.TEMP_PDF_DIR', tmp_path):
        file_id = create_tailored_pdf('EXPERIENCE\nReact and TypeScript\n' + 'A' * 500 + '\nEducation', 'test')
        text = extract_text_from_pdf((tmp_path / f'{file_id}.pdf').read_bytes())
    assert 'Education' in text
    assert 'React and TypeScript' in text


def test_explicit_preferences():
    requirements = [
        {'skill': skill, 'priority': 'not_required', 'evidence': f'{skill} experience is preferred.'}
        for skill in ['Redux', 'Redis', 'Kubernetes']
    ]
    requirements.append({'skill': 'Flutter', 'priority': 'required', 'evidence': 'Flutter is not required.'})
    response = SimpleNamespace(message=SimpleNamespace(content=json.dumps({'requirements': requirements})))
    with patch('app.services.analyzer.chat', return_value=response):
        result = extract_and_validate_jd_reqs({'job_description': ' '.join(r['evidence'] for r in requirements)})
    assert [r['priority'] for r in result['requirements']] == ['preferred'] * 3 + ['not_required']


def test_report_has_real_newlines():
    with patch('app.services.analyzer.create_tailored_pdf', return_value='test-id'):
        result = generate_report({'resume_txt': 'Original resume', 'owner': 'test'})
    assert '\n' in result['report']
    assert r'\n' not in result['report']
    assert result['download_id'] == 'test-id'


def test_model_timeout_is_not_retried():
    import pytest
    with patch('app.services.analyzer.chat', side_effect=TimeoutError('Model timed out')) as mocked:
        with pytest.raises(TimeoutError):
            extract_and_validate_jd_reqs({'job_description': 'React required.'})
    assert mocked.call_count == 1


def test_endpoint_timeout_returns_504():
    import asyncio
    import io
    import pytest
    from fastapi import UploadFile, HTTPException
    from app.routers.analyzer import analyze_resume
    with patch('app.routers.analyzer.run_analyzer_sync', side_effect=TimeoutError('Model timed out')):
        with pytest.raises(HTTPException) as error:
            asyncio.run(analyze_resume(UploadFile(filename='resume.pdf', file=io.BytesIO(b'test')), 'React required.', 'test'))
    assert error.value.status_code == 504


def test_tailoring_timeout_preserves_analysis():
    from app.services.analyzer import tailor_resume
    state = {'resume_txt': 'Original resume', 'mention_skills': ['react'],
             'preferred_skills_matched': [], 'non_mention_skills': [], 'warnings': []}
    with patch('app.services.analyzer.chat', side_effect=TimeoutError('slow')) as mocked:
        result = tailor_resume(state)
    assert result['tailored_resume_text'] == 'Original resume'
    assert result['changes_made'] == []
    assert 'timed out' in result['warnings'][0]
    assert mocked.call_count == 1


def test_analysis_only_skips_tailoring():
    from app.services.analyzer import tailor_resume
    with patch('app.services.analyzer.chat') as mocked:
        result = tailor_resume({'tailor_requested': False, 'resume_txt': 'Original resume'})
    mocked.assert_not_called()
    assert result['tailored_resume_text'] == 'Original resume'


def test_extraction_warning_identifies_rejected_skills():
    requirements = [
        {'skill': 'React', 'priority': 'required', 'evidence': 'React required.'},
        {'skill': 'Rust', 'priority': 'required', 'evidence': 'Invented Rust quote.'},
        {'skill': 'Scala', 'priority': 'required', 'evidence': 'Collaborate with the team.'},
    ]
    response = SimpleNamespace(message=SimpleNamespace(content=json.dumps({'requirements': requirements})))
    with patch('app.services.analyzer.chat', return_value=response) as mocked:
        result = extract_and_validate_jd_reqs({
            'job_description': 'React required. Rust required. Scala required. Collaborate with the team.'
        })
    assert mocked.call_count == 3
    assert [r['skill'] for r in result['requirements']] == ['react']
    assert any('Rust' in warning and 'could not be grounded' in warning for warning in result['warnings'])
    assert any('Scala' in warning and 'could not be grounded' in warning for warning in result['warnings'])


def test_unspecified_skills_are_included_in_primary_coverage():
    from app.services.analyzer import match_skills
    result = match_skills({
        'resume_txt': 'Built React.js apps with Next.js, Redux, Jest, and REST APIs.',
        'requirements': [
            {'skill': skill, 'priority': 'unspecified', 'evidence': skill}
            for skill in ['react', 'next.js', 'redux', 'jest', 'rest apis', 'typescript']
        ],
    })
    assert set(result['mention_skills']) == {'react', 'next.js', 'redux', 'jest', 'rest apis'}
    assert result['non_mention_skills'] == ['typescript']


def test_relaxed_evidence_accepts_punctuation_but_not_invented_quotes():
    from app.services.analyzer import resolve_evidence
    jd = 'Experience with React, Next.js, and Redux is required.'
    assert resolve_evidence(jd, 'Experience with React Next.js and Redux is required', 'react') == jd
    assert resolve_evidence(jd, 'We build amazing Rust services.', 'rust') is None


def test_tailoring_rejects_sections_missing_from_source():
    from app.schemas.analyzer import TailoredContent
    from app.services.analyzer import validate_tailored_content
    tailored = TailoredContent.model_validate({
        'sections': [{'heading': 'Employment', 'content': 'Engineer, XYZ Company | 2020 - Present'}],
        'changes_made': [], 'suggestions': [],
    })
    with pytest.raises(ValueError, match='unstructured source'):
        validate_tailored_content('Raja is a Python and FastAPI engineer.', tailored)


def test_short_text_pdf_is_accepted(tmp_path):
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', size=12)
    pdf.cell(0, 10, text='Jane Doe - Skills: Java')
    path = tmp_path / 'short.pdf'
    pdf.output(path)
    assert 'Java' in extract_text_from_pdf(path.read_bytes())


def test_known_skills_repair_wrong_quotes_and_omissions():
    jd = '''Responsibilities
Build responsive interfaces using React and TypeScript.
Develop and maintain REST APIs using Node.js and .NET.
Required Technical Skills
React is required for frontend development.
TypeScript is required for application development.
Node.js is required for backend development.
.NET and C# are required for maintaining existing services.
MongoDB is required for application data storage.
REST APIs experience is required.
JWT experience is required for authentication.
Jest is required for unit testing.
Docker is required for containerized development.
PostgreSQL is required for a new reporting service.
Preferred Technical Skills
Next.js experience is preferred.
Firebase and Firestore experience is preferred.
Gmail API and Outlook API experience is preferred.
Redux experience is preferred.
Redis experience is preferred for caching.
Kubernetes experience is preferred for deployment management.
Additional Information
GraphQL is used by a separate team.
Flutter is not required for this role.'''
    requirements = [{'skill': 'C#', 'priority': 'required', 'evidence': 'Wrong quote.'}]
    response = SimpleNamespace(message=SimpleNamespace(content=json.dumps({'requirements': requirements})))
    with patch('app.services.analyzer.chat', return_value=response) as mocked:
        result = extract_and_validate_jd_reqs({'job_description': jd})
    mocked.assert_called_once()
    reqs = {r['skill']: r for r in result['requirements']}
    assert sum(r['priority'] == 'required' for r in reqs.values()) == 11
    assert sum(r['priority'] == 'preferred' for r in reqs.values()) == 8
    assert reqs['graphql']['priority'] == 'unspecified'
    assert reqs['flutter']['priority'] == 'not_required'
    assert reqs['c#']['evidence'] == '.NET and C# are required for maintaining existing services.'
    assert all(r['evidence'] in jd for r in reqs.values())
    assert not result['warnings']


def test_valid_unknown_skill_is_retained_across_retries():
    def response(reqs):
        return SimpleNamespace(message=SimpleNamespace(content=json.dumps({'requirements': reqs})))
    rust = {'skill': 'Rust', 'priority': 'required', 'evidence': 'Rust required.'}
    scala_bad = {'skill': 'Scala', 'priority': 'required', 'evidence': 'Invented.'}
    scala_good = {'skill': 'Scala', 'priority': 'required', 'evidence': 'Scala required.'}
    with patch('app.services.analyzer.chat', side_effect=[response([rust, scala_bad]), response([scala_good])]):
        result = extract_and_validate_jd_reqs({'job_description': 'Rust required. Scala required.'})
    assert {r['skill'] for r in result['requirements']} == {'rust', 'scala'}
